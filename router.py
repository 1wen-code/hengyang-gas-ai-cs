"""
Router — 轻量路由，严格顺序分发

所有消息：前端 → Flask → Router → Handler → 回复
Router 决定 mode，AI 不允许决定 mode
"""
from session_manager import session_manager
from detectors import (
    detect_smalltalk,
    detect_human,
    detect_danger,
    detect_faq,
    detect_normal,
)
from handlers import (
    handle_smalltalk,
    handle_human,
    handle_danger,
    handle_faq,
    handle_normal,
)
from services.knowledge_service import KnowledgeService
from services.emergency import detect_emergency, generate_ticket, log_emergency

_kb = None


def _kb():
    global _kb
    if _kb is None:
        _kb = KnowledgeService()
    return _kb


def route_message(message, session_id, client_ip="", client_history=None):
    """
    路由顺序（严格）：
      1. smalltalk — 最高优先级（骗你的/开玩笑/哈哈 → 退出 danger）
      2. human     — 转人工
      3. danger    — 真实危险
      4. faq       — 业务关键词 → 知识库检索
      5. normal    — 通用 AI 回答
    """
    session = session_manager.get(session_id)
    mode = session["mode"]
    msg = message.strip()
    history = client_history or []
    result = None

    # 新对话 → 重置
    if not client_history:
        session_manager.reset(session_id)
        mode = "normal"

    # ── 0. 非燃气相关 → smalltalk ──
    if not detect_normal(msg):
        result = handle_smalltalk(msg, session, history)
        session_manager.set_mode(session_id, "smalltalk")
        return result

    # ═════════════════════════════════════════
    # 1. SMALLTALK — 最高优先级
    #    "骗你的""开玩笑" 必须退出 danger
    # ═════════════════════════════════════════
    if detect_smalltalk(msg):
        if mode == "danger":
            session_manager.cancel_danger(session_id)
        result = handle_smalltalk(msg, session, history)
        session_manager.set_mode(session_id, "smalltalk")
        return result

    # ── 当前在 danger 模式 → 继续 danger handler ──
    if mode == "danger":
        result = handle_danger(msg, session, history)
        new_mode = result.get("mode", "danger")
        if new_mode == "normal":
            session_manager.cancel_danger(session_id)
        else:
            session_manager.set_mode(session_id, "danger")
        return result

    # ═════════════════════════════════════════
    # 2. HUMAN
    # ═════════════════════════════════════════
    if detect_human(msg):
        result = handle_human(msg, session, history)
        session_manager.set_mode(session_id, "human")
        return result

    if mode == "human":
        result = handle_human(msg, session, history)
        return result

    # ═════════════════════════════════════════
    # 3. DANGER
    # ═════════════════════════════════════════
    if detect_danger(msg):
        session_manager.confirm_danger(session_id)
        result = handle_danger(msg, session, history)
        new_mode = result.get("mode", "danger")
        if new_mode == "normal":
            session_manager.cancel_danger(session_id)
        else:
            session_manager.set_mode(session_id, "danger")

        # 高风险 → 工单
        risk = detect_emergency(msg)
        if risk and risk["level"] >= 2:
            import uuid
            uid = session.get("user_id", "")
            if not uid:
                uid = uuid.uuid4().hex[:12]
                session["user_id"] = uid
            ticket = generate_ticket(msg, risk["risk_label"], client_ip, uid)
            log_emergency(msg, risk["risk_label"], client_ip, ticket["工单ID"])
            prefix = risk.get("reply", "")
            if prefix and result.get("reply"):
                result["reply"] = prefix + "\n\n" + result["reply"]
            result["ticket"] = ticket["工单ID"]
            result["risk_level"] = risk["risk_label"]
            result["risk_code"] = risk["level"]
        return result

    # ═════════════════════════════════════════
    # 4. FAQ
    # ═════════════════════════════════════════
    if detect_faq(msg):
        result = handle_faq(msg, session, history)
        if result.get("reply") is not None:
            session_manager.set_mode(session_id, "faq")
            session_manager.set_topic(session_id, result.get("category", ""))
            return result
        # FAQ handler 未命中 → 降级 normal

    # ═════════════════════════════════════════
    # 5. NORMAL — 兜底
    # ═════════════════════════════════════════
    session_manager.set_mode(session_id, "normal")
    return handle_normal(msg, session, history)
