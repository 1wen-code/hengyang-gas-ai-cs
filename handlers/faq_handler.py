"""
FAQ Handler — 知识库检索 + AI 自然组织语言
"""
from deepseek_client import deepseek
from prompts import FAQ_PROMPT
from services.knowledge_service import KnowledgeService

_kb = None


def _get_kb():
    global _kb
    if _kb is None:
        _kb = KnowledgeService()
    return _kb


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    """
    1. 检索知识库 top-3
    2. 把 context 给 AI
    3. AI 自然组织语言
    """
    kb = _get_kb()

    # 检索
    faq = kb.search_faq(message)
    top_k = kb.search_top_k(message, k=3)

    # 构建 context
    context = "无参考资料"
    if faq and faq.get("score", 0) >= 0.20:
        context = f"【最匹配】Q: {faq['question']}\nA: {faq['answer']}"
    elif top_k:
        parts = []
        for i, item in enumerate(top_k, 1):
            parts.append(f"【参考{i}】Q: {item['question']}\nA: {item['answer']}")
        context = "\n".join(parts)

    history = session.get("history", [])

    if deepseek:
        user_msg = f"问题：{message}\n\n参考资料：\n{context}"
        reply = deepseek.chat(FAQ_PROMPT, user_msg, history=history,
                              temperature=0.3, max_tokens=300)
        if reply:
            return {
                "reply": reply,
                "mode": "faq",
                "matched": faq.get("question", "") if faq else "",
                "category": faq.get("category", "") if faq else "",
            }

    # AI 不可用：直接用知识库原文
    if faq:
        return {
            "reply": faq["answer"],
            "mode": "faq",
            "matched": faq.get("question", ""),
            "category": faq.get("category", ""),
        }

    return {
        "reply": None,  # 信号：降级到 normal
        "mode": "normal",
    }
