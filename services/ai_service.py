"""
衡阳市天然气AI客服智能体 — DeepSeek API + RAG + 意图识别
"""
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
import re

# ── 燃气业务关键词 ──────────────────────────
GAS_KEYWORDS = [
    "开户", "报装", "新装", "安装", "开通", "燃气", "天然气", "管道气",
    "缴费", "收费", "价格", "费用", "充值", "账单", "发票", "阶梯", "气价",
    "安检", "检查", "检测", "安全", "隐患", "整改",
    "报修", "维修", "故障", "修理", "漏气", "泄漏", "打不着火",
    "停气", "供气", "气压",
    "灶具", "燃气灶", "热水器", "壁挂炉", "锅炉", "燃气表", "IC卡",
    "过户", "销户", "报停", "低保", "残疾", "优惠", "改管",
    "条例", "法规", "政策", "标准", "规范",
    "衡阳", "营业厅", "客服", "8677777", "投诉", "建议",
    "红火", "黄火", "回火", "熄火", "点火", "火焰",
    "一氧化碳", "中毒", "通风", "软管", "胶管", "波纹管", "阀门",
    "人工", "转人工", "报警器", "报警",
    # 多轮对话衔接词
    "材料", "证件", "手续", "身份证", "房产证", "户口本", "合同",
    "怎么办", "怎么弄", "流程", "步骤", "需要什么", "怎么操作",
    "去哪里", "在哪", "多少个", "多久", "多长时间",
]

# ── 明确无关关键词 ──────────────────────────
IRRELEVANT_KEYWORDS = [
    "写代码", "编程", "python", "java", "代码", "程序",
    "股票", "基金", "理财", "投资", "比特币",
    "游戏", "王者荣耀", "吃鸡", "打牌",
    "政治", "选举",
    "娱乐", "明星", "电影", "综艺",
    "数学", "计算", "方程式",
    "做饭", "菜谱", "食谱",
]

# ── 回复模板 ────────────────────────────────
REJECT_REPLY = "您好，我是衡阳市天然气AI客服助手，目前仅支持燃气业务相关咨询。"

GREETING_REPLY = """您好，我是衡阳市天然气AI客服助手，可为您提供以下服务：

- **燃气开户** — 居民/商业新装、过户、销户
- **燃气缴费** — 收费标准、线上缴费、发票查询
- **安全用气** — 用气常识、泄漏处置、设备安全
- **报修服务** — 故障报修、紧急抢修、上门维修
- **安检服务** — 入户安检预约、隐患整改
- **投诉建议** — 服务投诉、意见反馈

请问有什么可以帮您的？"""

IDENTITY_REPLY = "您好，我是衡阳市天然气AI客服助手，隶属于衡阳市天然气有限责任公司，负责提供燃气业务咨询与安全服务。如有燃气相关问题，欢迎随时向我咨询。"

REFUND_REPLY = """您好，燃气业务退款需根据办理类型审核。

**可退款业务：**
1. 重复缴费 — 同一账单支付多次
2. 未完成开户 — 缴费后未进场施工
3. 误充值 — 充错户号或金额
4. 未上门安装订单 — 已缴费但尚未安装

**请提供以下信息：**
- 用户姓名
- 手机号
- 缴费截图
- 订单编号（如有）

客服将在 **1-3 个工作日**内审核并联系您。您也可直接拨打客服热线 **0734-8677777** 加急处理。"""

# ── 情绪安抚模板 ──────────────────────────────
EMOTION_REPLY = """很抱歉让您有不好的体验。如果您遇到了燃气问题，可以告诉我具体情况，我会尽力帮助您处理。"""

EMOTION_LIGHT_REPLY = """您好，请问您遇到了什么燃气问题？我可以帮您查询或办理相关业务。"""

CHITCHAT_REPLIES = {
    "哈哈": "您好，有什么可以帮您的吗？",
    "呵呵": "您好，请问需要办理什么燃气业务？",
    "在吗": "在的，请问有什么可以帮您？",
    "今天天气": "天气不错！请问有什么燃气方面的问题需要咨询？",
    "你是谁": IDENTITY_REPLY,
}

# ── 危机干预模板 ──────────────────────────────
CRISIS_REPLY = """我注意到您现在情绪非常低落。

如果您正处于危险或有伤害自己的想法中，请立即联系家人、朋友，或拨打心理援助热线 **12356**（24小时免费）。

如果您愿意，也可以告诉我发生了什么，我会尽力陪您沟通。"""

# ── 投诉处理模板 ──────────────────────────────
COMPLAINT_REPLY = """您的问题已进入投诉处理流程。

**请提供以下信息以便加急处理：**
1. 联系电话
2. 用气地址
3. 问题描述
4. 业务编号（如有）

工作人员将在 **24小时内**联系您。您也可以直接拨打客服热线 **0734-8677777** 按0键转投诉专线。"""

BUSINESS_GUIDE_REPLY = """您好，请问您需要办理哪类燃气业务？

1. **居民开户** — 新房开通天然气
2. **商业开户** — 餐饮/工业燃气报装
3. **过户业务** — 二手房/商铺燃气过户
4. **燃气缴费** — 查询费用、线上缴费、发票
5. **上门安装** — 装表、点火、管道改造
6. **安全检查** — 预约入户安检
7. **故障报修** — 设备维修、紧急抢修

请点击上方选项，或直接描述您的需求。"""

