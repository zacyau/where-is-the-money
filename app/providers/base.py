import asyncio
import logging
import httpx

from app.config import REQUEST_TIMEOUT, RATE_LIMIT, RETRIES, USER_AGENT

logger = logging.getLogger("moneyflow.provider")

_client: httpx.AsyncClient | None = None
_limiter = asyncio.Semaphore(1)
_last_ts = 0.0


class ProviderError(Exception):
    pass


def get_client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    return _client


async def aclose():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _throttle():
    global _last_ts
    async with _limiter:
        loop = asyncio.get_event_loop()
        now = loop.time()
        gap = 1.0 / RATE_LIMIT
        wait = gap - (now - _last_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_ts = loop.time()


async def fetch_bytes(url, params=None, headers=None):
    await _throttle()
    client = get_client()
    last = None
    for attempt in range(RETRIES + 1):
        try:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            logger.warning("fetch fail %s attempt %d: %s", url, attempt, e)
            await asyncio.sleep(1.2 ** attempt)
    raise ProviderError(f"请求失败 {url}: {last}")


async def fetch_text(url, params=None, encoding=None, headers=None):
    r = await fetch_bytes(url, params, headers)
    if encoding:
        return r.content.decode(encoding, errors="replace")
    return r.text


async def fetch_json(url, params=None, headers=None):
    r = await fetch_bytes(url, params, headers)
    try:
        return r.json()
    except Exception as e:  # noqa: BLE001
        raise ProviderError(f"JSON 解析失败 {url}: {e}")
