"""
Smalltalk Handler — AI 自然回复
"""
from deepseek_client import deepseek
from prompts import SMALLTALK_PROMPT


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    """
    返回: {"reply": str, "mode": "smalltalk"}
    """
    if deepseek:
        reply = deepseek.chat(
            SMALLTALK_PROMPT,
            f"用户说：{message}",
            history=None,
            temperature=0.5,
            max_tokens=120,
        )
        if reply:
            return {"reply": reply, "mode": "smalltalk"}

    return {"reply": "您好，请问有什么燃气方面的问题需要咨询？", "mode": "smalltalk"}
