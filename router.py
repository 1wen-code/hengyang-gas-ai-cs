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
    # 1. SMALLTALK — 最高优先
    # ═════════════════════════════════════════
    if detect_smalltalk(message):
        sessions.set_mode(session_id, "smalltalk")
        result = handle_smalltalk(message, session)
        _save_history(session_id, message, result["reply"])
        return result

    # ═════════════════════════════════════════
    # 2. 已在 DANGER 模式
    # ═════════════════════════════════════════
    if session["mode"] == "danger":
        if detect_cancel_danger(message):
            sessions.set_mode(session_id, "normal")
            reply = "好的，确认安全了。还有其他燃气问题需要帮您吗？"
            _save_history(session_id, message, reply)
            return {"reply": reply, "mode": "normal", "source": "guide",
                    "risk": {"level": 1, "label": "普通"}, "risk_code": 1, "risk_level": "普通"}

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
