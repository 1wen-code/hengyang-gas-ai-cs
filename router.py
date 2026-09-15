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

# 危险模式下用户插入业务问题：正常作答，但不解除风险状态
DANGER_REMINDER = (
    "\n\n---\n⚠️ 提醒：您刚才提到的燃气异味**尚未确认排除**。"
    "如仍有气味，请立即关闭总阀门、开窗通风，并拨打 0734-8677777。"
)

# 恢复确认中插入业务问题：作答后只留一句确认提示，不再重复整段
RECOVERY_REMINDER = (
    "\n\n---\n您遇到的燃气风险是否已排除？"
    "回复「已解决」解除风险状态，或「仍需帮助」继续求助。"
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

    # 危险期间插入业务问题 → 由 _apply_sticky 在作答后恢复风险状态
    sticky = None

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
            # 用户表示仍需帮助 → 回到 danger
            # 必须先判：confirm_kw 里「好了」「没问题」是子串匹配，
            # 「阀门关好了，但还是有煤气味」会先撞上 confirm_kw 被判成安全
            need_help = ["仍需帮助", "还要帮助", "没解决", "还有", "还在", "还是",
                        "仍然", "依然", "依旧", "继续", "需要帮助"]
            if any(kw in message for kw in need_help):
                sessions.exit_recovery(session_id)
                result = handle_danger(message, session, client_ip)
                if result.get("reply") is not None:
                    _save_history(session_id, message, result["reply"])
                    return result

            # 用户确认安全 → 正式退出 danger
            confirm_kw = ["已解决", "解决了", "处理了", "没事了", "修好了",
                         "好了", "正常了", "安全了", "已处理", "搞定了",
                         "没有危险", "不危险", "没问题", "确认安全", "是安全的"]
            # 硬守卫：话里还带着危险信号，就不许判"已解除"。
            # 「阀门关好了，但还是有煤气味」——"好了"是子串，靠词表挡不住
            if any(kw in message for kw in confirm_kw) and not detect_danger(message):
                sessions.confirm_leave_danger(session_id)
                reply = "好的，已解除风险状态。如有其他燃气问题，可随时咨询。"
                _save_history(session_id, message, reply)
                return {"reply": reply, "mode": "normal", "source": "guide",
                        "risk": {"level": 1, "label": "普通"}, "risk_code": 1, "risk_level": "普通"}

            # 业务问题 → 正常作答，但保留确认状态（否则用户被锁死，什么都问不了）
            if detect_faq(message) and not detect_danger(message):
                sticky = "recovery"
            else:
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

        # ── 业务问题 → 作答但不退出 danger（静默退出会丢掉未排除的风险）──
        # sticky is None 守卫：恢复确认态已判定过，别在这里被覆盖成 danger
        if sticky is None and detect_faq(message) and not detect_danger(message):
            sticky = "danger"

        # ── 继续危险处理 ──
        elif sticky is None:
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
        result = _apply_sticky(session_id, result, sticky)
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
            if new_topic and len(message.strip()) >= 3:
                # 长消息=新话题，短消息=保持旧话题
                sessions.set_topic(session_id, new_topic)
            elif not new_topic:
                pass  # 保持旧话题
            result = _apply_sticky(session_id, result, sticky)
            _save_history(session_id, message, result["reply"])
            return result

    # ═════════════════════════════════════════
    # 6. NORMAL — 兜底
    # ═════════════════════════════════════════
    sessions.set_mode(session_id, "normal")
    result = handle_normal(message, session)
    result = _apply_sticky(session_id, result, sticky)
    _save_history(session_id, message, result["reply"])
    return result


def _apply_sticky(session_id: str, result: dict, sticky: str | None) -> dict:
    """
    危险期间插入业务问题：照常作答，但不丢失风险状态。

    sticky="danger"   危险模式中问业务问题 → 保留 danger + 安全提醒
    sticky="recovery" 恢复确认中问业务问题 → 保留确认态 + 一句确认提示

    背景：早先的做法是静默退出 danger，导致用户问完业务问题后
    再说"还有味道"不会重新报警；恢复确认态则会死循环、什么都答不了。
    """
    if not sticky:
        return result

    sessions.set_mode(session_id, "danger")
    if sticky == "recovery":
        sessions.enter_recovery(session_id)
        result["reply"] = (result.get("reply") or "") + RECOVERY_REMINDER
        label = "恢复确认中"
    else:
        result["reply"] = (result.get("reply") or "") + DANGER_REMINDER
        label = "疑似风险（未确认排除）"

    result["mode"] = "danger"
    result["risk"] = {"level": 2, "label": label}
    result["risk_code"] = 2
    result["risk_level"] = "疑似风险"
    return result


def _save_history(sid: str, user_msg: str, bot_msg: str):
    sessions.add_history(sid, "user", user_msg)
    sessions.add_history(sid, "assistant", bot_msg)
