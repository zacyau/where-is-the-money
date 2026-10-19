import re
import codecs

from app.providers.base import fetch_text, fetch_json, ProviderError

QT_URL = "https://qt.gtimg.cn/q"
KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SMARTBOX_URL = "https://smartbox.gtimg.cn/s3/"


def _sina_num(code: str) -> str:
    return code[2:] if code[:2] in ("sh", "sz", "hk") else code


def _unescape(s: str) -> str:
    if "\\u" not in s and "\\U" not in s:
        return s
    try:
        return s.encode("ascii", "ignore").decode("unicode_escape")
    except Exception:
        return s


async def get_quote(code: str) -> dict:
    raw = await fetch_text(QT_URL, params={"q": code}, encoding="gbk")
    m = re.search(r'=["\'](.*)["\']', raw)
    body = m.group(1) if m else raw
    p = body.split("~")
    if len(p) < 7:
        raise ProviderError("行情解析失败")
    return {
        "name": p[1],
        "price": float(p[3]) if p[3] else None,
        "prev_close": float(p[4]) if p[4] else None,
        "open": float(p[5]) if p[5] else None,
        "volume": float(p[6]) if p[6] else None,
    }


async def get_kline(code: str, count: int = 60) -> list:
    r = await fetch_json(
        KLINE_URL, params={"param": f"{code},day,,,{count},qfq"}
    )
    data = (r.get("data") or {}).get(code, {})
    key = next((k for k in ("qfqday", "day") if k in data), None)
    rows = data.get(key, []) if key else []
    out = []
    for row in rows[-count:]:
        out.append(
            {
                "date": row[0],
                "open": float(row[1]),
                "close": float(row[2]),
                "high": float(row[3]),
                "low": float(row[4]),
                "volume": float(row[5]),
            }
        )
    return out


async def search(q: str) -> list:
    raw = await fetch_text(
        SMARTBOX_URL, params={"v": "2", "t": "all", "q": q}, encoding="gbk"
    )
    m = re.search(r"v_hint=\"?(.*?)\"?$", raw, re.DOTALL)
    if not m:
        return []
    items = []
    seen = set()
    for part in m.group(1).split("^"):
        f = part.split("~")
        if len(f) < 4:
            continue
        market, num, name, pinyin = f[0], f[1], _unescape(f[2]), f[3]
        if market in ("sh", "sz", "hk") and num and num not in seen:
            seen.add(num)
            items.append(
                {"code": f"{market}{num}", "name": name, "pinyin": pinyin}
            )
    return items
