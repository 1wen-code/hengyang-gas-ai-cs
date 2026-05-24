"""
Danger Handler — 危险模式独立处理

禁止：闲聊、RAG、条例宣传、长篇分析、AI自由发挥
只允许：安全动作、简短确认、是否转人工
"""
from deepseek_client import deepseek

DANGER_PROMPT = """你是燃气安全助手。

用户可能存在危险。

目标：优先确认安全状态。

禁止：闲聊、长篇解释、法规宣传、自由扩展。

回答必须：短、直接、安全优先。

如果用户说"没事了""处理好了""骗你的""开玩笑"：
接受并回复安抚语，不继续报警。"""


def handle_danger(message: str, session: dict, history: list = None) -> dict:
    """
    处理危险模式下的用户消息。

    返回: {"reply": str, "mode": "danger", "source": "danger_handler"}
    """
    msg = message.strip()

    # 快速规则：用户确认安全
    cancel_kw = ["没事了", "处理好了", "解决了", "修好了", "正常了",
                 "骗你的", "开玩笑", "逗你", "测试的", "假的",
                 "没味了", "关好了", "通风了", "已处理", "搞定了",
                 "好了", "没事", "不响了", "没闻到", "不臭了"]
    if any(kw in msg for kw in cancel_kw):
        return {
            "reply": "好的，确认安全就好。如果后续再闻到异味或有异常，随时联系我们。还有其他燃气问题需要帮您吗？",
            "mode": "normal",
            "source": "danger_handler",
        }

    # 快速规则：安全指令类，直接返回固定回答
    if any(kw in msg for kw in ["怎么做", "怎么办", "怎么处理", "然后", "然后呢"]):
        return {
            "reply": (
                "请按以下步骤处理：\n"
                "1. 立即关闭燃气总阀门\n"
                "2. 打开门窗通风\n"
                "3. 不要开关任何电器\n"
                "4. 不要使用明火\n"
                "5. 远离泄漏区域\n\n"
                "确认安全后请告诉我。如需紧急帮助，请拨打 0734-8677777。"
            ),
            "mode": "danger",
            "source": "danger_handler",
        }

    # 调用 DeepSeek 生成简短安全回复
    if deepseek:
        reply = deepseek.chat(
            system_prompt=DANGER_PROMPT,
            user_message=f"用户消息：{msg}",
            temperature=0.1,
            max_tokens=150,  # 极短回复
        )
        if reply:
            return {"reply": reply, "mode": "danger", "source": "danger_handler"}

    # 兜底
    return {
        "reply": "请确保安全。如有燃气异味、明火或身体不适，请立即关闭阀门、开窗通风，并拨打 0734-8677777。现在情况怎么样了？",
        "mode": "danger",
        "source": "danger_handler",
    }
