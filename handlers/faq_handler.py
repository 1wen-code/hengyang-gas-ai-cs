"""
FAQ Handler — 知识库匹配 + AI润色

FAQ 只负责业务知识回答，禁止危险提示污染
"""
from deepseek_client import deepseek
from services.knowledge_service import KnowledgeService
from config import MATCH_THRESHOLD

FAQ_POLISH_PROMPT = """你是衡阳燃气客服，语气亲切自然。

把以下标准答案用自然口语重新表达一遍。

规则：
1. 保持原意，不添加额外信息
2. 不生成新的条例、法规、安全建议
3. 不推测风险
4. 不拼接其他知识
5. 不超过200字

标准答案：
{structured_answer}"""

# 全局知识库实例
_kb: KnowledgeService | None = None


def _get_kb() -> KnowledgeService:
    global _kb
    if _kb is None:
        _kb = KnowledgeService()
    return _kb


def handle_faq(message: str, session: dict, history: list = None) -> dict:
    """
    FAQ 模式：先匹配知识库，再用 AI 润色。

    返回: {"reply": str, "mode": "faq", "source": "faq_handler", "matched": str}
    """
    kb = _get_kb()
    result = kb.search_faq(message)

    # 命中 FAQ
    if result and result.get("score", 0) >= MATCH_THRESHOLD:
        structured = result["answer"]

        # 用 AI 润色
        if deepseek:
            polished = deepseek.chat(
                system_prompt=FAQ_POLISH_PROMPT.format(structured_answer=structured),
                user_message=f"用户问：{message}",
                temperature=0.3,
                max_tokens=250,
            )
            if polished and len(polished) > 20:
                return {
                    "reply": polished,
                    "mode": "faq",
                    "source": "faq_handler",
                    "matched": result.get("question", ""),
                    "score": result.get("score", 0),
                    "category": result.get("category", ""),
                }

        # 直接用原始答案
        return {
            "reply": structured,
            "mode": "faq",
            "source": "faq_handler",
            "matched": result.get("question", ""),
            "score": result.get("score", 0),
            "category": result.get("category", ""),
        }

    # FAQ 未命中，降级到 normal
    return {
        "reply": None,  # 信号：降级
        "mode": "normal",
        "source": "faq_handler",
    }
