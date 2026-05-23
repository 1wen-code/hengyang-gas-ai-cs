"""
语义归一化层 — UNDERSTAND
把用户口语、方言、模糊表达、情绪化表达
转换成标准燃气场景描述

管道位置：用户输入 → UNDERSTAND → 标准表达 → 风险判断 → 业务处理
"""
from openai import OpenAI
from config import DEEPSEEK_MODEL

UNDERSTAND_PROMPT = """你是燃气行业语义理解助手。

任务：把用户口语、模糊表达、情绪化表达，转换成标准燃气场景描述。

要求：
1. 不直接回答用户
2. 不输出建议
3. 只分析用户真正意思
4. 输出JSON

输出格式：
{
"normalized_intent": "用户真正想表达的标准燃气场景",
"possible_scene": "最可能的燃气故障或业务场景",
"risk_hint": "none|low|medium|high",
"emotion": "用户当前情绪"
}

---

示例

输入：灶台跟抽风一样
输出：
{"normalized_intent": "燃气灶火焰异常波动，忽大忽小", "possible_scene": "风门异常或燃气压力不稳", "risk_hint": "medium", "emotion": "困惑"}

输入：我家炸了没
输出：
{"normalized_intent": "用户怀疑家中是否发生燃气爆燃或泄漏事故", "possible_scene": "燃气安全确认", "risk_hint": "high", "emotion": "紧张"}

输入：那个灶今天发神经
输出：
{"normalized_intent": "燃气灶运行异常，火焰不稳定或点火故障", "possible_scene": "灶具故障", "risk_hint": "low", "emotion": "困惑"}

输入：跟放炮一样
输出：
{"normalized_intent": "燃气灶点火时发生爆燃声", "possible_scene": "点火爆燃/回火", "risk_hint": "high", "emotion": "紧张"}

输入：火像喘气
输出：
{"normalized_intent": "燃气火焰不稳定，忽大忽小像呼吸", "possible_scene": "燃气压力波动或管道问题", "risk_hint": "medium", "emotion": "困惑"}

输入：闻到煤气味怎么办
输出：
{"normalized_intent": "用户闻到疑似燃气泄漏的气味，需要紧急处理指导", "possible_scene": "燃气泄漏应急处置", "risk_hint": "high", "emotion": "紧张"}

输入：怎么交燃气费
输出：
{"normalized_intent": "用户想了解燃气费的缴纳方式和渠道", "possible_scene": "燃气缴费业务", "risk_hint": "none", "emotion": "平静"}

---

重要规则：
- 用户说"炸了没"、"爆炸了吗" → 不是闲聊，是安全确认，risk_hint至少medium
- 用户说方言/口语 → 翻译成标准故障描述
- 用户情绪化表达 → 提取背后的真实问题
- 不确定时 → normalized_intent写明"不确定"，不要编造

历史聊天：{chat_history}
当前问题：{question}"""


class UnderstandService:
    """语义归一化：口语→标准燃气场景"""

    def __init__(self, client: OpenAI):
        self._client = client

    def normalize(self, question: str, chat_history: str = "") -> dict:
        """归一化用户输入为标准燃气场景描述"""
        prompt = UNDERSTAND_PROMPT.format(
            chat_history=chat_history or "（无历史记录）",
            question=question,
        )
        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw)
        except Exception:
            return self._fallback(question)

    def _parse(self, raw: str) -> dict:
        import json, re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            raw = m.group(0)
        try:
            data = json.loads(raw)
            return {
                "normalized_intent": data.get("normalized_intent", ""),
                "possible_scene": data.get("possible_scene", ""),
                "risk_hint": data.get("risk_hint", "none"),
                "emotion": data.get("emotion", "平静"),
            }
        except (json.JSONDecodeError, ValueError):
            return self._fallback(question)

    def _fallback(self, question: str) -> dict:
        return {
            "normalized_intent": question,
            "possible_scene": "",
            "risk_hint": "none",
            "emotion": "",
        }
