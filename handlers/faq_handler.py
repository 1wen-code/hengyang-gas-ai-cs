"""
FAQ Handler — 知识库检索 + AI 自然组织语言 + 多轮上下文
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
    kb = _get_kb()

    # 多轮上下文：用 last_topic 增强搜索
    topic = session.get("last_topic", "")
    search_query = message
    if topic and len(message.strip()) <= 8:
        # 短追问 → 结合话题搜索
        search_query = f"{topic} {message}"

    faq = kb.search_faq(search_query)
    if not faq:
        faq = kb.search_faq(message)
    top_k = kb.search_top_k(search_query, k=3)

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
        topic_hint = f"（当前话题：{topic}）" if topic else ""
        user_msg = f"问题：{message}{topic_hint}\n\n参考资料：\n{context}"
        reply = deepseek.chat(FAQ_PROMPT, user_msg, history=history,
                              temperature=0.3, max_tokens=300)
        if reply:
            return {
                "reply": reply,
                "mode": "faq",
                "matched": faq.get("question", "") if faq else "",
                "category": faq.get("category", "") if faq else "",
            }

    if faq:
        return {
            "reply": faq["answer"],
            "mode": "faq",
            "matched": faq.get("question", ""),
            "category": faq.get("category", ""),
        }

    return {
        "reply": None,
        "mode": "normal",
    }
