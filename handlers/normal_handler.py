"""
Normal Handler — 通用模式

允许 AI 自然说话，但限制长度，不要长篇官话
"""
from deepseek_client import deepseek
from services.knowledge_service import KnowledgeService

NORMAL_PROMPT = """你是衡阳燃气AI客服。

请像真实客服一样自然回答用户问题。

要求：
- 简洁、口语化
- 不要重复
- 不要长篇条例
- 优先解决问题
- 不超过200字"""

# 全局知识库
_kb: KnowledgeService | None = None


def _get_kb() -> KnowledgeService:
    global _kb
    if _kb is None:
        _kb = KnowledgeService()
    return _kb


def handle_normal(message: str, session: dict, history: list = None) -> dict:
    """
    Normal 模式：RAG 提供参考资料，AI 生成回答。

    RAG 只提供 top-1 to top-2 参考资料，不拼接全文。
    """
    kb = _get_kb()

    # RAG 检索：只取 top-2
    faq = kb.search_faq(message)
    top_k = kb.search_top_k(message, k=2)

    reference = "无参考资料"
    if faq and faq.get("score", 0) >= 0.20:
        reference = f"【最匹配】{faq['question']}\n答案：{faq['answer']}"
    elif top_k:
        refs = []
        for i, item in enumerate(top_k, 1):
            refs.append(f"【参考{i}】{item['question']}\n答案：{item['answer']}")
        reference = "\n".join(refs)

    # 格式化历史
    chat_history = "无历史"
    if history:
        lines = []
        for h in history[-4:]:
            role = "用户" if h.get("role") == "user" else "客服"
            content = h.get("content", "")[:80]
            lines.append(f"{role}：{content}")
        chat_history = "\n".join(lines)

    # 构建 user message
    user_msg = f"""参考资料：
{reference}

当前问题：{message}"""

    # 构建 system prompt
    system = NORMAL_PROMPT + f"\n\n历史对话：\n{chat_history}" if chat_history != "无历史" else NORMAL_PROMPT

    if deepseek:
        reply = deepseek.chat(
            system_prompt=system,
            user_message=user_msg,
            temperature=0.3,
            max_tokens=300,
        )
        if reply:
            matched_question = faq.get("question", "") if faq else ""
            return {
                "reply": reply,
                "mode": "normal",
                "source": "normal_handler",
                "matched": matched_question,
            }

    # AI 不可用时的兜底
    return {
        "reply": "您好，请问您遇到了什么燃气问题？我可以帮您查询相关信息或引导您处理。",
        "mode": "normal",
        "source": "normal_handler",
    }
