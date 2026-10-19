import datetime
import re
from dataclasses import dataclass, field
from typing import Optional

from app.providers import sina, eastmoney, tencent
from app.cache.store import cached
from app.config import TTL_STATEMENT, TTL_SEGMENT, TTL_DIVIDEND
from app.models.schemas import (
    PeriodInfo, SegmentItem, IncomeStmt, BalanceStmt, CashFlowStmt, Snapshot,
)

# 科目名规范化：新浪不同行业报表的科目带「一、二、」序号前缀，
# 且冒号全角/半角混用（如「一、营业收入」「减:所得税费用」）。
_PREFIX = re.compile(r"^[一二三四五六七八九十]+[、.．]\s*")


def _norm_rows(raw: dict) -> dict:
    out = {}
    for name, row in raw.items():
        out.setdefault(name, row)
        variants = {_PREFIX.sub("", name).strip(),
                    name.replace("：", ":"), name.replace(":", "：")}
        for v in list(variants):
            out.setdefault(v, row)
            out.setdefault(_PREFIX.sub("", v).strip(), row)
    return out


@dataclass
class RawData:
    code: str
    name: str
    periods: list = field(default_factory=list)        # List[PeriodInfo]
    income_raw: dict = field(default_factory=dict)      # 科目 -> {日期: 值}
    balance_raw: dict = field(default_factory=dict)
    cashflow_raw: dict = field(default_factory=dict)
    segments: dict = field(default_factory=dict)         # 日期 -> [SegmentItem]
    dividends_total: float = 0.0
    refinance_total: float = 0.0
    price: Optional[float] = None                       # 现价（股息率用）
    dividend_ttm: Optional[float] = None                # 近12个月每股分红(税前)
    kcfj_raw: dict = field(default_factory=dict)         # 日期 -> 扣非净利润


INCOME_MAP = {
    "revenue": ["营业收入", "营业总收入"],
    "cost": ["营业成本", "营业支出"],
    "tax_surcharge": ["税金及附加", "营业税金及附加"],
    "selling_expense": ["销售费用"],
    "admin_expense": ["管理费用"],
    "rnd_expense": ["研发费用"],
    "finance_expense": ["财务费用"],
    "invest_income": ["投资收益"],
    "fair_value_change": ["公允价值变动收益"],
    "other_income": ["其他收益"],
    "asset_disposal_income": ["资产处置收益"],
    "credit_impairment": ["信用减值损失"],
    "asset_impairment": ["资产减值损失"],
    "operating_profit": ["营业利润", "三、营业利润"],
    "nonbiz_income": ["营业外收入", "加:营业外收入"],
    "nonbiz_expense": ["营业外支出", "减：营业外支出"],
    "total_profit": ["利润总额", "四、利润总额"],
    "income_tax": ["所得税费用", "减：所得税费用"],
    "net_profit": ["净利润", "五、净利润"],
    "parent_net_profit": ["归属于母公司股东的净利润", "归属于母公司所有者的净利润"],
    "minority_interest": ["少数股东损益"],
}

BALANCE_MAP = {
    "total_assets": ["资产总计", "资产合计"],
    "total_liab": ["负债合计"],
    "parent_equity": ["归属于母公司股东权益合计", "归属于母公司所有者权益合计"],
    "accounts_receivable": ["应收账款", "应收票据及应收账款"],
    "inventory": ["存货"],
    "short_loan": ["短期借款"],
    "noncurrent_liab_1y": ["一年内到期的非流动负债"],
    "long_loan": ["长期借款"],
    "bond_payable": ["应付债券"],
    "lease_liab": ["租赁负债"],
    "cash": ["货币资金"],
}

CASHFLOW_MAP = {
    "sales_cash": ["销售商品、提供劳务收到的现金"],
    "operating_net": ["经营活动产生的现金流量净额"],
}


def make_period(yyyymmdd: str) -> PeriodInfo:
    y = int(yyyymmdd[:4]); m = int(yyyymmdd[4:6]); d = int(yyyymmdd[6:8])
    if m == 3:
        t, lab = "Q1", "一季报"
    elif m == 6:
        t, lab = "H1", "中报"
    elif m == 9:
        t, lab = "Q3", "三季报"
    else:
        t, lab = "Y", "年报"
    key = f"{y}{t}"
    start = datetime.date(y, 1, 1)
    end = datetime.date(y, m, d)
    days = (end - start).days + 1
    return PeriodInfo(
        key=key, report_date=f"{y}-{m:02d}-{d:02d}",
        label=f"{y}{lab}", days=days, year=y, month=m,
    )


def _val(raw: dict, date: str, names: list):
    for n in names:
        row = raw.get(n)
        if row and date in row and row[date] is not None:
            return row[date]
    return None


def _build_income(raw: dict, date: str) -> IncomeStmt:
    return IncomeStmt(
        **{k: (_val(raw, date, v) or 0.0) for k, v in INCOME_MAP.items()}
    )


def _build_balance(raw: dict, date: str) -> BalanceStmt:
    return BalanceStmt(
        **{k: (_val(raw, date, v) or 0.0) for k, v in BALANCE_MAP.items()}
    )


