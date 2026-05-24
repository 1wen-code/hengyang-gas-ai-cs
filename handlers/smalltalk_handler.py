"""
Smalltalk Handler — 固定回复，不调用 AI
"""
FIXED_REPLIES = {
    "你好": "您好，请问有什么可以帮您？",
    "您好": "您好，请问有什么可以帮您？",
    "hi": "您好，请问有什么可以帮您？",
    "hello": "您好，请问有什么可以帮您？",
    "嗨": "您好，请问有什么可以帮您？",
    "你是谁": "我是衡阳燃气AI客服。",
    "你叫什么": "我是衡阳燃气AI客服。",
    "谢谢": "不客气，很高兴为您服务。",
    "感谢": "不客气，很高兴为您服务。",
    "多谢": "不客气，很高兴为您服务。",
    "再见": "感谢咨询，祝您生活愉快。",
    "拜拜": "感谢咨询，祝您生活愉快。",
    "bye": "感谢咨询，祝您生活愉快。",
}
DEFAULT_REPLY = "请问有什么燃气业务问题需要咨询？"


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    key = message.strip()
    reply = FIXED_REPLIES.get(key, DEFAULT_REPLY)
    return {"reply": reply, "mode": "smalltalk", "source": "smalltalk"}