# ── System Prompt（第一层：核心人格）─────────────
SYSTEM_PROMPT = """你是"衡阳燃气 AI 客服助手"。

你的职责：

1. 为用户提供燃气业务咨询
2. 解答燃气安全问题
3. 识别高风险燃气事件
4. 进行业务分类
5. 必要时转人工客服
6. 基于知识库进行准确回答

---

【核心规则】

1. 禁止胡乱匹配知识库

若知识库相似度不足：
禁止强行回答。

---

2. 优先理解上下文

用户后续问题默认与历史聊天相关。

必须结合：

* chat_history
* current_intent
* 用户当前场景

综合判断。

---

3. 不允许只靠关键词回答

必须理解真实语义。

例如：

"右边打不着"
属于：
"燃气灶故障"

不是：
"超出范围"。

---

4. 如果问题不明确：

主动追问。

例如：
"请问您说的是燃气灶还是热水器？"

---

5. 若问题与燃气业务无关：

礼貌说明服务范围。

不要乱回答。

---

6. 若发现高风险内容：

立即触发风险预警。

例如：

* 燃气泄漏
* 爆炸
* 闻到煤气味
* 火焰异常
* 一氧化碳
* 中毒

---

7. 回答风格：

* 专业
* 简洁
* 像真实客服
* 不机械
* 不重复
* 不说"知识库没有相关信息"

---

8. 回答优先级：

风险安全

>

业务准确性

>

用户体验

---

当前业务：
{current_intent}

历史聊天：
{chat_history}

当前问题：
{question}

---

【追问规则】

当以下情况出现时，不要给出最终答案，必须主动追问：

1. 用户问题含义模糊，有多种理解方式
   → 追问："您说的燃气不足，是指余额不够要充值，还是火变小了不够用？"

2. 缺少关键信息无法判断
   → 追问："请问是燃气灶打不着火，还是热水器不出热水？"

3. 知识库匹配度低，没有找到精确答案
   → 追问："为了更准确地帮您，请问您具体遇到了什么情况？"

4. 用户简短回复（如"右边"、"还是不行"）
   → 先复述理解："您是说你灶具右边灶头打不着火对吗？" 确认后再给方案

追问时：
- 一次只问一个问题
- 给出 2-3 个明确选项
- 不要同时给排查步骤
- 等用户回答后再继续

---

【风险状态锁定规则】

当用户在当前会话中出现以下任意高风险信息后：
- 燃气味、臭鸡蛋味、头晕/恶心、点火爆燃、回火、火焰异常
- 泄漏、听到漏气声、燃气报警器响、黑烟、一氧化碳

系统进入高风险锁定状态。

进入高风险锁定状态后：
1. 后续所有回答必须结合之前的风险信息综合判断
2. 不允许因为用户后续一句简短描述就降级为普通故障
3. 必须优先考虑安全风险
4. 必须持续提醒：通风、禁止开关电器、必要时撤离

只有用户明确表示以下内容时，才能退出高风险锁定状态：
- 已关闭燃气阀门、已检查无异味、已维修完成、已恢复正常

否则禁止降级判断。

---

【多轮记忆规则】

你必须具备连续对话能力。

必须记住：
1. 当前用户正在讨论的问题
2. 当前风险等级
3. 当前故障类型
4. 是否已进入危险状态
5. 是否正在等待用户选择选项
6. 用户上一轮提到的现象

如果用户后续输入："对"、"是的"、"有"、"没有"、"好了"、"还在"、"又响了"、"还是这样"、"1"、"2"、"第一个"
→ 必须结合上一轮语境理解，禁止脱离上下文。

用户回复数字 → 对应上一轮的选项编号。
用户说"还是不行" → 继续上一轮故障排查。

禁止：用户简短回复就丢失上下文、高危时突然变普通客服、每次都重新归类。"""


