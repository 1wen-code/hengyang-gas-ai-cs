"""
Normal Handler — AI 回答，80字以内，简洁专业
"""
import jieba
from deepseek_client import deepseek
from prompts import NORMAL_PROMPT
from services.knowledge_service import KnowledgeService
from config import MATCH_THRESHOLD

_kb = None

# 话题关键词映射
TOPIC_EXTRACT = {
    "开户": ["开户", "报装", "新装", "安装费", "点火", "通气"],
    "缴费": ["缴费", "充值", "交费", "气价", "阶梯", "欠费"],
    "过户": ["过户", "变更", "换户主"],
    "维修": ["维修", "报修", "故障", "打不着", "不出热水"],
    "安检": ["安检", "检查", "安全"],
    "投诉": ["投诉", "意见", "建议"],
}


def _scene_mismatch(user_msg: str, faq_question: str) -> bool:
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
    msg = message.strip()

    # 多轮上下文增强
    topic = session.get("last_topic", "")
    search_msg = msg
    topic_tag = ""
    if topic and len(msg) <= 10:
        for key, keywords in TOPIC_EXTRACT.items():
            if any(kw in topic for kw in keywords):
                topic_tag = key
                break
        if topic_tag:
            search_msg = f"{topic_tag} {msg}"

    # RAG top-2
    faq = kb.search_faq(search_msg)
    if not faq or faq.get("score", 0) < MATCH_THRESHOLD:
        faq = kb.search_faq(msg)
    top_k = kb.search_top_k(search_msg, k=2)

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
