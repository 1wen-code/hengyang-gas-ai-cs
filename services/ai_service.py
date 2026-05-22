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

# ── System Prompt ───────────────────────────────
SYSTEM_PROMPT = """## 你是谁
你是"衡阳市天然气AI客服助手"。你不是一个只会查数据库的机器人，而是一个真正理解用户、能推理、能安抚情绪的燃气客服。

## 你的工作方式
1. **先理解，后回答** — 用户表达可能不标准。"我家燃气打不开"可能意味着欠费、阀门关闭、电池没电或故障。你要主动分析可能原因，一步步引导排查。
2. **像真人一样说话** — 不生硬、不模板化、不每次重复菜单。用自然对话的方式回应。
3. **有同理心** — 用户可能生气、焦虑、害怕。先解决情绪，再解决问题。
4. **合理推理** — 知识库没覆盖时，基于燃气业务常识给出合理建议。但不能编造政策、价格、时间承诺。

## 回答优先级（严格遵循）
1. 安全 > 2. 情绪 > 3. 问题解决 > 4. 业务办理 > 5. 补充建议

## 安全铁律
涉及燃气泄漏、爆炸、火灾时，必须先说：
"请立即关闭燃气阀门、开窗通风、禁止明火和电器，撤离到室外拨打 0734-8677777"

## 情绪处理
用户生气/骂人/投诉时，先道歉安抚，再处理问题。不要直接丢业务菜单。

## 你可以做的
- 基于燃气常识合理推理（如"打不着火"可能是电池、阀门、欠费、火盖堵塞）
- 主动追问细节帮助判断
- 给出操作建议和安全提醒
- 引导用户转人工

## 你不能做的
- 编造政策、收费标准
- 承诺处理时间
- 生成危险操作指导
- 回答燃气以外的问题
- 对自杀/自伤言论继续办理业务（必须先安抚并提供 12356 热线）

## 回答字数
控制在200字以内。简洁清晰，像真人对话。
"""


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

        # 1. 无意义输入
        for p in cls.NONSENSE_PATTERNS:
            if re.match(p, q):
                return "nonsense"

        # 1.2 闲聊/问候
        for p in cls.GREETING_PATTERNS:
            if re.match(p, q):
                return "greeting"

        # 2. 身份询问
        for p in cls.IDENTITY_PATTERNS:
            if re.search(p, q):
                return "identity"

        # 3. 转人工
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

    def ask_with_rag(self, question: str, kb_contexts: list[dict],
                     history: list[dict] = None) -> str | None:
        """RAG上下文注入DeepSeek，支持多轮对话"""
        parts = []
        for i, ctx in enumerate(kb_contexts, 1):
            parts.append(
                f"【参考{i}】\n"
                f"问题：{ctx['question']}\n"
                f"答案：{ctx['answer']}\n"
                f"来源：{ctx.get('source', '')}\n"
                f"法规：{ctx.get('law', '')}（{ctx.get('law_code', '')}）"
            )
        context_text = "\n\n".join(parts) if parts else "无相关知识库内容"

        # 构建消息列表
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 加入历史对话（最近3轮）
        if history:
            for h in history[-6:]:
                messages.append(h)

        # 当前提问
        user_msg = f"""## 知识库上下文
{context_text}

## 用户提问
{question}

请基于知识库上下文回答。如上下文无相关信息，请理解用户真实意图，尝试提供最接近的业务引导，或建议拨打客服热线0734-8677777。"""

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
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            for h in history[-6:]:
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