def _build_cashflow(raw: dict, date: str) -> CashFlowStmt:
    return CashFlowStmt(
        **{k: (_val(raw, date, v) or 0.0) for k, v in CASHFLOW_MAP.items()}
    )


def _yearend(date: str, year: int) -> Optional[str]:
    cand = f"{year - 1}1231"
    return cand if cand in date else None


def build_snapshot(rd: RawData, period_key: str) -> Optional[Snapshot]:
    period = next((p for p in rd.periods if p.key == period_key), None)
    if not period:
        return None
    date = period.report_date.replace("-", "")
    inc = _build_income(rd.income_raw, date)
    bal = _build_balance(rd.balance_raw, date)
    cf = _build_cashflow(rd.cashflow_raw, date)
    segs = rd.segments.get(period.report_date, [])
    prior_date = _yearend(date, period.year)
    prior_balance = _build_balance(rd.balance_raw, prior_date) if prior_date else None
    prior_income = _build_income(rd.income_raw, prior_date) if prior_date else None
    return Snapshot(
        code=rd.code, name=rd.name, period=period,
        income=inc, balance=bal, cashflow=cf,
        segments=segs, prior_balance=prior_balance, prior_income=prior_income,
    )


async def collect(code: str) -> RawData:
    quote = await cached(f"q:{code}", 60, lambda: tencent.get_quote(code))
    inc_raw = await cached(f"inc:{code}", TTL_STATEMENT,
                           lambda: sina.get_statement(code, "income"))
    bal_raw = await cached(f"bal:{code}", TTL_STATEMENT,
                           lambda: sina.get_statement(code, "balance"))
    cf_raw = await cached(f"cf:{code}", TTL_STATEMENT,
                          lambda: sina.get_statement(code, "cashflow"))
    inc_raw = _norm_rows(inc_raw)
    bal_raw = _norm_rows(bal_raw)
    cf_raw = _norm_rows(cf_raw)
    seg_map_raw = await cached(f"seg:{code}", TTL_SEGMENT,
                               lambda: eastmoney.get_mainop_map(code))

    # 报告期列表（来自利润表营收行，降序；缺失时取日期最多的科目行）
    rev_row = inc_raw.get("营业收入") or inc_raw.get("营业总收入") or {}
    dates = sorted(
        (d for d in rev_row if rev_row.get(d) is not None),
        reverse=True,
    )
    if not dates:
        best_row, best_n = None, 0
        for row in inc_raw.values():
            n = sum(1 for v in row.values() if v is not None)
            if n > best_n:
                best_row, best_n = row, n
        if best_row:
            dates = sorted(
                (d for d in best_row if best_row.get(d) is not None),
                reverse=True,
            )
    periods = [make_period(d) for d in dates]

    # 构建 segments 并计算同比
    sorted_dates = sorted(seg_map_raw.keys(), reverse=True)
    segments = {}
    prev_by_name = {}
    for d in sorted_dates:
        cur = seg_map_raw[d]
        total = sum(s["income"] for s in cur) or 1
        out = []
        for s in sorted(cur, key=lambda x: -x["income"]):
            yoy = None
            if s["name"] in prev_by_name and prev_by_name[s["name"]]:
                yoy = (s["income"] - prev_by_name[s["name"]]) / prev_by_name[s["name"]] * 100
            out.append(SegmentItem(
                name=s["name"], income=s["income"],
                ratio=s["income"] / total, yoy=yoy,
            ))
            prev_by_name[s["name"]] = s["income"]
        segments[d] = out

    div = await cached(f"div:{code}", TTL_DIVIDEND,
                       lambda: eastmoney.get_dividends_total(code))
    ref = await cached(f"ref:{code}", TTL_DIVIDEND,
                       lambda: eastmoney.get_refinance_total(code))
    supp = await cached(f"in supp:{code}", TTL_STATEMENT,
                        lambda: eastmoney.get_income_supp(code))
    div_ttm = await cached(f"divttm:{code}", TTL_DIVIDEND,
                           lambda: eastmoney.get_dividend_ttm(code))
    kcfj = await cached(f"kcfj:{code}", TTL_STATEMENT,
                        lambda: eastmoney.get_kcfj_map(code))

    # 东财减值明细兜底：新浪缺行或某期值为空/0 时逐期补齐
    # （东财日期为 YYYY-MM-DD，新浪利润表日期为 YYYYMMDD，需转换）
    merged_income = dict(inc_raw)
    for row_name, key in (("信用减值损失", "credit_impairment"),
                          ("资产减值损失", "asset_impairment")):
        row = dict(merged_income.get(row_name) or {})
        for d, item in supp.items():
            dk = d.replace("-", "")
            cur = row.get(dk)
            if cur in (None, 0) and key in item:
                row[dk] = item[key]
        if row:
            merged_income[row_name] = row

    return RawData(
        code=code, name=quote.get("name", code), periods=periods,
        income_raw=merged_income, balance_raw=bal_raw, cashflow_raw=cf_raw,
        segments=segments, dividends_total=div or 0.0, refinance_total=ref or 0.0,
        price=quote.get("price"), dividend_ttm=div_ttm or 0.0,
        kcfj_raw=kcfj or {},
    )
