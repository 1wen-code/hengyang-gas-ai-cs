"""
纯规则检测器 — 不调 AI，只关键词+正则
"""
import re

# ── smalltalk / 取消危险（最高优先）───────────
CANCEL_DANGER = [
    "骗你的", "开玩笑", "逗你", "测试的", "试一下",
    "闹着玩", "假的", "说着玩", "吓你的",
    "没事了", "没事", "好了", "处理好了", "解决了",
    "修好了", "正常了", "已处理", "已解决", "搞定了",
    "没味了", "没闻到", "关好了", "通风了", "不响了",
]

SMALLTALK_WORDS = [
    "哈哈", "呵呵", "嘿嘿", "嘻嘻",
    "你好", "您好", "hi", "hello", "嗨",
    "在吗", "在不在", "在不",
    "谢谢", "感谢", "多谢",
    "再见", "拜拜", "bye",
    "晚安", "早安", "早上好", "下午好", "晚上好",
    "你是谁", "你叫什么", "你能做什么",
    "无聊", "聊天",
    "今天天气", "天气怎么样",
    "吃饭了", "吃了吗",
    "测试", "test",
]


def detect_smalltalk(msg: str) -> bool:
    m = msg.strip()
    for kw in CANCEL_DANGER:
        if kw in m:
            return True
    for kw in SMALLTALK_WORDS:
        if kw in m.lower():
            return True
    if len(m) <= 2:
        return True
    return False


# ── danger（只检测真实危险）────────────────────

DANGER_PATTERNS = [
    r"漏气", r"泄漏", r"漏煤气", r"漏燃气",
    r"闻到.*燃气味", r"闻到.*煤气味", r"燃气味", r"煤气味", r"臭鸡蛋",
    r"着火", r"起火", r"火灾", r"明火", r"烧起来",
    r"爆炸", r"爆燃", r"炸了",
    r"中毒", r"一氧化碳",
    r"昏迷", r"没有呼吸", r"烧伤",
    r"管子.*破", r"管道.*裂", r"阀门.*关不上",
]

SAFE_CONTEXT = [
    r"打不着火", r"打不燃", r"点不着", r"不打火",
    r"没热水", r"不出热水", r"火焰.*小", r"火.*小",
    r"电池", r"没电", r"欠费", r"充值",
    r"开户", r"缴费", r"过户", r"销户",
    r"材料", r"证件", r"多少钱", r"收费标准",
    r"流程", r"步骤", r"怎么办", r"怎么弄",
    r"火盖.*堵", r"火孔.*堵",
    r"怎么.*修", r"排查", r"什么原因",
]


def detect_danger(msg: str) -> bool:
    for p in SAFE_CONTEXT:
        if re.search(p, msg):
            return False
    for p in DANGER_PATTERNS:
        if re.search(p, msg):
            return True
    return False


def detect_cancel_danger(msg: str) -> bool:
    for kw in CANCEL_DANGER:
        if kw in msg:
            return True
    return False


# ── human ─────────────────────────────────────

HUMAN_WORDS = [
    "转人工", "人工客服", "人工服务",
    "找人工", "我要人工", "帮我转人工",
    "联系人工", "接人工",
    "我要找.*人", "能不能.*人工",
]


def detect_human(msg: str) -> bool:
    for p in HUMAN_WORDS:
        if re.search(p, msg):
            return True
    return False


# ── faq ───────────────────────────────────────

FAQ_WORDS = [
    "开户", "报装", "新装", "安装", "开通",
    "缴费", "充值", "交费", "欠费", "账单",
    "过户", "销户", "报停", "改管", "移表",
    "多少钱", "收费", "价格", "费用", "阶梯", "气价",
    "材料", "证件", "需要什么", "准备什么",
    "身份证", "房产证", "户口本",
    "维修", "报修", "上门", "营业厅",
    "在哪里", "去哪里", "地址", "网点",
    "多久", "多长时间", "几个工作日",
    "安检", "停气", "恢复供气",
    "低保", "优惠", "发票",
    "灶", "热水器", "壁挂炉", "燃气表", "IC卡",
    "报警器", "软管", "胶管", "波纹管",
    "条例", "法规", "政策", "规定",
    "打不着火", "打不燃", "点不着", "不出热水",
    "红火", "黄火", "熄火", "火焰",
]


def detect_faq(msg: str) -> bool:
    for kw in FAQ_WORDS:
        if re.search(kw, msg):
            return True
    return False
