"""
Router — 核心路由

严格顺序：
  1. smalltalk      — 最高优先，可退出 danger
  2. danger(mode)   — 已在危险中，优先处理
  3. detect_danger  — 新危险检测
  4. human          — 转人工
  5. faq            — 知识库匹配
  6. normal         — 通用 AI
"""

# 风险状态恢复确认提示
RECOVERY_PROMPT = (
    "系统检测到您此前提到了可能存在风险的信息。\n\n"
    "请确认目前是否仍存在以下情况：\n"
    "· 燃气泄漏\n"
    "· 明火或火灾\n"
    "· 人员受伤\n"
    "· 其他紧急状况\n\n"
    "请回复：\n"
    "「已解决」— 危险已排除，恢复正常\n"
    "「仍需帮助」— 情况仍未解决，继续求助"
)

from session_manager import sessions
from detectors import (
    detect_smalltalk, detect_danger, detect_cancel_danger,
    detect_human, detect_faq,
)
from handlers.danger_handler import handle as handle_danger
from handlers.smalltalk_handler import handle as handle_smalltalk
from handlers.human_handler import handle as handle_human
from handlers.faq_handler import handle as handle_faq
from handlers.normal_handler import handle as handle_normal


def route(message: str, session_id: str, client_ip: str = "",
          client_history: list = None) -> dict:
    """所有消息的唯一入口"""

    session = sessions.get(session_id)

    # 新对话 → 重置状态
    if not client_history:
        sessions.reset(session_id)
        session = sessions.get(session_id)

    # ═════════════════════════════════════════
    # 1. SMALLTALK — 最高优先（非 danger 模式下）
    # ═════════════════════════════════════════
    # 注意：如果当前已在 danger 模式，跳过 smalltalk 检测，
    # 让取消危险词（骗你的等）走恢复确认流程
    if session["mode"] != "danger" and detect_smalltalk(message):
        sessions.set_mode(session_id, "smalltalk")
        result = handle_smalltalk(message, session)
        _save_history(session_id, message, result["reply"])
        return result

    # ═════════════════════════════════════════
    # 2. 已在 DANGER 模式
    # ═════════════════════════════════════════
    if session["mode"] == "danger":

        # ── 恢复确认子状态 ──
        if sessions.is_recovering(session_id):
            # 用户确认安全 → 正式退出 danger
            confirm_kw = ["已解决", "解决了", "处理了", "没事了", "修好了",
                         "好了", "正常了", "安全了", "已处理", "搞定了",
                         "没有危险", "不危险", "没问题", "确认安全", "是安全的"]
            if any(kw in message for kw in confirm_kw):
                sessions.confirm_leave_danger(session_id)
                reply = "好的，已解除风险状态。如有其他燃气问题，可随时咨询。"
                _save_history(session_id, message, reply)
                return {"reply": reply, "mode": "normal", "source": "guide",
                        "risk": {"level": 1, "label": "普通"}, "risk_code": 1, "risk_level": "普通"}

            # 用户表示仍需帮助 → 回到 danger
            need_help = ["仍需帮助", "还要帮助", "没解决", "还有", "还在",
                        "仍然", "依然", "依旧", "继续", "需要帮助"]
            if any(kw in message for kw in need_help):
                sessions.exit_recovery(session_id)
                result = handle_danger(message, session, client_ip)
                if result.get("reply") is not None:
                    _save_history(session_id, message, result["reply"])
                    return result

            # 其他回复 → 再次提醒确认
            reply = RECOVERY_PROMPT
            _save_history(session_id, message, reply)
            return {"reply": reply, "mode": "danger", "source": "warning",
                    "risk": {"level": 2, "label": "恢复确认中"}}

        # ── 取消危险词 → 进入恢复确认状态 ──
        if detect_cancel_danger(message):
            sessions.enter_recovery(session_id)
            reply = RECOVERY_PROMPT
            _save_history(session_id, message, reply)
            return {"reply": reply, "mode": "danger", "source": "warning",
                    "risk": {"level": 2, "label": "恢复确认中"}}

        # ── 明显是业务问题 → 自动退出 danger，正常处理 ──
        if detect_faq(message) and not detect_danger(message):
            sessions.cancel_danger(session_id)

        # ── 继续危险处理 ──
        else:
            result = handle_danger(message, session, client_ip)
            if result.get("reply") is not None:
                new_mode = result.get("mode", "danger")
                sessions.set_mode(session_id, new_mode)
                if new_mode == "normal":
                    sessions.reset(session_id)
                _save_history(session_id, message, result["reply"])
                return result
            # reply=None → 降级，继续往下走

    # ═════════════════════════════════════════
    # 3. 新 DANGER 检测
    # ═════════════════════════════════════════
    if detect_danger(message):
        result = handle_danger(message, session, client_ip)
        # handler 可能返回 reply=None 表示 risk=1 应降级 normal
        if result.get("reply") is not None:
            sessions.set_mode(session_id, result.get("mode", "danger"))
            _save_history(session_id, message, result["reply"])
            return result

    # ═════════════════════════════════════════
    # 4. HUMAN
    # ═════════════════════════════════════════
    if detect_human(message):
        sessions.set_mode(session_id, "human")
        result = handle_human(message, session)
        _save_history(session_id, message, result["reply"])
        return result

    # ═════════════════════════════════════════
    # 5. FAQ
    # ═════════════════════════════════════════
    if detect_faq(message):
        result = handle_faq(message, session)
        if result.get("reply") is not None:
            sessions.set_mode(session_id, "faq")
            # 优先用 topic_tag（更精确），否则用 category
            new_topic = result.get("topic_tag") or result.get("category", "")
            if new_topic and len(message.strip()) > 4:
                # 长消息=新话题，短消息=保持旧话题
                sessions.set_topic(session_id, new_topic)
            elif not new_topic:
                pass  # 保持旧话题
            _save_history(session_id, message, result["reply"])
            return result

    # ═════════════════════════════════════════
    # 6. NORMAL — 兜底
    # ═════════════════════════════════════════
    sessions.set_mode(session_id, "normal")
    result = handle_normal(message, session)
    _save_history(session_id, message, result["reply"])
    return result


def _save_history(sid: str, user_msg: str, bot_msg: str):
    sessions.add_history(sid, "user", user_msg)
    sessions.add_history(sid, "assistant", bot_msg)
