"""
Human Handler — 转人工
"""
from deepseek_client import deepseek
from prompts import HUMAN_PROMPT


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    if deepseek:
        reply = deepseek.chat(HUMAN_PROMPT, f"用户说：{message}",
                              history=None, temperature=0.3, max_tokens=120)
        if reply:
            return {"reply": reply, "mode": "human", "source": "human_handler"}

    return {
        "reply": (
            "好的，已了解您需要人工客服。\n\n"
            "请拨打衡阳燃气24小时客服热线：\n"
            "**0734-8677777**"
        ),
        "mode": "human",
        "source": "human_handler",
    }
