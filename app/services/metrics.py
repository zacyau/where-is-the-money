from app.models.schemas import MetricResult, Snapshot
from app.services.statements import RawData, build_snapshot


def _prev_year_key(period_key: str):
    for suf in ("H1", "Q1", "Q3", "Y"):
        if period_key.endswith(suf):
            return f"{int(period_key[:4]) - 1}{suf}"
    return None


def _avg(cur, prior):
    if prior is None:
        return cur
    return (cur + prior) / 2


def build(rd: RawData, period_key: str):
    snap = build_snapshot(rd, period_key)
    if snap is None:
        return [], None
    cur_period = snap.period
    prev_key = _prev_year_key(period_key)
    out: list = []

    def mval(fn, pk):
        s = build_snapshot(rd, pk)
        return fn(s) if s else None

    def hist_vals(fn):
        vals, labs = [], []
        for p in reversed(rd.periods[:8]):
            vals.append(mval(fn, p.key))
            labs.append(p.label)
        return vals, labs

    def add(key, label, value, unit, fn, kind_pp=False, caliber=None, source=None):
        yoy = None
        if prev_key:
            pv = mval(fn, prev_key)
            if value is not None and pv not in (None, 0):
                yoy = (value - pv) / abs(pv) * 100 if not kind_pp else (value - pv)
        h, l = hist_vals(fn)
        out.append(MetricResult(
            key=key, label=label, value=value, unit=unit, yoy=yoy,
            yoy_kind=("pp" if kind_pp else "pct"), history=h,
            history_labels=l, caliber=caliber, source=source,
        ))

    rev = snap.income.revenue

    add("roe", "ROE",
        (snap.income.parent_net_profit / _avg(snap.balance.parent_equity,
            snap.prior_balance.parent_equity if snap.prior_balance else None) * 100)
        if snap.balance.parent_equity else None, "%",
        lambda s: (s.income.parent_net_profit / _avg(s.balance.parent_equity,
            s.prior_balance.parent_equity if s.prior_balance else None) * 100)
        if s.balance.parent_equity else None, source="新浪财经")

    add("roa", "ROA",
        (snap.income.net_profit / _avg(snap.balance.total_assets,
            snap.prior_balance.total_assets if snap.prior_balance else None) * 100)
        if snap.balance.total_assets else None, "%",
        lambda s: (s.income.net_profit / _avg(s.balance.total_assets,
            s.prior_balance.total_assets if s.prior_balance else None) * 100)
        if s.balance.total_assets else None, source="新浪财经")

    add("net_cash", "净现比",
        (snap.cashflow.operating_net / snap.income.net_profit)
        if snap.income.net_profit else None, "倍",
        lambda s: (s.cashflow.operating_net / s.income.net_profit)
        if s.income.net_profit else None, source="新浪财经")

    add("cash_receive", "收现比",
        (snap.cashflow.sales_cash / rev) if rev else None, "倍",
        lambda s: (s.cashflow.sales_cash / s.income.revenue)
        if s.income.revenue else None, source="新浪财经")

    # 分红募资比（累计口径）
    div = rd.dividends_total
    ref = rd.refinance_total
    if ref and ref > 0:
        dr_val = div / ref
        dr_cal = None
    else:
        cum_np = 0.0
        for p in rd.periods:
            if p.month == 12:
                s = build_snapshot(rd, p.key)
                if s:
                    cum_np += s.income.parent_net_profit
        dr_val = (div / cum_np) if cum_np else None
        dr_cal = "募资明细缺失，已降级为 累计分红 / 累计归母净利润"
    out.append(MetricResult(
        key="dividend_raise", label="分红募资比", value=dr_val, unit="倍",
        yoy=None, yoy_kind="pct", history=None, history_labels=None,
        caliber=dr_cal, source="东方财富",
    ))

    add("ar_ratio", "应收账款占比",
        (snap.balance.accounts_receivable / snap.balance.total_assets * 100)
        if snap.balance.total_assets else None, "%",
        lambda s: (s.balance.accounts_receivable / s.balance.total_assets * 100)
        if s.balance.total_assets else None, source="新浪财经")

    def ibd_fn(s):
        debt = (s.balance.short_loan + s.balance.noncurrent_liab_1y +
                s.balance.long_loan + s.balance.bond_payable + s.balance.lease_liab)
        return debt / s.balance.total_assets * 100 if s.balance.total_assets else None
    add("ibd_ratio", "带息债务占比", ibd_fn(snap), "%", ibd_fn, source="新浪财经")

    def inv_fn(s):
        if not s.income.cost:
            return None
        begin = s.prior_balance.inventory if s.prior_balance else s.balance.inventory
        avg = (s.balance.inventory + begin) / 2
        return avg / s.income.cost * s.period.days
    add("inv_days", "存货周转天数", inv_fn(snap), "天", inv_fn, source="新浪财经")

    def ar_fn(s):
        if not s.income.revenue:
            return None
        begin = (s.prior_balance.accounts_receivable
                 if s.prior_balance else s.balance.accounts_receivable)
        avg = (s.balance.accounts_receivable + begin) / 2
        return avg / s.income.revenue * s.period.days
    add("ar_days", "应收账款周转天数", ar_fn(snap), "天", ar_fn, source="新浪财经")

    add("gross_margin", "毛利率",
        ((rev - snap.income.cost) / rev * 100) if rev else None, "%",
        lambda s: ((s.income.revenue - s.income.cost) / s.income.revenue * 100)
        if s.income.revenue else None, kind_pp=True, source="新浪财经")

    add("operating_margin", "营业利润率",
        (snap.income.operating_profit / rev * 100) if rev else None, "%",
        lambda s: (s.income.operating_profit / s.income.revenue * 100)
        if s.income.revenue else None, kind_pp=True, source="新浪财经")

    add("net_margin", "净利率",
        (snap.income.net_profit / rev * 100) if rev else None, "%",
        lambda s: (s.income.net_profit / s.income.revenue * 100)
        if s.income.revenue else None, kind_pp=True, source="新浪财经")

    return out, cur_period
