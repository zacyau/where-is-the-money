import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_DB = DATA_DIR / "cache.db"

REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
RATE_LIMIT = float(os.getenv("RATE_LIMIT", "3"))   # 全局每秒请求上限
RETRIES = int(os.getenv("RETRIES", "2"))
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) moneyflow/1.0",
)
PORT = int(os.getenv("PORT", "8000"))

# 缓存 TTL（秒）
TTL_QUOTE = int(os.getenv("TTL_QUOTE", "60"))
TTL_STATEMENT = int(os.getenv("TTL_STATEMENT", "21600"))   # 6h
TTL_DIVIDEND = int(os.getenv("TTL_DIVIDEND", "86400"))
TTL_SEGMENT = int(os.getenv("TTL_SEGMENT", "21600"))

WARM_COMPANIES = ["sh600519", "sh600309", "sh600900", "sz300750", "sh601318"]
