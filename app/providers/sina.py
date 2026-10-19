from app.providers.base import fetch_text, ProviderError

BASE = "https://money.finance.sina.com.cn/corp/go.php"
KINDS = {
    "income": "vDOWN_ProfitStatement",
    "balance": "vDOWN_BalanceSheet",
    "cashflow": "vDOWN_CashFlow",
}


def _sina_num(code: str) -> str:
    return code[2:] if code[:2] in ("sh", "sz", "hk") else code


async def get_statement(code: str, kind: str) -> dict:
    """返回 {科目名: {报告期YYYYMMDD: 数值|None}}。"""
    url = (
        f"{BASE}/{KINDS[kind]}/displaytype/4/stockid/"
        f"{_sina_num(code)}/ctrl/all.phtml"
    )
    text = await fetch_text(url, encoding="gb18030")
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) < 3:
        raise ProviderError(f"新浪{kind}数据为空")
    periods = [
        p.strip()
        for p in lines[0].split("\t")[1:]
        if p.strip() and p.strip() != "19700101"
    ]
    out = {}
    for ln in lines[2:]:
        cols = ln.split("\t")
        name = cols[0].strip()
        if not name or name == "单位":
            continue
        vals = cols[1 : 1 + len(periods)]
        row = {}
        for p, v in zip(periods, vals):
            v = v.strip().replace(",", "")
            if v in ("", "--", "-", "false"):
                row[p] = None
            else:
                try:
                    row[p] = float(v)
                except ValueError:
                    row[p] = None
        if any(x is not None for x in row.values()):
            out[name] = row
    return out