class IntentDetector:
    """意图识别器 — 对用户输入进行意图分类"""

    GREETING_PATTERNS = [
        r"^(你好|您好|hi|hello|嗨|在吗|在不在|哈哈|呵呵|嘿嘿)$",
        r"^(你好|您好|hi|hello|嗨|在吗|在不在|哈哈|呵呵|嘿嘿)[,，!！\s]*$",
        r"^(早上好|下午好|晚上好|早安|晚安)",
        r"^(请问)?(在么|在吗|在不|有人在吗)",
    ]

    IDENTITY_PATTERNS = [
        r"你是谁", r"你是什么", r"你是做什么的",
        r"你能做什么", r"你有什么用", r"你会什么",
        r"你的功能", r"介绍一下你自己", r"你叫什么",
    ]

    VAGUE_BUSINESS_PATTERNS = [
        r"怎么.*(办理|办).*业务", r"我要办.*(天然气|燃气)",
        r"我想.*(开户|装.*燃气|开通.*燃气|安装.*燃气)",
        r"(怎么办|怎么弄|怎么搞).*(天然气|燃气)",
        r"(天然气|燃气).*(怎么.*办|流程|步骤)",
        r"我要.*(开通|安装|办).*",
        r"想.*了解.*一下.*(燃气|天然气)",
        r"(打不开|用不了|不能用|没反应|没气).*(燃气|灶|热水器|火|气)",
        r"(燃气|灶|热水器).*(打不开|用不了|不能用|没反应|不工作)",
        r"(家里|我家|厨房).*(没.*气|没.*火|用不了.*气)",
    ]

    ABUSE_PATTERNS = [
        r"神经病", r"有病", r"你.*病",
        r"傻逼", r"傻叉", r"脑残", r"智障", r"sb",
        r"操", r"艹", r"靠",
    ]

    NONSENSE_PATTERNS = [
        r"^[啊哈嘻嘿嗯哦]+$", r"^[?？!！.。]+$",
        r"^\d{1,4}$", r"^[a-zA-Z]{1,4}$",
        r"^\.{2,}$", r"^[~～]+$",
    ]

    EMOTION_PATTERNS = [
        r"垃圾", r"(什么|太|真|很|好).*(差|烂|恶心|坑|骗)",
        r"(气死|气疯|气炸|恼火|愤怒|生气|火大)",
        r"(投诉|举报).*(态度|服务|工作)",
        r"(没人管|不理|不回复|敷衍|踢皮球|推卸)",
        r"(等了|拖了).*(多久|好久|几天|几个月)",
        r"(崩溃|受不了|忍不了|没法忍)",
        r"(委屈|伤心|失望|寒心|无语)",
    ]

    CRISIS_PATTERNS = [
        r"(自杀|不想活|想死|轻生|不想.*活)",
        r"(跳楼|上吊|割腕|吃药.*死)",
        r"(活着.*没.*意义|活着.*没.*意思|没有.*意义)",
        r"(撑不住|熬不住|过不去|活不下去)",
        r"(想.*结束|想.*离开.*世界|不想.*继续)",
    ]

    REFUND_PATTERNS = [
        r"退款", r"退费", r"申请退", r"退钱",
        r"取消业务", r"取消订单", r"撤销",
        r"误充值", r"充错了", r"多充了",
        r"不装了.*退", r"不想.*退",
    ]

    COMPLAINT_PATTERNS = [
        r"我要投诉", r"怎么投诉", r"投诉你们",
        r"要求赔偿", r"索赔", r"赔偿",
        r"服务态度.*差", r"态度.*恶劣",
        r"长时间.*没人", r"一直.*不处理",
    ]

    TRANSFER_PATTERNS = [
        r"转人工", r"人工客服", r"找人工", r"人工服务",
        r"我要找人", r"我要人工", r"帮我转人工",
    ]

    @classmethod
    def detect(cls, question: str) -> str:
        """
        返回意图类型：
        greeting / identity / vague_business / transfer / gas_related / irrelevant
        """
        q = question.strip().lower()

        # 0. 危机言论 — 最高优先
        for p in cls.CRISIS_PATTERNS:
            if re.search(p, q):
                return "crisis"

        # 0.3 攻击性语言 — 不争吵，轻度安抚
        for p in cls.ABUSE_PATTERNS:
            if re.search(p, q):
                return "abuse"

        # 0.5 投诉
        for p in cls.COMPLAINT_PATTERNS:
            if re.search(p, q):
                return "complaint"

        # 0.8 情绪安抚
        for p in cls.EMOTION_PATTERNS:
            if re.search(p, q):
                return "emotion"

        # 1. 闲聊/问候（必须在无意义之前，避免"哈哈"被拦截）
        for p in cls.GREETING_PATTERNS:
            if re.match(p, q):
                return "greeting"

        # 1.2 身份询问
        for p in cls.IDENTITY_PATTERNS:
            if re.search(p, q):
                return "identity"

        # 1.3 无意义输入
        for p in cls.NONSENSE_PATTERNS:
            if re.match(p, q):
                return "nonsense"

        # 2. 转人工
        for p in cls.TRANSFER_PATTERNS:
            if re.search(p, q):
                return "transfer"

        # 3.5 退款
        for p in cls.REFUND_PATTERNS:
            if re.search(p, q):
                return "refund"

        # 4. 模糊业务提问
        for p in cls.VAGUE_BUSINESS_PATTERNS:
            if re.search(p, q):
                return "vague_business"

        # 5. 明确无关
        for kw in IRRELEVANT_KEYWORDS:
            if kw in q:
                return "irrelevant"

        # 6. 燃气相关
        for kw in GAS_KEYWORDS:
            if kw in q:
                return "gas_related"

        # 7. 短输入：若含常见追问词，视为燃气相关（多轮对话场景）
        followup_kw = ["材料", "证件", "流程", "怎么办", "怎么弄", "需要什么",
                       "多少钱", "多久", "哪里", "在哪", "手续", "怎么", "什么",
                       "哪个", "还要", "然后", "再", "呢"]
        for kw in followup_kw:
            if kw in q:
                return "gas_related"

        # 8. 默认：短输入可能是闲聊/模糊咨询；明显长无关才拒绝
        if len(q) <= 15:
            return "vague_business"
        return "irrelevant"


