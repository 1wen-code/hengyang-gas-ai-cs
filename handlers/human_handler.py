"""
Human Handler — 转人工模式
"""
from deepseek_client import deepseek

HUMAN_PROMPT = """你是衡阳燃气客服助手。

用户要求转人工客服。

请输出：
1. 告知已了解用户需要人工服务
2. 提供联系方式
3. 不超过80字

衡阳燃气24小时客服热线：0734-8677777"""


def handle_human(message: str, session: dict, history: list = None) -> dict:
    """处理转人工请求"""
    if deepseek:
        reply = deepseek.chat(
            system_prompt=HUMAN_PROMPT,
            user_message=f"用户说：{message}",
            temperature=0.3,
            max_tokens=120,
        )
        if reply:
            return {"reply": reply, "mode": "human", "source": "human_handler"}

    return {
        "reply": (
            "好的，已了解您需要人工客服。\n\n"
            "请拨打衡阳燃气24小时客服热线：\n"
            "**0734-8677777**\n\n"
            "如需紧急帮助也可直接拨打此号码。"
        ),
        "mode": "human",
        "source": "human_handler",
    }
