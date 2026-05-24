"""
Smalltalk Handler — 闲聊/问候独立处理

禁止触发危险系统，禁止长篇大论
"""
from deepseek_client import deepseek

SMALLTALK_PROMPT = """你是衡阳燃气客服助手。

用户正在闲聊或打招呼。

任务：
1. 友好简短回应
2. 自然引导回燃气业务
3. 不超过60字
4. 不要触发安全提醒
5. 不要长篇大论

如果用户说"骗你的""开玩笑"：
不要报警，不要追问安全状态，友好回应。"""

# 快速回复映射（不走 AI）
QUICK_REPLIES = {
    "你好": "您好，我是衡阳燃气AI客服，请问有什么可以帮您？",
    "您好": "您好，请问有什么燃气业务需要办理？",
    "hi": "您好，有什么可以帮您的吗？",
    "hello": "您好，有什么可以帮您的吗？",
    "在吗": "在的，请问有什么可以帮您？",
    "谢谢": "不客气，还有其他问题可以随时问我。",
    "感谢": "不客气，很高兴能帮到您。",
    "再见": "再见，如有燃气问题随时联系我们。祝您生活愉快！",
    "拜拜": "再见，祝您生活愉快！",
}


def handle_smalltalk(message: str, session: dict, history: list = None) -> dict:
    """处理闲聊/问候"""
    msg = message.strip().lower()

    # 快速回复
    if msg in QUICK_REPLIES:
        return {"reply": QUICK_REPLIES[msg], "mode": "smalltalk", "source": "smalltalk_handler"}

    # 简短输入（≤3字），直接引导
    if len(msg) <= 3:
        return {
            "reply": "您好，请问有什么燃气方面的问题需要咨询？",
            "mode": "smalltalk",
            "source": "smalltalk_handler",
        }

    # 调用 AI
    if deepseek:
        reply = deepseek.chat(
            system_prompt=SMALLTALK_PROMPT,
            user_message=f"用户说：{message}",
            temperature=0.5,
            max_tokens=100,
        )
        if reply:
            return {"reply": reply, "mode": "smalltalk", "source": "smalltalk_handler"}

    return {
        "reply": "您好，我是衡阳燃气AI客服，请问有什么需要帮您的？",
        "mode": "smalltalk",
        "source": "smalltalk_handler",
    }
