"""
Normal Handler — AI 回答，80字以内，简洁专业
"""
from deepseek_client import deepseek
from prompts import NORMAL_PROMPT
from services.knowledge_service import KnowledgeService
from config import MATCH_THRESHOLD

_kb = None


def _scene_mismatch(user_msg: str, faq_question: str) -> bool:
    import jieba
    u_words = set(jieba.lcut(user_msg))
    f_words = set(jieba.lcut(faq_question))
    extra = f_words - u_words
    if not f_words:
        return False
    return len(extra) / len(f_words) > 0.4


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
    if faq and faq.get("score", 0) >= MATCH_THRESHOLD:
        if not _scene_mismatch(message, faq.get("question", "")):
            context = f"Q: {faq['question']}\nA: {faq['answer']}"
    if context == "无参考资料" and top_k:
        parts = []
        for i, item in enumerate(top_k, 1):
            parts.append(f"Q: {item['question']}\nA: {item['answer']}")
        context = "\n".join(parts)

    history = session.get("history", [])

    if deepseek:
        user_msg = f"问题：{message}\n\n参考资料：\n{context}"
        reply = deepseek.chat(NORMAL_PROMPT, user_msg, history=history,
                              temperature=0.3, max_tokens=200)
        if reply:
            return {
                "reply": reply,
                "mode": "normal",
                "source": "normal_handler",
                "matched": faq.get("question", "") if faq else "",
                "category": faq.get("category", "") if faq else "",
            }

    return {
        "reply": "您好，请问有什么燃气问题需要咨询？如需人工服务请拨打 0734-8677777。",
        "mode": "normal",
        "source": "normal_handler",
    }
