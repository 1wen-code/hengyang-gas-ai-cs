"""
FAQ Handler — 知识库直接返回，不调用 AI
"""
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


def _get_kb():
    global _kb
    if _kb is None:
        _kb = KnowledgeService()
    return _kb


def handle(message: str, session: dict, client_ip: str = "") -> dict:
    kb = _get_kb()
    msg = message.strip()

    # 多轮上下文：短追问结合 last_topic 搜索
    topic = session.get("last_topic", "")
    search_query = msg
    topic_tag = ""

    if topic and len(msg) <= 10:
        for key, keywords in TOPIC_EXTRACT.items():
            if any(kw in topic for kw in keywords):
                topic_tag = key
                break
        if topic_tag:
            search_query = f"{topic_tag} {msg}"

    # 知识库检索
    faq = kb.search_faq(search_query)
    if not faq or faq.get("score", 0) < MATCH_THRESHOLD:
        faq = kb.search_faq(msg)

    if faq and faq.get("score", 0) >= MATCH_THRESHOLD:
        # 场景过滤：匹配问题和用户问题场景不一致时，降级 normal
        faq_q = faq.get("question", "")
        faq_extra = ["国外", "海外", "委托", "代办", "商用", "工业", "饭店", "商铺"]
        has_extra = any(kw in faq_q and kw not in msg for kw in faq_extra)
        if has_extra:
            return {"reply": None, "mode": "normal", "source": "faq_handler"}

        new_category = faq.get("category", "")
        return {
            "reply": faq["answer"],
            "mode": "faq",
            "source": "faq_handler",
            "matched": faq_q,
            "category": new_category,
            "topic_tag": topic_tag or new_category,
        }

    # 未命中 → 降级 normal
    return {
        "reply": None,
        "mode": "normal",
        "source": "faq_handler",
    }
