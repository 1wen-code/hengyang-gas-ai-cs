import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ── DeepSeek API ──────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
ENABLE_AI_FALLBACK = bool(DEEPSEEK_API_KEY)  # 无Key时自动禁用AI

# ── Supabase 持久化存储 ──────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
ENABLE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# ── 知识库路径 ──────────────────────────────────
KB_FAQ_PATH = os.path.join(BASE_DIR, "knowledge", "faq", "faq_knowledge.csv")
KB_POLICY_PATH = os.path.join(BASE_DIR, "knowledge", "policy", "policy_knowledge.csv")
TAG_SYSTEM_PATH = os.path.join(BASE_DIR, "knowledge", "labels", "tag_system.json")
KB_TEMPLATE_PATH = os.path.join(BASE_DIR, "knowledge", "knowledge_template.xlsx")

# ── 检索配置 ─────────────────────────────────────
MATCH_THRESHOLD = 0.24

# ── Flask ─────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "hengyang-gas-ai-cs-2024")
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
