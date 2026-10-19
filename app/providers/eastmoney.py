from app.providers.base import fetch_json, fetch_text, ProviderError

EM_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def _codes(code: str):
    num = code[2:] if code[:2] in ("sh", "sz", "hk") else code
    market = (
        "SH" if code.startswith("sh")
        else ("SZ" if code.startswith("sz") else "HK")
    )
    return num, f"{num}.{market}"


async def _em(report, columns, num, page=1, size=20, filter_str=None,
              sort_columns="REPORT_DATE"):
    if filter_str is None:
        filter_str = f'(SECURITY_CODE="{num}")'
    params = {
        "reportName": report,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": page,
        "pageSize": size,
        "source": "WEB",
        "client": "WEB",
    }
    if sort_columns:
        params["sortColumns"] = sort_columns
        params["sortTypes"] = "-1"
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
    # RPT_SEO_DETAIL 无 REPORT_DATE 列，按其排序会报错返回空
    rows = await _em("RPT_SEO_DETAIL", "ALL", num, size=100, sort_columns=None)
    total = 0.0
    for r in rows:
        v = r.get("NET_RAISE_FUNDS") or r.get("TOTAL_RAISE_FUNDS")
        if v:
            total += v
    return total


async def get_income_supp(code: str, periods: int = 16) -> dict:
    """东财利润表补充：{报告期YYYY-MM-DD: {"credit_impairment": 正值, "asset_impairment": 正值}}。

    新浪利润表部分公司缺「信用/资产减值损失」行，用东财 F10 利润表兜底。
    东财字段为收益口径（损失为负），这里统一转为正的损失金额。
    """
    num, secu = _codes(code)
    rows = await _em("RPT_F10_FINANCE_GINCOME", "ALL", num, size=periods,
                     filter_str=f'(SECUCODE="{secu}")')
    out = {}
    for r in rows:
        rd = (r.get("REPORT_DATE") or "")[:10]
        if not rd:
            continue
        item = {}
        ci = r.get("CREDIT_IMPAIRMENT_INCOME")
        ai = r.get("ASSET_IMPAIRMENT_INCOME")
        if ci is not None:
            item["credit_impairment"] = abs(ci)
        if ai is not None:
            item["asset_impairment"] = abs(ai)
        if item:
            out[rd] = item
    return out


async def get_dividend_year(code: str, year: int) -> float:
    """某自然年(按除息日)每股分红合计，税前，元/股。东财主源 + 网易兜底。

    用于股息率：取「上一个完整自然年」的全部分红，避免多次分红下
    TTM（跨年混算）或「今年至今」（不完整）导致的口径偏差。
    """
    try:
        val = await _dividend_year_em(code, year)
    except Exception:  # noqa: BLE001
        val = 0.0
    if val:
        return val
    try:
        return await _dividend_year_netease(code, year)
    except Exception:  # noqa: BLE001
        return 0.0


async def _dividend_year_em(code: str, year: int) -> float:
    num, _ = _codes(code)
    rows = await _em("RPT_SHAREBONUS_DET", "ALL", num, size=300)
    ystr = str(year)
    total = 0.0
    for r in rows:
        ex = (r.get("EX_DIVIDEND_DATE") or "")[:10]
        if not ex.startswith(ystr):
            continue
        per = r.get("PRETAX_BONUS_RMB")
        if per:
            total += per / 10.0
    return total


NETEASE_FHSP = "http://quotes.money.163.com/service/fhsp.html"


async def _dividend_year_netease(code: str, year: int) -> float:
    """网易分红送配 CSV 兜底（接口时好时坏，失败由上层吞掉）。"""
    num = code[2:] if code[:2] in ("sh", "sz") else code
    prefix = "0" if code.startswith("sh") else "1"
    csv = await fetch_text(NETEASE_FHSP, params={"code": f"{prefix}{num}"},
                           encoding="gbk")
    lines = [ln for ln in csv.strip().split("\n") if ln.strip()]
    if len(lines) < 2 or "<" in lines[0]:
        return 0.0
    header = lines[0].split(",")
    ex_i = next((i for i, h in enumerate(header) if "除权除息日" in h), None)
    per_i = next((i for i, h in enumerate(header)
                  if "股利" in h or "每股派" in h), None)
    if ex_i is None or per_i is None:
        return 0.0
    ystr = str(year)
    total = 0.0
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) <= max(ex_i, per_i):
            continue
        ex = parts[ex_i].strip()
        if not ex.startswith(ystr):
            continue
        try:
            total += float(parts[per_i])
        except ValueError:
            continue
    return total


async def get_kcfj_map(code: str, periods: int = 24) -> dict:
    """东财主要指标：{报告期YYYY-MM-DD: 扣除非经常性损益后的净利润(元)}。"""
    num, secu = _codes(code)
    rows = await _em("RPT_F10_FINANCE_MAINFINADATA", "ALL", num, size=periods,
                     filter_str=f'(SECUCODE="{secu}")')
    out = {}
    for r in rows:
        rd = (r.get("REPORT_DATE") or "")[:10]
        v = r.get("KCFJCXSYJLR")
        if rd and v is not None:
            out[rd] = float(v)
    return out
