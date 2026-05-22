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
    "天气", "下雨", "温度", "台风",
    "游戏", "王者荣耀", "吃鸡", "打牌",
    "政治", "选举", "政府",
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
SYSTEM_PROMPT = """## 身份与职责
你是"衡阳市天然气AI客服助手"，隶属于衡阳市天然气有限责任公司。

你的职责：
1. 理解用户的燃气业务问题，识别其真实意图
2. 优先依据知识库内容回答，可将知识库内容重新组织为自然语言
3. 知识库未精准命中时，尝试理解用户需求，提供最接近的业务引导
4. 支持多轮对话，能根据上下文进行追问和确认
5. 对模糊问题主动引导用户明确需求

## 服务范围（仅限以下8类）
1. 业务申请 — 开户、过户、销户、改管、工商业报装
2. 气费管理 — 收费标准、缴费方式、账单查询、发票、欠费处理、费用争议
3. 上门服务 — 安检、报修、抢修、点火、隐患整改
4. 安全用气 — 用气常识、设备安全、泄漏处置、中毒预防、设施保护
5. 投诉建议 — 服务投诉、施工投诉、意见建议
6. 政策咨询 — 法律法规、地方政策、行业标准、价格政策
7. 系统操作 — 账号管理、在线缴费、功能查询
8. 转人工 — 超出范围、无法解答、用户要求

## 必须遵守的规则
1. 允许将知识库内容重新组织成自然语言，但不允许编造政策、法规、收费标准
2. 允许进行业务引导和多轮对话，但不允许脱离燃气业务范围
3. 禁止回答编程、代码、金融、股票、政治、娱乐、游戏等无关问题
4. 没有知识依据时，必须建议转人工或提供业务引导，不得凭空编造
5. 涉及安全事故（泄漏、爆炸、中毒等），必须优先引导用户执行应急处置并转人工
6. 涉及具体业务流程时，合理引用法规依据

## 回答风格
1. 企业客服风格：正式、专业、简洁、得体
2. 称呼用户为"您"，自称"我公司"或"我们"
3. 涉及安全问题时，必须强调安全注意事项
4. 回答控制在300字以内
5. 尽量引用具体法规依据（如《城镇燃气管理条例》）
6. 涉及业务流程时，列出清晰步骤
7. 不确定时主动建议用户拨打客服热线 0734-8677777 核实
"""


class IntentDetector:
    """意图识别器 — 对用户输入进行意图分类"""

    GREETING_PATTERNS = [
        r"^(你好|您好|hi|hello|嗨|在吗|在不在)$",
        r"^(你好|您好|hi|hello|嗨|在吗|在不在)[,，!！\s]*$",
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
    ]

    REFUND_PATTERNS = [
        r"退款", r"退费", r"申请退", r"退钱",
        r"取消业务", r"取消订单", r"撤销",
        r"误充值", r"充错了", r"多充了",
        r"不装了.*退", r"不想.*退",
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

        # 1. 问候
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

        # 8. 默认：短输入可能是模糊咨询，长输入可能是无关
        if len(q) <= 5:
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
