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
    返回包含前端预警所需的完整字段：
      source: "emergency"(高危) | "warning"(疑似)
      risk: {level, label}
      risk_code: int
      risk_level: str
      ticket: str | None
    """
    # 取消危险 → 退出
    cancel_kw = ["没事了", "处理好了", "解决了", "修好了", "正常了",
                 "骗你的", "开玩笑", "逗你", "测试的", "假的",
                 "没味了", "关好了", "通风了", "已处理", "搞定了"]
    if any(kw in message for kw in cancel_kw):
        return {
            "reply": "好的，确认安全了。后续如有异常请随时联系。还有其他燃气问题需要帮您吗？",
            "mode": "normal",
            "source": "guide",
            "risk": {"level": 1, "label": "普通"},
            "risk_code": 1,
            "risk_level": "普通",
            "ticket": None,
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
            "source": "emergency",
            "risk": {"level": 3, "label": "高危"},
            "risk_code": 3,
            "risk_level": "高危",
            "ticket": None,
        }

    # 生成工单
    risk = detect_emergency(message)
    ticket_id = None
    risk_level_num = 1
    risk_label = "普通"
    if risk:
        risk_level_num = risk["level"]
        risk_label = risk["risk_label"]
        if risk_level_num >= 2:
            import uuid
            uid = str(uuid.uuid4().hex[:12])
            t = generate_ticket(message, risk_label, client_ip, uid)
            log_emergency(message, risk_label, client_ip, t["工单ID"])
            ticket_id = t["工单ID"]

    # 前端 source 映射
    if risk_level_num >= 3:
        source = "emergency"
    elif risk_level_num >= 2:
        source = "warning"
    else:
        source = "danger_handler"

    # risk=1 不应该用危险语气，降级到 normal 模式
    if risk_level_num < 2:
        return {
            "reply": None,  # 信号：router 降级到 normal
            "mode": "normal",
            "source": "guide",
            "risk": {"level": 1, "label": "普通"},
            "risk_code": 1,
            "risk_level": "普通",
            "ticket": None,
        }

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
                "source": source,
                "risk": {"level": risk_level_num, "label": risk_label},
                "risk_code": risk_level_num,
                "risk_level": risk_label,
                "ticket": ticket_id,
            }

    # 兜底
    return {
        "reply": "请确保安全。如有燃气异味、明火或身体不适，请立即关闭阀门、开窗通风，拨打 0734-8677777。现在情况怎么样？",
        "mode": "danger",
        "source": source,
        "risk": {"level": risk_level_num, "label": risk_label},
        "risk_code": risk_level_num,
        "risk_level": risk_label,
        "ticket": ticket_id,
    }