class AIService:
    """DeepSeek API — RAG严格约束"""

    def __init__(self):
        self._client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    def _format_history(self, history: list[dict]) -> str:
        """将对话历史格式化为可读文本"""
        if not history:
            return "（无历史记录）"
        lines = []
        for h in history[-10:]:
            role = "用户" if h.get("role") == "user" else "客服"
            content = h.get("content", "")
            if len(content) > 120:
                content = content[:120] + "..."
            lines.append(f"{role}：{content}")
        return "\n".join(lines)

    def ask_with_rag(self, question: str, kb_contexts: list[dict],
                     history: list[dict] = None,
                     standard_question: str = "",
                     category: str = "",
                     match_score: float = 0.0) -> str | None:
        """RAG上下文注入DeepSeek，支持多轮对话 + 意图理解增强"""
        # 构建知识库上下文（放在 user message 中）
        parts = []
        best_score = match_score
        for i, ctx in enumerate(kb_contexts, 1):
            parts.append(
                f"【参考{i}】{ctx['question']}\n"
                f"答案：{ctx['answer']}\n"
                f"来源：{ctx.get('source', '')} | 法规：{ctx.get('law', '')}（{ctx.get('law_code', '')}）"
            )
            if ctx.get('score', 0) > best_score:
                best_score = ctx['score']
        rag_context = "\n".join(parts) if parts else "无相关知识库内容"

        # 格式化历史
        chat_history = self._format_history(history)
        cat = category or "其他"
        score_pct = f"{best_score:.0%}" if best_score > 0 else "低于阈值"

        # System Prompt：核心人格 + 规则（只填3个占位符）
        filled_prompt = SYSTEM_PROMPT.format(
            current_intent=cat,
            chat_history=chat_history,
            question=question,
        )

        messages = [{"role": "system", "content": filled_prompt}]

        # 历史消息（OpenAI 原生多轮格式）
        if history:
            for h in history[-10:]:
                messages.append(h)

        # User Message：RAG 上下文 + 当前问题
        user_msg = f"""## 知识库参考（匹配度：{score_pct}）
{rag_context}

---

## 当前问题
{question}

---

## 答案生成规则

1. 根据用户真实问题回答，优先回答最相关故障
2. 禁止发散联想 — 不要列举与当前问题无关的故障原因
3. 禁止答非所问 — 用户问什么就答什么
4. 禁止套模板 — 不要一上来就输出大量安全模板
5. 不确定时必须追问

### 严禁错误联想

用户说"火焰发飘"：
- 只能回答：火焰不稳定、风门问题、空气过大、燃烧异常
- 禁止回答：电池没电、点火针故障、阀门关闭

用户说"燃气不足"：
- 只能回答：火力小、气压低、阀门未全开、欠费、高峰期压力波动
- 禁止回答：泄漏、爆炸、中毒

### 模糊描述必须追问

如果用户描述不明确（如"冒扑"、"有问题"、"不对劲"、"那个东西响"）：
- 不允许直接下结论
- 必须先追问确认，追问时给出2-3个明确选项

### 回答优先级
1. 用户当前描述 → 2. 故障现象 → 3. 最相关知识 → 4. 安全提醒 → 5. 联系电话"""

        if best_score < 0.40:
            user_msg += """

## 注意：当前知识库匹配度较低，请追问而非直接回答，给出2-3个选项帮用户缩小范围。"""

        messages.append({"role": "user", "content": user_msg})

        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=600,
            )
            ans = resp.choices[0].message.content.strip()
            if ans and ans != REJECT_REPLY:
                return ans
            return None
        except Exception:
            return None

    def ask(self, question: str, history: list[dict] = None) -> str | None:
        """纯AI兜底（支持多轮对话）"""
        chat_history = self._format_history(history)
        filled_prompt = SYSTEM_PROMPT.format(
            current_intent="未知",
            chat_history=chat_history,
            question=question,
        )
        messages = [{"role": "system", "content": filled_prompt}]
        if history:
            for h in history[-10:]:
                messages.append(h)
        messages.append({"role": "user", "content": question})

        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )
            ans = resp.choices[0].message.content.strip()
            if ans and ans != REJECT_REPLY:
                return ans
            return None
        except Exception:
            return None


# ── 用户意图理解模块（LLM深度理解）────────────────

INTENT_UNDERSTANDING_PROMPT = """你是衡阳燃气AI客服系统中的"用户意图理解模块"。

你的任务：理解用户真实业务需求。

即使用户使用：
* 口语
* 方言
* 长句
* 情绪化表达

也必须识别真实意图。

要求：
1. 不要只看关键词 — 理解用户真正想解决的问题
2. 即使带有情绪（生气、焦虑、抱怨），也要抽出背后的业务诉求
3. 转换为一句通顺的标准业务问题
4. 输出业务分类

业务分类（只从以下选择）：
* 缴费业务 — 充值、缴费、欠费、余额、发票、账单、气价、阶梯价
* 开户业务 — 新装、开户、报装、过户、销户、改管
* 安全用气 — 漏气、泄漏、异味、报警器、通风、中毒、安检
* 燃气灶故障 — 打不着火、火焰异常、熄火、火盖堵塞、电池
* 热水器故障 — 不出热水、水温异常、热水器报错、点火失败
* 报修维修 — 设备维修、管道维修、上门维修、表具故障
* 停气问题 — 停气、气压低、断气、供气恢复
* 人工客服 — 要求转人工、投诉跟进、紧急工单查询
* 投诉建议 — 服务投诉、意见反馈、赔偿要求
* 其他 — 闲聊、问候、非燃气问题

输出格式（严格按此格式，不要多余文字）：

【真实意图】
xxx

【标准问题】
xxx

【业务分类】
xxx"""


