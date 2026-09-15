"""
Danger Handler — 固定安全指令，不调用 AI
"""
from detectors import detect_danger
from services.emergency import detect_emergency, generate_ticket, log_emergency

DANGER_REPLY = (
    "检测到可能存在燃气安全风险，请立即关闭阀门、开窗通风、"
    "不要使用电器，并远离现场。请及时拨打衡阳燃气24小时抢修电话：0734-8677777。"
)

CANCEL_KW = ["没事了", "处理好了", "解决了", "修好了", "正常了",
             "骗你的", "开玩笑", "逗你", "测试的", "假的",
             "没味了", "关好了", "通风了", "已处理", "搞定了"]


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    msg = message.strip()

    # 取消危险 → 退出
    # CANCEL_KW 里「关好了」是子串：「阀门关好了，但还是有煤气味」不能算安全。
    # 话里仍带危险信号时一律不予解除。
    if any(kw in msg for kw in CANCEL_KW) and not detect_danger(message):
        return {
            "reply": "好的，确认安全了。还有其他燃气问题需要帮您吗？",
            "mode": "normal",
            "source": "guide",
            "risk": {"level": 1, "label": "普通"},
            "risk_code": 1,
            "risk_level": "普通",
            "ticket": None,
        }

    # 生成工单
    risk = detect_emergency(message)
    risk_level = risk["level"] if risk else 1
    risk_label = risk["risk_label"] if risk else "普通"
    ticket_id = None

    if risk and risk_level >= 2:
        uid = session.get("user_id", "")
        t = generate_ticket(message, risk_label, client_ip, uid)
        if t:
            ticket_id = t["工单ID"]
        # 落库失败时不编工单号，但安全事件照记 —— 用户看到的指引不受影响
        log_emergency(message, risk_label, client_ip, ticket_id or "")

    source = "emergency" if risk_level >= 3 else "warning"

    reply = DANGER_REPLY
    if ticket_id:
        reply = f"[工单 {ticket_id}] {reply}"

    return {
        "reply": reply,
        "mode": "danger",
        "source": source,
        "risk": {"level": risk_level, "label": risk_label},
        "risk_code": risk_level,
        "risk_level": risk_label,
        "ticket": ticket_id,
    }
