"""
Human Handler — 固定回复，不调用 AI
"""
HUMAN_REPLY = (
    "好的，已了解您需要人工客服。\n\n"
    "请拨打衡阳燃气24小时客服热线：\n"
    "**0734-8677777**"
)


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    return {"reply": HUMAN_REPLY, "mode": "human", "source": "human_handler"}