class IntentUnderstandingService:
    """LLM 用户意图理解 — 深度语义理解，处理口语/方言/长句/情绪化表达"""

    def __init__(self, client: OpenAI):
        self._client = client

    def understand(self, question: str) -> dict:
        """
        调用 DeepSeek 深度理解用户意图。

        返回:
            {
                "real_intent": "真实意图描述",
                "standard_question": "标准业务问题",
                "category": "业务分类",
                "raw_response": "原始LLM回复"
            }
            失败时返回 None
        """
        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": INTENT_UNDERSTANDING_PROMPT},
                    {"role": "user", "content": question},
                ],
                temperature=0.1,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw, question)
        except Exception:
            return None

    def _parse(self, response: str, question: str) -> dict:
        """解析LLM的结构化输出"""
        import re

        real_intent = ""
        standard_question = ""
        category = "其他"

        m = re.search(r"【真实意图】\s*(.+?)(?=【标准问题】|$)", response, re.DOTALL)
        if m:
            real_intent = m.group(1).strip()

        m = re.search(r"【标准问题】\s*(.+?)(?=【业务分类】|$)", response, re.DOTALL)
        if m:
            standard_question = m.group(1).strip()

        m = re.search(r"【业务分类】\s*(.+?)$", response, re.DOTALL)
        if m:
            category = m.group(1).strip()

        if not real_intent:
            real_intent = question
        if not standard_question:
            standard_question = question

        return {
            "real_intent": real_intent,
            "standard_question": standard_question,
            "category": category,
            "raw_response": response,
        }


# ── 风险识别模块（LLM深度判别，独立运行）─────────

RISK_DETECTION_PROMPT = """你是燃气AI客服系统中的"风险识别模块"。

你的任务：识别用户问题中的风险等级。

风险等级：

【高危】
* 漏气
* 爆炸
* 火灾
* 中毒
* 报警器响
* 人员受伤

【中危】
* 停气
* 无法点火
* 故障
* 投诉
* 情绪激动

【低危】
普通业务咨询。

输出格式（严格按此格式，不要多余文字）：

【风险等级】
xxx

【风险原因】
xxx

【是否生成工单】
是/否

【是否转人工】
是/否"""


class RiskDetectionService:
    """LLM 风险识别 — 独立运行，深度语义判断用户问题中的安全风险等级"""

    def __init__(self, client: OpenAI):
        self._client = client

    def detect(self, question: str) -> dict:
        """
        调用 DeepSeek 识别用户问题的风险等级。

        返回:
            {
                "risk_level": "高危" | "中危" | "低危",
                "risk_reason": "风险原因说明",
                "create_ticket": True | False,
                "transfer_human": True | False,
                "raw_response": "原始LLM回复"
            }
            失败时返回 None
        """
        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": RISK_DETECTION_PROMPT},
                    {"role": "user", "content": question},
                ],
                temperature=0.0,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw)
        except Exception:
            return None

    def _parse(self, response: str) -> dict:
        """解析LLM的结构化风险输出"""
        import re

        risk_level = "低危"
        risk_reason = ""
        create_ticket = False
        transfer_human = False

        m = re.search(r"【风险等级】\s*(.+?)(?=【风险原因】|$)", response, re.DOTALL)
        if m:
            risk_level = m.group(1).strip()

        m = re.search(r"【风险原因】\s*(.+?)(?=【是否生成工单】|$)", response, re.DOTALL)
        if m:
            risk_reason = m.group(1).strip()

        m = re.search(r"【是否生成工单】\s*(.+?)(?=【是否转人工】|$)", response, re.DOTALL)
        if m:
            create_ticket = "是" in m.group(1)

        m = re.search(r"【是否转人工】\s*(.+?)$", response, re.DOTALL)
        if m:
            transfer_human = "是" in m.group(1)

        return {
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "create_ticket": create_ticket,
            "transfer_human": transfer_human,
            "raw_response": response,
        }

    def compare_with_keyword(self, question: str, keyword_result: dict) -> dict:
        """
        对比 LLM 风险识别与关键词规则的结果，返回综合评估。

        keyword_result: detect_emergency() 的返回值 {level, risk_label, ...}

        返回:
            {
                "llm_risk": LLM识别结果,
                "keyword_risk": 关键词规则结果,
                "verdict": "agree" | "llm_upgrade" | "llm_downgrade" | "llm_only",
                "final_level": 最终建议等级,
                "final_action": 最终建议动作,
            }
        """
        llm_result = self.detect(question)

        if llm_result is None:
            return {
                "llm_risk": None,
                "keyword_risk": keyword_result,
                "verdict": "keyword_only",
                "final_level": keyword_result["level"],
                "final_action": keyword_result.get("action", ""),
            }

        # 等级映射
        llm_level_map = {"高危": 3, "中危": 2, "低危": 1}
        kw_level = keyword_result["level"]
        llm_level = llm_level_map.get(llm_result["risk_level"], 1)

        if llm_level == kw_level:
            verdict = "agree"
        elif llm_level > kw_level:
            verdict = "llm_upgrade"
        else:
            verdict = "llm_downgrade"

        # 综合建议：取两者中较高的等级（安全优先）
        final_level = max(llm_level, kw_level)
        final_level_label = {3: "高危", 2: "中危", 1: "低危"}[final_level]

        return {
            "llm_risk": llm_result,
            "keyword_risk": {
                "level": kw_level,
                "risk_label": keyword_result.get("risk_label", ""),
                "matched": keyword_result.get("matched", []),
                "reason": keyword_result.get("reason", ""),
            },
            "verdict": verdict,
            "final_level": final_level,
            "final_level_label": final_level_label,
        }


