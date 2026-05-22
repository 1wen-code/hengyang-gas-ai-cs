import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── DeepSeek API ──────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-2a7b608d812d407c8a98b0de8760db7f")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
ENABLE_AI_FALLBACK = True

# ── 知识库路径 ──────────────────────────────────
KB_FAQ_PATH = os.path.join(BASE_DIR, "knowledge", "faq", "faq_knowledge.csv")
KB_POLICY_PATH = os.path.join(BASE_DIR, "knowledge", "policy", "policy_knowledge.csv")
TAG_SYSTEM_PATH = os.path.join(BASE_DIR, "knowledge", "labels", "tag_system.json")
KB_TEMPLATE_PATH = os.path.join(BASE_DIR, "knowledge", "knowledge_template.xlsx")

# ── 检索配置 ─────────────────────────────────────
MATCH_THRESHOLD = 0.15

# ── Flask ─────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "hengyang-gas-ai-cs-2024")
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
