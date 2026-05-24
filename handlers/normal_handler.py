"""
Normal Handler — 通用 AI 回答，带多轮上下文
"""
from deepseek_client import deepseek
from prompts import NORMAL_PROMPT
from services.knowledge_service import KnowledgeService

_kb = None


def _get_kb():
    global _kb
    if _kb is None:
        _kb = KnowledgeService()
    return _kb


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    kb = _get_kb()

    # RAG top-2
    faq = kb.search_faq(message)
    top_k = kb.search_top_k(message, k=2)

    context = "无参考资料"
    if faq and faq.get("score", 0) >= 0.20:
        context = f"Q: {faq['question']}\nA: {faq['answer']}"
    elif top_k:
        parts = []
        for i, item in enumerate(top_k, 1):
            parts.append(f"Q: {item['question']}\nA: {item['answer']}")
        context = "\n".join(parts)

    history = session.get("history", [])

    if deepseek:
        user_msg = f"问题：{message}\n\n参考资料：\n{context}"
        reply = deepseek.chat(NORMAL_PROMPT, user_msg, history=history,
                              temperature=0.3, max_tokens=300)
        if reply:
            return {
                "reply": reply,
                "mode": "normal",
                "matched": faq.get("question", "") if faq else "",
                "category": faq.get("category", "") if faq else "",
            }

    return {
        "reply": "您好，请问您遇到了什么燃气问题？我可以帮您查询或引导处理。",
        "mode": "normal",
    }