# ── 工单生成模块（LLM生成，最后运行）─────────────

TICKET_GENERATION_PROMPT = """你是燃气AI客服系统中的工单生成模块。

请根据用户问题和风险等级，生成标准客服工单。

输出格式（严格按此格式，不要多余文字）：

【业务类型】
xxx

【风险等级】
xxx

【问题摘要】
xxx

【处理建议】
xxx

【是否人工介入】
是/否"""


class TicketGenerationService:
    """LLM 工单生成 — 独立运行，根据用户问题和风险结果生成标准工单"""

    def __init__(self, client: OpenAI):
        self._client = client

    def generate(self, question: str, risk_result: dict) -> dict:
        """
        调用 DeepSeek 生成标准客服工单。

        risk_result 可以是 RiskDetectionService.detect() 的返回，
        或 detect_emergency() 的返回，或 compare_with_keyword() 的返回。

        返回:
            {
                "ticket_id": "自动生成的工单编号",
                "business_type": "业务类型",
                "risk_level": "风险等级",
                "summary": "问题摘要",
                "suggestion": "处理建议",
                "human_intervention": True | False,
                "raw_response": "原始LLM回复"
            }
            失败时返回 None
        """
        # 将风险结果序列化为可读文本
        risk_text = self._format_risk(risk_result)

        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": TICKET_GENERATION_PROMPT},
                    {"role": "user", "content": f"用户问题：{question}\n\n风险结果：{risk_text}"},
                ],
                temperature=0.1,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw)
        except Exception:
            return None

    def _format_risk(self, risk_result: dict) -> str:
        """将风险结果格式化为文本"""
        parts = []

        # 处理不同的 risk_result 格式
        if "risk_level" in risk_result:
            parts.append(f"风险等级：{risk_result['risk_level']}")
        elif "level" in risk_result:
            level_map = {3: "高危", 2: "中危", 1: "低危"}
            parts.append(f"风险等级：{level_map.get(risk_result['level'], '未知')}")

        if "risk_reason" in risk_result:
            parts.append(f"风险原因：{risk_result['risk_reason']}")
        elif "reason" in risk_result:
            parts.append(f"风险原因：{risk_result['reason']}")

        if "risk_label" in risk_result:
            parts.append(f"风险标签：{risk_result['risk_label']}")

        if "matched" in risk_result and risk_result["matched"]:
            parts.append(f"命中关键词：{', '.join(risk_result['matched'])}")

        if "final_level_label" in risk_result:
            parts.append(f"综合等级：{risk_result['final_level_label']}")

        if "verdict" in risk_result:
            parts.append(f"判定方式：{risk_result['verdict']}")

        return "\n".join(parts) if parts else str(risk_result)

    def _parse(self, response: str) -> dict:
        """解析LLM的结构化工单输出"""
        import re, uuid
        from datetime import datetime

        ticket_id = f"TK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # 防御：如果 LLM 自行输出了【工单编号】，先剥离（含同行内容和尾部空白）
        cleaned = re.sub(r"【工单编号】[^\n]*\s*", "", response)

        def _extract(text: str, tag: str, next_tag: str = "") -> str:
            if next_tag:
                m = re.search(rf"【{tag}】\s*(.+?)\s*\n【{next_tag}】", text, re.DOTALL)
            else:
                m = re.search(rf"【{tag}】\s*(.+?)$", text, re.DOTALL)
            return m.group(1).strip() if m else ""

        business_type = _extract(cleaned, "业务类型", "风险等级")
        risk_level = _extract(cleaned, "风险等级", "问题摘要")
        summary = _extract(cleaned, "问题摘要", "处理建议")
        suggestion = _extract(cleaned, "处理建议", "是否人工介入")
        hi = _extract(cleaned, "是否人工介入")
        human_intervention = "是" in hi

        return {
            "ticket_id": ticket_id,
            "business_type": business_type,
            "risk_level": risk_level,
            "summary": summary,
            "suggestion": suggestion,
            "human_intervention": human_intervention,
            "raw_response": response,
        }


# ── 第二层：意图分类器（检索前 JSON 分类）─────────

INTENT_CLASSIFIER_PROMPT = """你是燃气AI客服系统的"检索前分类器"。

请判断用户问题属于哪个业务类型。

输出 JSON（严格只输出 JSON，不要多余文字）：

{{
"is_gas_related": true,
"need_rag": true,
"category": "",
"risk_level": "",
"confidence": 0.95
}}

---

分类范围（category 只从以下选择）：

* 燃气缴费
* 开户安装
* 灶具维修
* 热水器故障
* 燃气泄漏
* 安全用气
* 投诉建议
* 人工客服
* 闲聊无关

---

规则：

1. 必须结合历史上下文。

2. 用户简短回复时：
   要自动补全语义。

例如：

历史：
"灶打不着火"

当前：
"右边"

应理解为：
"右边灶头打不着火"。

---

3. 非燃气问题：

禁止进入知识库检索。
is_gas_related 设为 false
need_rag 设为 false

---

4. 若无法确定：

category 返回：
"需要追问"

---

历史聊天：
{chat_history}

当前问题：
{question}

---

【多轮记忆规则】

你必须具备连续对话能力。

必须记住：
1. 当前用户正在讨论的问题
2. 当前风险等级
3. 当前故障类型
4. 是否已进入危险状态
5. 是否正在等待用户选择选项
6. 用户上一轮提到的现象

如果用户后续输入：对、是的、有、没有、好了、还在、又响了、还是这样、1、2、第一个
→ 必须结合上一轮语境理解，禁止脱离上下文。

用户回复数字 → 对应上一轮的选项编号。
用户说还是不行 → 继续上一轮故障排查。

【风险记忆】
已判断存在燃气泄漏/回火/爆燃/一氧化碳/火焰异常时，
→ 后续必须保持风险状态，除非用户明确说已关闭/已维修/已恢复。

禁止：用户简短回复就丢失上下文、高危时突然变普通客服、每次都重新归类。"""


