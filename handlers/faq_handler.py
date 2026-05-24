"""
FAQ Handler — 知识库检索 + AI 自然组织语言 + 多轮上下文
"""
from deepseek_client import deepseek
from prompts import FAQ_PROMPT
from services.knowledge_service import KnowledgeService
from config import MATCH_THRESHOLD

_kb = None

# 话题关键词映射，用于提取核心话题
TOPIC_EXTRACT = {
    "开户": ["开户", "报装", "新装", "安装费", "点火", "通气"],
    "缴费": ["缴费", "充值", "交费", "气价", "阶梯", "欠费"],
    "过户": ["过户", "变更", "换户主"],
    "维修": ["维修", "报修", "故障", "打不着", "不出热水"],
    "安检": ["安检", "检查", "安全"],
    "投诉": ["投诉", "意见", "建议"],
}


def _get_kb():
    global _kb
    if _kb is None:
        _kb = KnowledgeService()
    return _kb


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    kb = _get_kb()

    topic = session.get("last_topic", "")
    msg = message.strip()

    # 多轮上下文：短追问用话题增强搜索
    search_query = msg
    topic_tag = ""
    if topic and len(msg) <= 10:
        # 提取核心话题词
        for key, keywords in TOPIC_EXTRACT.items():
            if any(kw in topic for kw in keywords):
                topic_tag = key
                break
        if topic_tag:
            search_query = f"{topic_tag} {msg}"

    faq = kb.search_faq(search_query)
    if not faq:
        faq = kb.search_faq(msg)
    top_k = kb.search_top_k(search_query, k=3)

    context = "无参考资料"
    if faq and faq.get("score", 0) >= MATCH_THRESHOLD:
        context = f"【最匹配】Q: {faq['question']}\nA: {faq['answer']}"
    elif top_k:
        parts = []
        for i, item in enumerate(top_k, 1):
            parts.append(f"【参考{i}】Q: {item['question']}\nA: {item['answer']}")
        context = "\n".join(parts)

    history = session.get("history", [])

    if deepseek:
        # 强话题提示
        topic_line = f"上一轮话题：{topic_tag or topic}。用户在追问。" if topic else ""
        user_msg = f"{topic_line}\n问题：{msg}\n\n参考资料：\n{context}"
        reply = deepseek.chat(FAQ_PROMPT, user_msg, history=history,
                              temperature=0.3, max_tokens=300)
        if reply:
            # 更新话题：保留原话题（不覆盖，除非是新话题）
            new_category = faq.get("category", "") if faq else ""
            return {
                "reply": reply,
                "mode": "faq",
                "matched": faq.get("question", "") if faq else "",
                "category": new_category,
                "topic_tag": topic_tag,
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
