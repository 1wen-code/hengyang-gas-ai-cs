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

【安全确认类】

输入：我家炸了没
输出：{"normalized_intent": "用户怀疑家中是否发生燃气爆燃或泄漏事故", "possible_scene": "燃气安全确认", "risk_hint": "high", "emotion": "紧张"}

输入：我家燃气爆炸了没有
输出：{"normalized_intent": "用户确认家中是否发生燃气爆炸", "possible_scene": "燃气爆炸事故确认", "risk_hint": "high", "emotion": "恐慌"}

输入：刚刚砰一下是不是炸了
输出：{"normalized_intent": "用户听到爆燃声，怀疑发生燃气爆炸", "possible_scene": "燃气爆燃/回火", "risk_hint": "high", "emotion": "紧张"}

输入：有没有爆炸的危险
输出：{"normalized_intent": "用户担心当前情况可能导致燃气爆炸", "possible_scene": "燃气安全风险评估", "risk_hint": "high", "emotion": "担忧"}

---

【方言/口语故障类】

输入：灶台跟抽风一样
输出：{"normalized_intent": "燃气灶火焰异常波动，忽大忽小", "possible_scene": "风门异常或燃气压力不稳", "risk_hint": "medium", "emotion": "困惑"}

输入：那个灶今天发神经
输出：{"normalized_intent": "燃气灶运行异常，火焰不稳定或点火故障", "possible_scene": "灶具故障", "risk_hint": "low", "emotion": "困惑"}

输入：跟放炮一样
输出：{"normalized_intent": "燃气灶点火时发生爆燃声", "possible_scene": "点火爆燃/回火", "risk_hint": "high", "emotion": "紧张"}

输入：火像喘气
输出：{"normalized_intent": "燃气火焰不稳定，忽大忽小像呼吸", "possible_scene": "燃气压力波动或管道问题", "risk_hint": "medium", "emotion": "困惑"}

输入：煤气灶冒扑
输出：{"normalized_intent": "燃气灶点火时有回火或爆燃现象", "possible_scene": "回火/爆燃", "risk_hint": "high", "emotion": "困惑"}

输入：火苗突突的
输出：{"normalized_intent": "燃气火焰不稳定，出现波动或跳动", "possible_scene": "供气压力不稳或风门问题", "risk_hint": "medium", "emotion": "困惑"}

输入：灶台哗哗响
输出：{"normalized_intent": "燃气灶使用时发出异常噪音", "possible_scene": "燃气流动异常或灶具部件松动", "risk_hint": "medium", "emotion": "困惑"}

输入：打火哒哒响就是不着
输出：{"normalized_intent": "燃气灶点火时有哒哒声但无法点燃", "possible_scene": "点火针故障或燃气未到达", "risk_hint": "low", "emotion": "困惑"}

输入：火没劲
输出：{"normalized_intent": "燃气灶火焰太小，火力不足", "possible_scene": "气压不足或阀门未全开", "risk_hint": "low", "emotion": "困惑"}

输入：时好时坏
输出：{"normalized_intent": "燃气设备间歇性故障，不稳定", "possible_scene": "设备老化或供气不稳", "risk_hint": "medium", "emotion": "无奈"}

---

【泄漏/气味类】

输入：闻到煤气味怎么办
输出：{"normalized_intent": "用户闻到疑似燃气泄漏的气味，需要紧急处理指导", "possible_scene": "燃气泄漏应急处置", "risk_hint": "high", "emotion": "紧张"}

输入：感觉有怪味
输出：{"normalized_intent": "用户闻到异常气味，怀疑燃气泄漏", "possible_scene": "疑似燃气泄漏", "risk_hint": "high", "emotion": "担忧"}

输入：厨房臭臭的
输出：{"normalized_intent": "用户厨房有异常气味，可能涉及燃气", "possible_scene": "燃气泄漏排查", "risk_hint": "high", "emotion": "困惑"}

输入：有点冲鼻子
输出：{"normalized_intent": "用户闻到刺激性气味，疑似燃气加臭剂", "possible_scene": "燃气泄漏检测", "risk_hint": "high", "emotion": "担忧"}

---

【身体不适类（不能直接判燃气中毒）】

输入：我妈头有点晕
输出：{"normalized_intent": "用户家属出现头晕症状，需排查是否与燃气有关", "possible_scene": "健康异常，可能涉及燃气安全", "risk_hint": "medium", "emotion": "担忧"}

输入：感觉恶心是不是燃气漏了
输出：{"normalized_intent": "用户出现恶心症状，怀疑与燃气泄漏有关", "possible_scene": "身体不适+燃气泄漏怀疑", "risk_hint": "high", "emotion": "担忧"}

输入：有点不舒服不知道是不是煤气
输出：{"normalized_intent": "用户身体不适，不确定是否与燃气有关", "possible_scene": "健康异常排查", "risk_hint": "medium", "emotion": "困惑"}

---

【业务办理类】

输入：怎么交燃气费
输出：{"normalized_intent": "用户想了解燃气费的缴纳方式和渠道", "possible_scene": "燃气缴费业务", "risk_hint": "none", "emotion": "平静"}

输入：没气了是不是要交钱了
输出：{"normalized_intent": "用户家中停气，怀疑是欠费需要缴费", "possible_scene": "欠费停气/缴费恢复", "risk_hint": "low", "emotion": "困惑"}

输入：去哪开户
输出：{"normalized_intent": "用户想办理燃气新装开户业务", "possible_scene": "燃气开户", "risk_hint": "none", "emotion": "平静"}

输入：燃气不够用
输出：{"normalized_intent": "用户觉得燃气火力或气量不足", "possible_scene": "气压不足或余额不足", "risk_hint": "low", "emotion": "困惑"}

---

【情绪发泄类】

输入：气死了报修三天没人来
输出：{"normalized_intent": "用户报修后长时间无人上门处理，非常愤怒", "possible_scene": "报修投诉", "risk_hint": "low", "emotion": "愤怒"}

输入：你们客服太差了
输出：{"normalized_intent": "用户对客服服务不满意，需要投诉", "possible_scene": "服务投诉", "risk_hint": "none", "emotion": "愤怒"}

---

【简短追问类（需结合历史）】

输入：右边
输出：{"normalized_intent": "用户确认故障位置在右侧灶头", "possible_scene": "灶具故障定位", "risk_hint": "low", "emotion": "平静"}

输入：还是不行
输出：{"normalized_intent": "用户按建议操作后问题仍未解决", "possible_scene": "故障排查未果", "risk_hint": "low", "emotion": "无奈"}

输入：1
输出：{"normalized_intent": "用户选择第一个选项", "possible_scene": "选项确认", "risk_hint": "none", "emotion": "平静"}

---

【闲聊/非燃气】

输入：今天天气怎么样
输出：{"normalized_intent": "用户询问天气，与燃气无关", "possible_scene": "闲聊", "risk_hint": "none", "emotion": "平静"}

输入：你好
输出：{"normalized_intent": "用户打招呼问好", "possible_scene": "问候", "risk_hint": "none", "emotion": "平静"}

---

重要规则：
- 用户说"炸了没"、"爆炸了吗"、"砰" → 安全确认，不是闲聊，risk_hint至少medium
- 用户说方言/口语 → 翻译成标准故障描述，保留风险判断
- 用户情绪化表达 → 提取背后的真实问题，标注情绪
- 单症状（头晕/恶心/不舒服）没有燃气味时 → risk_hint不能高于medium
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
