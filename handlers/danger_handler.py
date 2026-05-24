"""
Danger Handler — 独立危险模式
禁止：闲聊、RAG、条例、长篇、AI自由发挥
只允许：安全指令、简短确认、工单、转人工
"""
from deepseek_client import deepseek
from prompts import DANGER_PROMPT
from services.emergency import detect_emergency, generate_ticket, log_emergency


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    """
    返回: {"reply": str, "mode": "danger"|"normal", "ticket": str|None, "risk_level": str|None}
    """
    # 取消危险 → 退出
    cancel_kw = ["没事了", "处理好了", "解决了", "修好了", "正常了",
                 "骗你的", "开玩笑", "逗你", "测试的", "假的",
                 "没味了", "关好了", "通风了", "已处理", "搞定了"]
    if any(kw in message for kw in cancel_kw):
        return {
            "reply": "好的，确认安全了。后续如有异常请随时联系。还有其他燃气问题需要帮您吗？",
            "mode": "normal",
            "ticket": None,
            "risk_level": None,
        }

    # 安全指令类问题 → 直接返回固定步骤，不调 AI
    if any(kw in message for kw in ["怎么做", "怎么办", "怎么处理", "然后呢", "然后"]):
        return {
            "reply": (
                "请立即按以下步骤处理：\n"
                "1. 关闭燃气总阀门\n"
                "2. 打开门窗通风\n"
                "3. 不要开关电器、不使用明火\n"
                "4. 远离泄漏区域\n"
                "5. 拨打抢修电话 0734-8677777\n\n"
                "确认安全后请告诉我。"
            ),
            "mode": "danger",
            "ticket": None,
            "risk_level": None,
        }

    # 生成工单
    risk = detect_emergency(message)
    ticket_id = None
    risk_label = None
    if risk and risk["level"] >= 2:
        import uuid
        uid = str(uuid.uuid4().hex[:12])
        t = generate_ticket(message, risk["risk_label"], client_ip, uid)
        log_emergency(message, risk["risk_label"], client_ip, t["工单ID"])
        ticket_id = t["工单ID"]
        risk_label = risk["risk_label"]

    # 调用 AI 生成简短安全回复（不带历史）
    if deepseek:
        user_msg = f"用户说：{message}\n\n请简短回复，确认安全状态。"
        reply = deepseek.chat(DANGER_PROMPT, user_msg, history=None,
                              temperature=0.1, max_tokens=150)
        if reply:
            if ticket_id:
                reply = f"[工单 {ticket_id}] {reply}"
            return {
                "reply": reply,
                "mode": "danger",
                "ticket": ticket_id,
                "risk_level": risk_label,
            }

    # 兜底
    return {
        "reply": "请确保安全。如有燃气异味、明火或身体不适，请立即关闭阀门、开窗通风，拨打 0734-8677777。现在情况怎么样？",
        "mode": "danger",
        "ticket": ticket_id,
        "risk_level": risk_label,
    }
