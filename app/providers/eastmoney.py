from app.providers.base import fetch_json, ProviderError

EM_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def _codes(code: str):
    num = code[2:] if code[:2] in ("sh", "sz", "hk") else code
    market = (
        "SH" if code.startswith("sh")
        else ("SZ" if code.startswith("sz") else "HK")
    )
    return num, f"{num}.{market}"


async def _em(report, columns, num, page=1, size=20):
    params = {
        "reportName": report,
        "columns": columns,
        "filter": f"(SECURITY_CODE%3D%22{num}%22)",
        "pageNumber": page,
        "pageSize": size,
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    d = await fetch_json(EM_URL, params=params)
    return (d.get("result") or {}).get("data") or []


async def get_mainop_map(code: str, periods: int = 12) -> dict:
    """返回 {报告期YYYY-MM-DD: [{name, income, ratio}]}，优先分产品(2)/分行业(1)/分地区(3)。"""
    num, _ = _codes(code)
    rows = await _em("RPT_F10_FN_MAINOP", "ALL", num, size=periods * 14)
    by_date = {}
    for r in rows:
        rd = (r.get("REPORT_DATE") or "")[:10]
        t = str(r.get("MAINOP_TYPE"))
        by_date.setdefault(rd, {}).setdefault(t, []).append(r)
    result = {}
    for rd, types in by_date.items():
        cur = None
        for t in ("2", "1", "3"):
            if t in types:
                cur = types[t]
                break
        if not cur:
            continue
        total = sum((r.get("MAIN_BUSINESS_INCOME") or 0) for r in cur) or 1
        segs = [
            {
                "name": r.get("ITEM_NAME"),
                "income": r.get("MAIN_BUSINESS_INCOME") or 0,
                "ratio": (r.get("MAIN_BUSINESS_INCOME") or 0) / total,
            }
            for r in cur
        ]
        result[rd] = segs
    return result


async def get_dividends_total(code: str) -> float:
    num, _ = _codes(code)
    rows = await _em("RPT_SHAREBONUS_DET", "ALL", num, size=300)
    total = 0.0
    for r in rows:
        per = r.get("PRETAX_BONUS_RMB")
        shares = r.get("TOTAL_SHARES")
        if per and shares:
            total += per / 10.0 * shares
    return total


async def get_refinance_total(code: str) -> float:
    num, _ = _codes(code)
    rows = await _em("RPT_SEO_DETAIL", "ALL", num, size=100)
    total = 0.0
    for r in rows:
        v = r.get("NET_RAISE_FUNDS") or r.get("TOTAL_RAISE_FUNDS")
        if v:
            total += v
    return total