class IntentClassifierService:
    """检索前 JSON 分类器 — 判断业务类型 + 是否需要RAG"""

    def __init__(self, client: OpenAI):
        self._client = client

    def classify(self, question: str, chat_history: str = "") -> dict:
        """
        调用 DeepSeek 进行检索前分类。

        返回:
            {
                "is_gas_related": bool,
                "need_rag": bool,
                "category": str,
                "risk_level": str,
                "confidence": float,
            }
            失败时返回默认值
        """
        prompt = INTENT_CLASSIFIER_PROMPT.format(
            chat_history=chat_history or "（无历史记录）",
            question=question,
        )
        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=150,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw)
        except Exception:
            return self._default()

    def _parse(self, raw: str) -> dict:
        """解析 JSON 输出（容错 Markdown 代码块包裹）"""
        import json, re
        # 剥离可能的 ```json ... ``` 包裹
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            raw = m.group(0)
        try:
            data = json.loads(raw)
            return {
                "is_gas_related": data.get("is_gas_related", True),
                "need_rag": data.get("need_rag", True),
                "category": data.get("category", ""),
                "risk_level": data.get("risk_level", ""),
                "confidence": float(data.get("confidence", 0.5)),
            }
        except (json.JSONDecodeError, ValueError):
            return self._default()

    def _default(self) -> dict:
        return {
            "is_gas_related": True,
            "need_rag": True,
            "category": "",
            "risk_level": "",
            "confidence": 0.0,
        }


# ── 情绪识别模块（第三层：上下文后、风险前）─────

EMOTION_DETECTION_PROMPT = """你是燃气AI客服系统的"情绪识别模块"。

分析用户当前消息中的情绪状态。

输出 JSON（只输出 JSON）：

{{
"emotion": "",
"intensity": 0,
"need_calm_first": false,
"tone_suggestion": ""
}}

情绪类型（emotion）：
* calm — 平静、正常咨询
* anxious — 焦虑、担心（如闻到煤气味、打不着火）
* angry — 愤怒、不满（如投诉、骂人）
* frustrated — 沮丧、无奈（如多次尝试失败）
* urgent — 紧急、恐慌（如泄漏、爆炸）
* sad — 悲伤、低落
* confused — 困惑、不确定

强度（intensity）：0-10
* 0-3: 轻微
* 4-6: 中等
* 7-10: 强烈

need_calm_first：
* true — 需要先安抚情绪，再处理问题
* false — 可以直接回答

tone_suggestion：
* 如"先道歉"、"表达理解"、"快速给出方案"、"安抚+引导"、"正常回答"

---

历史聊天：
{chat_history}

当前消息：
{question}"""


class EmotionDetectionService:
    """情绪识别 — 分析用户情绪，指导客服话术"""

    def __init__(self, client: OpenAI):
        self._client = client

    def detect(self, question: str, chat_history: str = "") -> dict:
        try:
            prompt = EMOTION_DETECTION_PROMPT.format(
                chat_history=chat_history or "（无历史记录）",
                question=question,
            )
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.0,
                max_tokens=150,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw)
        except Exception:
            return self._default()

    def _parse(self, raw: str) -> dict:
        import json, re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            raw = m.group(0)
        try:
            data = json.loads(raw)
            return {
                "emotion": data.get("emotion", "calm"),
                "intensity": int(data.get("intensity", 0)),
                "need_calm_first": data.get("need_calm_first", False),
                "tone_suggestion": data.get("tone_suggestion", "正常回答"),
            }
        except (json.JSONDecodeError, ValueError):
            return self._default()

    def _default(self) -> dict:
        return {
            "emotion": "calm",
            "intensity": 0,
            "need_calm_first": False,
            "tone_suggestion": "正常回答",
        }


# ── 模糊语义拦截模块（答案生成前检查）─────────

