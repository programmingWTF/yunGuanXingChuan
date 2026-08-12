"""
云观星传 - 全局配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
PROMPTS_DIR = CONFIG_DIR / "prompts"

# 加载环境变量
load_dotenv(PROJECT_ROOT / ".env")

# Qwen API 配置
# Qwen API 配置（平台默认：阿里云百炼 / Token Plan）
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3.8-max")
QWEN_MODEL_FAST = os.getenv("QWEN_MODEL_FAST", "qwen3.8-max")
QWEN_MODEL_LONG = os.getenv("QWEN_MODEL_LONG", "qwen3.8-max")
QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "qwen3.7-text-embedding")
# Embedding 单独用独立端点和 Key
QWEN_EMBEDDING_BASE_URL = os.getenv("QWEN_EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_EMBEDDING_API_KEY = os.getenv("QWEN_EMBEDDING_API_KEY", QWEN_API_KEY)

# Pipeline 配置
MAX_ITERATION_ROUNDS = int(os.getenv("MAX_ITERATION_ROUNDS", "3"))
PASS_THRESHOLD = float(os.getenv("PASS_THRESHOLD", "75"))
ENABLE_AGENT_TOOLS = os.getenv("ENABLE_AGENT_TOOLS", "true").lower() == "true"  # Agent Tool Use 开关

# 认知议会配置
PARLIAMENT_MAX_ROUNDS = int(os.getenv("PARLIAMENT_MAX_ROUNDS", "5"))
PARLIAMENT_DEADLOCK_THRESHOLD = float(os.getenv("PARLIAMENT_DEADLOCK_THRESHOLD", "0.15"))
PARLIAMENT_PASS_THRESHOLD = float(os.getenv("PARLIAMENT_PASS_THRESHOLD", "0.65"))

# API 配置
API_PORT = int(os.getenv("API_PORT", "8000"))

# Tavily AI 搜索引擎
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# 阿里云百炼 WebSearch MCP（联网搜索）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_MCP_URL = "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp"

# 五维评分权重
EVALUATION_WEIGHTS = {
    "factual_accuracy": 0.30,
    "strategic_actionability": 0.25,
    "audience_fit": 0.20,
    "cultural_sensitivity": 0.15,
    "narrative_fluency": 0.10,
}

# 数据路径
SCIENCE_DIR = DATA_DIR / "science"
MEDIA_DIR = DATA_DIR / "media"
AUDIENCE_DIR = DATA_DIR / "audience_profiles"
KG_DIR = DATA_DIR / "kg"
