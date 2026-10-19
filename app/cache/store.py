import sqlite3
import time
import json
import threading
from app.config import CACHE_DB

_lock = threading.Lock()


def _conn():
    CACHE_DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(str(CACHE_DB), timeout=10)
    c.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, payload TEXT, fetched_at REAL)"
    )
    return c


def get(key):
    try:
        c = _conn()
        row = c.execute(
            "SELECT payload, fetched_at FROM cache WHERE key=?", (key,)
        ).fetchone()
        c.close()
        if not row:
            return None
        return row[0], row[1]
    except Exception:
        return None


def delete(key):
    with _lock:
        c = _conn()
        c.execute("DELETE FROM cache WHERE key=?", (key,))
        c.commit()
        c.close()


def clear_code(code: str):
    for k in (f"q:{code}", f"inc:{code}", f"bal:{code}", f"cf:{code}",
             f"seg:{code}", f"div:{code}", f"ref:{code}"):
        delete(k)


def set(key, payload):
    with _lock:
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
            (key, payload, time.time()),
        )
        c.commit()
        c.close()


async def cached(key, ttl, coro):
    """返回缓存中的 JSON；过期或缺失则调用 coro() 重新拉取并写回。"""
    raw, ts = get(key) or (None, 0)
    if raw and (time.time() - ts) < ttl:
        try:
            return json.loads(raw)
        except Exception:
            pass
    val = await coro()
    try:
        set(key, json.dumps(val, default=str, ensure_ascii=False))
    except Exception:
        pass
    return val