FUZZY_DETECTION_PROMPT = """你是燃气AI客服系统的"模糊语义识别模块"。

判断用户描述是否过于模糊，无法直接给出准确答案。

输出 JSON（只输出 JSON）：

{{
"is_fuzzy": false,
"reason": "",
"suggested_question": ""
}}

---

以下情况属于模糊描述（is_fuzzy = true）：

* 方言/口语/错别字/非标准表达
* 只描述了"有问题"、"不对劲"、"怪怪的"但没有具体现象
* 无法确定具体设备和故障类型

以下词语属于高模糊风险：
冒扑、怪怪的、不对劲、有问题、不正常、发飘、哒哒响、怪味、有点冲、火不稳、怪声音、没劲、时好时坏

---

规则：

1. 如果用户描述模糊 → is_fuzzy = true，reason 说明哪里模糊，suggested_question 给出追问话术
2. 如果用户描述清晰具体 → is_fuzzy = false
3. 模糊描述禁止直接给解决方案，必须先追问确认现象

---

当前问题：
{question}

---

【多轮记忆规则】

你必须具备连续对话能力。

必须记住：
1. 当前用户正在讨论的问题
2. 当前风险等级
3. 当前故障类型
4. 是否已进入危险状态
5. 是否正在等待用户选择选项
6. 用户上一轮提到的现象

如果用户后续输入：对、是的、有、没有、好了、还在、又响了、还是这样、1、2、第一个
→ 必须结合上一轮语境理解，禁止脱离上下文。

用户回复数字 → 对应上一轮的选项编号。
用户说还是不行 → 继续上一轮故障排查。

【风险记忆】
已判断存在燃气泄漏/回火/爆燃/一氧化碳/火焰异常时，
→ 后续必须保持风险状态，除非用户明确说已关闭/已维修/已恢复。

禁止：用户简短回复就丢失上下文、高危时突然变普通客服、每次都重新归类。"""


class FuzzyDetectionService:
    """模糊语义识别 — 检测用户描述是否过于模糊，强制追问"""

    def __init__(self, client: OpenAI):
        self._client = client

    def detect(self, question: str) -> dict:
        try:
            prompt = FUZZY_DETECTION_PROMPT.format(question=question)
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.0,
                max_tokens=150,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw)
        except Exception:
            return self._default()

    def _parse(self, raw: str) -> dict:
        import json, re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m: raw = m.group(0)
        try:
            data = json.loads(raw)
            return {
                "is_fuzzy": data.get("is_fuzzy", False),
                "reason": data.get("reason", ""),
                "suggested_question": data.get("suggested_question", ""),
            }
        except:
            return self._default()

    def _default(self) -> dict:
        return {"is_fuzzy": False, "reason": "", "suggested_question": ""}


# ── 会话状态跟踪模块（维护对话状态机）─────────

SESSION_STATE_PROMPT = """你是燃气AI客服的"会话状态管理模块"。

维护用户当前会话状态。

可用状态：

1. normal（普通咨询）
2. troubleshooting（故障排查）
3. dangerous（高危危险）
4. emergency（紧急事故）
5. resolved（风险解除）
6. human_transfer（转人工）

状态切换规则：

- 出现：漏气、臭鸡蛋味、头晕、砰、爆燃、火焰异常 → dangerous
- 出现：晕倒、昏迷、多人不适、着火 → emergency
- 用户说：好了、没事了、恢复了、已经处理 → resolved

特别规则：

如果上一轮状态是 dangerous 或 emergency，
用户说"没事了""好了"等结束语时：

禁止直接退出上下文。

应该：
1. 先确认安全
2. 提醒继续观察
3. 提醒异常继续联系
4. 再礼貌结束

---

当前会话状态：{current_state}
上一轮风险等级：{risk_level}
当前用户消息：{question}

输出 JSON：
{{
"new_state": "",
"state_reason": "",
"should_confirm_safety": false,
"safety_reminder": ""
}}"""


class SessionStateService:
    """会话状态机 — 跟踪对话状态，防止高危状态被意外重置"""

    def __init__(self, client: OpenAI):
        self._client = client

    def evaluate(self, question: str, current_state: str, risk_level: str) -> dict:
        try:
            prompt = SESSION_STATE_PROMPT.format(
                current_state=current_state,
                risk_level=risk_level,
                question=question,
            )
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse(raw)
        except Exception:
            return self._fallback(question, current_state, risk_level)

    def _parse(self, raw: str) -> dict:
        import json, re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m: raw = m.group(0)
        try:
            data = json.loads(raw)
            return {
                "new_state": data.get("new_state", "normal"),
                "state_reason": data.get("state_reason", ""),
                "should_confirm_safety": data.get("should_confirm_safety", False),
                "safety_reminder": data.get("safety_reminder", ""),
            }
        except:
            return {"new_state": "normal", "state_reason": "", "should_confirm_safety": False, "safety_reminder": ""}

    def _fallback(self, question: str, current_state: str, risk_level: str) -> dict:
        """本地规则兜底：不需要LLM也能判断基本状态切换"""
        new_state = current_state

        # 危险关键词 → emergency/dangerous
        emergency_kw = ["晕倒", "昏迷", "着火", "没有呼吸", "心跳"]
        danger_kw = ["漏气", "泄漏", "臭鸡蛋", "头晕", "砰", "爆燃", "火焰异常", "煤气味"]

        if any(kw in question for kw in emergency_kw):
            new_state = "emergency"
        elif any(kw in question for kw in danger_kw):
            new_state = "dangerous"
        elif current_state in ("dangerous", "emergency"):
            # 高危状态下，用户说"好了/没事了" → resolved
            resolve_kw = ["好了", "没事了", "恢复了", "已经处理", "解决了", "没了"]
            if any(kw in question for kw in resolve_kw):
                new_state = "resolved"
                return {
                    "new_state": "resolved",
                    "state_reason": "用户表示风险已缓解",
                    "should_confirm_safety": True,
                    "safety_reminder": "请继续保持通风，暂时不要再次点火。如有异常请立即联系抢修。",
                }

        return {"new_state": new_state, "state_reason": "", "should_confirm_safety": False, "safety_reminder": ""}
