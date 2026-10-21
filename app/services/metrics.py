from app.models.schemas import (
    METRIC_CATEGORY_ORDER,
    MetricResult,
    Snapshot,
)
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


def _amt(v) -> str:
    """元 → 人类可读金额（用于计算过程展示）。"""
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if a >= 1e4:
        return f"{v / 1e4:.1f}万"
    return f"{v:.0f}元"


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

    def add(key, label, value, unit, fn, kind_pp=False, caliber=None,
            source=None, formula=None, process=None, category=None):
        yoy = None
        if prev_key:
            pv = mval(fn, prev_key)
            if value is not None and pv not in (None, 0):
                yoy = (value - pv) / abs(pv) * 100 if not kind_pp else (value - pv)
        h, l = hist_vals(fn)
        out.append(MetricResult(
            key=key, label=label, value=value, unit=unit, yoy=yoy,
            yoy_kind=("pp" if kind_pp else "pct"), history=h,
            history_labels=l, caliber=caliber, formula=formula,
            process=process, category=category, source=source,
        ))

    rev = snap.income.revenue
    # 银行/保险口径（有「业务及管理费用」科目）：收现比、存货/应收周转、
    # 应收账款占比、带息债务占比等指标不适用（科目为 0 或口径完全不同），隐藏
    is_bank = snap.income.biz_admin_expense > 0
    ta = snap.balance.total_assets
    idays = snap.period.days

    def _ttm_detail(pk, income_field, balance_field):
        """TTM 口径明细：返回 (百分比, TTM净利过程文本, 平均分母过程文本)。

        TTM 净利润 = 当期累计 − 去年同期同周期累计 + 去年全年累计
                    （当期为年报时上式自然退化为当年全年净利润）
        分母（平均）= (当期期末值 + 去年同期同周期期末值) / 2
        解决中报/季报净利润为「累计值」导致 ROE/ROA 被低估的问题。
        """
        cur = build_snapshot(rd, pk)
        if not cur:
            return None
        cy = cur.period.year
        prev_same = build_snapshot(rd, _prev_year_key(pk))
        prev_year = build_snapshot(rd, f"{cy - 1}Y")
        ci = getattr(cur.income, income_field)
        if prev_same is not None and prev_year is not None:
            ps = getattr(prev_same.income, income_field)
            pyv = getattr(prev_year.income, income_field)
            inc = ci - ps + pyv
            inc_txt = f"{_amt(ci)} − {_amt(ps)} + {_amt(pyv)} = {_amt(inc)}"
        else:
            inc = ci  # 去年同周期/去年全年数据缺失，退化为当期累计
            inc_txt = f"{_amt(ci)}（去年数据缺失，退化为当期累计）"
        cb = getattr(cur.balance, balance_field)
        denom = _avg(cb, getattr(prev_same.balance, balance_field)) if prev_same is not None else cb
        if not denom:
            return None
        if prev_same is not None:
            pb = getattr(prev_same.balance, balance_field)
            den_txt = f"({_amt(cb)} + {_amt(pb)}) ÷ 2 = {_amt(denom)}"
        else:
            den_txt = f"{_amt(cb)}（期初数据缺失，未取平均）"
        return inc / denom * 100, inc_txt, den_txt

    def roe_fn(s):
        d = _ttm_detail(s.period.key, "parent_net_profit", "parent_equity")
        return d[0] if d else None

    def roa_fn(s):
        d = _ttm_detail(s.period.key, "net_profit", "total_assets")
        return d[0] if d else None

    roe_d = _ttm_detail(period_key, "parent_net_profit", "parent_equity")
    add("roe", "ROE", roe_d[0] if roe_d else None, "%", roe_fn,
        formula="TTM归母净利润 ÷ 平均归母净资产 × 100",
        process=(f"TTM归母净利：{roe_d[1]}；平均净资产：{roe_d[2]}；"
                 f"ROE = {roe_d[0]:.2f}%") if roe_d else None,
        caliber="TTM 口径：滚动12个月归母净利润 / 平均归母净资产 ×100；"
                "中报/季报净利润为累计值会低估，故取滚动12个月",
        source="新浪财经", category="盈利能力")

    roa_d = _ttm_detail(period_key, "net_profit", "total_assets")
    add("roa", "ROA", roa_d[0] if roa_d else None, "%", roa_fn,
        formula="TTM净利润 ÷ 平均总资产 × 100",
        process=(f"TTM净利：{roa_d[1]}；平均总资产：{roa_d[2]}；"
                 f"ROA = {roa_d[0]:.2f}%") if roa_d else None,
        caliber="TTM 口径：滚动12个月净利润 / 平均总资产 ×100；"
                "中报/季报净利润为累计值会低估，故取滚动12个月",
        source="新浪财经", category="盈利能力")

    oc = snap.cashflow.operating_net
    npf = snap.income.net_profit
    add("net_cash", "净现比",
        (oc / npf * 100) if npf else None, "%",
        lambda s: (s.cashflow.operating_net / s.income.net_profit * 100)
        if s.income.net_profit else None,
        formula="经营活动现金流净额 ÷ 净利润 × 100",
        process=(f"{_amt(oc)} ÷ {_amt(npf)} × 100 = {oc / npf * 100:.1f}%")
        if npf else None,
        caliber="经营活动现金流净额 / 净利润 ×100（≥100% 说明利润含金量足）",
        category="现金流含金量")

    if not is_bank:
        sc = snap.cashflow.sales_cash
        add("cash_receive", "收现比",
            (sc / rev * 100) if rev else None, "%",
            lambda s: (s.cashflow.sales_cash / s.income.revenue * 100)
            if s.income.revenue else None,
            formula="销售商品收到的现金 ÷ 营业收入 × 100",
            process=(f"{_amt(sc)} ÷ {_amt(rev)} × 100 = {sc / rev * 100:.1f}%")
            if rev else None,
            caliber="销售商品收到现金 / 营业收入 ×100（≥100% 说明收入含金量足）",
            category="现金流含金量")

    # 分红募资比（累计口径）
    div = rd.dividends_total
    ref = rd.refinance_total
    if ref and ref > 0:
        dr_val = div / ref
        dr_formula = "累计现金分红 ÷ 累计增发募资"
        dr_process = f"{_amt(div)} ÷ {_amt(ref)} = {dr_val:.2f}倍"
        dr_cal = "累计现金分红 / 累计增发募资（东财口径，IPO 及配股未计入）"
    else:
        cum_np = 0.0
        for p in rd.periods:
            if p.month == 12:
                s = build_snapshot(rd, p.key)
                if s:
                    cum_np += s.income.parent_net_profit
        dr_val = (div / cum_np) if cum_np else None
        dr_formula = "累计现金分红 ÷ 累计归母净利润（募资明细缺失降级）"
        dr_process = (f"{_amt(div)} ÷ {_amt(cum_np)} = {dr_val:.2f}倍"
                      if dr_val is not None else None)
        dr_cal = "募资明细缺失，已降级为 累计分红 / 累计归母净利润"
    out.append(MetricResult(
        key="dividend_raise", label="分红募资比", value=dr_val, unit="倍",
        yoy=None, yoy_kind="pct", history=None, history_labels=None,
        caliber=dr_cal, formula=dr_formula, process=dr_process,
        category="股东回报", source="东方财富",
    ))

    # 股息率 = 上一个完整自然年每股分红(税前) / 现价
    # 多次分红下 TTM 会跨年混算、今年至今又不完整，故取「上一个完整自然年」全部分红。
    dy_label = rd.dividend_prev_year_label or "上一年"
    dy_per = rd.dividend_prev_year
    if dy_per and rd.price:
        dy_val = dy_per / rd.price * 100
        dy_formula = "上一年度每股分红(税前) ÷ 现价 × 100"
        dy_process = (f"{dy_label}年度每股分红 {dy_per:.3f} 元 ÷ "
                      f"现价 {rd.price:.2f} 元 × 100 = {dy_val:.2f}%")
        dy_cal = f"{dy_label}年度每股分红 {dy_per:.3f} 元(税前) / 现价 {rd.price:.2f} 元"
    else:
        dy_val = None
        dy_formula = "上一年度每股分红(税前) ÷ 现价 × 100"
        dy_process = None
        dy_cal = f"{dy_label}年度无除息分红记录或行情缺失，暂无法计算"
    out.append(MetricResult(
        key="dividend_yield", label="股息率", value=dy_val, unit="%",
        yoy=None, yoy_kind="pct", history=None, history_labels=None,
        caliber=dy_cal, formula=dy_formula, process=dy_process,
        category="股东回报", source="东方财富/腾讯",
    ))

    if not is_bank:
        ar = snap.balance.accounts_receivable
        add("ar_ratio", "应收账款占比",
            (ar / ta * 100) if ta else None, "%",
            lambda s: (s.balance.accounts_receivable / s.balance.total_assets * 100)
            if s.balance.total_assets else None,
            formula="应收账款 ÷ 总资产 × 100",
            process=(f"{_amt(ar)} ÷ {_amt(ta)} × 100 = {ar / ta:.1f}%")
            if ta else None,
            caliber="应收账款 / 总资产 ×100（占比过高警惕收入质量）",
            source="新浪财经", category="资产安全性")

        def ibd_fn(s):
            debt = (s.balance.short_loan + s.balance.noncurrent_liab_1y +
                    s.balance.long_loan + s.balance.bond_payable + s.balance.lease_liab)
            return debt / s.balance.total_assets * 100 if s.balance.total_assets else None

        b = snap.balance
        ibd_debt = (b.short_loan + b.noncurrent_liab_1y + b.long_loan +
                    b.bond_payable + b.lease_liab)
        add("ibd_ratio", "带息债务占比", ibd_fn(snap), "%", ibd_fn,
            formula="（短期借款 + 一年内到期非流动负债 + 长期借款 + 应付债券 + 租赁负债）÷ 总资产 × 100",
            process=(f"({_amt(b.short_loan)} + {_amt(b.noncurrent_liab_1y)} + "
                     f"{_amt(b.long_loan)} + {_amt(b.bond_payable)} + "
                     f"{_amt(b.lease_liab)}) ÷ {_amt(ta)} × 100 = {ibd_debt / ta * 100:.1f}%")
            if ta else None,
            caliber="五项带息债务合计 / 总资产 ×100（衡量财务杠杆压力）",
            source="新浪财经", category="资产安全性")

        def inv_fn(s):
            if not s.income.cost:
                return None
            begin = s.prior_balance.inventory if s.prior_balance else s.balance.inventory
            avg = (s.balance.inventory + begin) / 2
            return avg / s.income.cost * s.period.days

        icost = snap.income.cost
        ibegin = (snap.prior_balance.inventory
                  if snap.prior_balance else snap.balance.inventory)
        iavg = (snap.balance.inventory + ibegin) / 2
        add("inv_days", "存货周转天数", inv_fn(snap), "天", inv_fn,
            formula="平均存货 ÷ 营业成本 × 报告期天数",
            process=(f"[({_amt(snap.balance.inventory)} + {_amt(ibegin)}) ÷ 2] ÷ "
                     f"{_amt(icost)} × {idays} 天 = {iavg / icost * idays:.1f} 天")
            if icost else None,
            caliber="（期末存货+期初存货)/2 ÷ 营业成本 × 报告期天数",
            source="新浪财经", category="营运效率")

        def ar_fn(s):
            if not s.income.revenue:
                return None
            begin = (s.prior_balance.accounts_receivable
                     if s.prior_balance else s.balance.accounts_receivable)
            avg = (s.balance.accounts_receivable + begin) / 2
            return avg / s.income.revenue * s.period.days

        arbegin = (snap.prior_balance.accounts_receivable
                   if snap.prior_balance else snap.balance.accounts_receivable)
        aravg = (snap.balance.accounts_receivable + arbegin) / 2
        add("ar_days", "应收账款周转天数", ar_fn(snap), "天", ar_fn,
            formula="平均应收账款 ÷ 营业收入 × 报告期天数",
            process=(f"[({_amt(ar)} + {_amt(arbegin)}) ÷ 2] ÷ {_amt(rev)} × "
                     f"{idays} 天 = {aravg / rev * idays:.1f} 天")
            if rev else None,
            caliber="（期末应收+期初应收)/2 ÷ 营业收入 × 报告期天数",
            source="新浪财经", category="营运效率")

    icost2 = snap.income.cost
    add("gross_margin", "毛利率",
        ((rev - icost2) / rev * 100) if rev else None, "%",
        lambda s: ((s.income.revenue - s.income.cost) / s.income.revenue * 100)
        if s.income.revenue else None, kind_pp=True,
        formula="（营业收入 − 营业成本）÷ 营业收入 × 100",
        process=(f"({_amt(rev)} − {_amt(icost2)}) ÷ {_amt(rev)} × 100 = "
                 f"{(rev - icost2) / rev * 100:.1f}%") if rev else None,
        caliber="（营业收入-营业成本) / 营业收入 ×100",
        source="新浪财经", category="盈利能力")

    opf = snap.income.operating_profit
    add("operating_margin", "营业利润率",
        (opf / rev * 100) if rev else None, "%",
        lambda s: (s.income.operating_profit / s.income.revenue * 100)
        if s.income.revenue else None, kind_pp=True,
        formula="营业利润 ÷ 营业收入 × 100",
        process=(f"{_amt(opf)} ÷ {_amt(rev)} × 100 = {opf / rev * 100:.1f}%")
        if rev else None,
        caliber="营业利润 / 营业收入 ×100",
        source="新浪财经", category="盈利能力")

    npm = snap.income.net_profit
    add("net_margin", "净利率",
        (npm / rev * 100) if rev else None, "%",
        lambda s: (s.income.net_profit / s.income.revenue * 100)
        if s.income.revenue else None, kind_pp=True,
        formula="净利润 ÷ 营业收入 × 100",
        process=(f"{_amt(npm)} ÷ {_amt(rev)} × 100 = {npm / rev * 100:.1f}%")
        if rev else None,
        caliber="净利润 / 营业收入 ×100",
        source="新浪财经", category="盈利能力")

    # 扣非净利润同比增速（东财主要指标）
    kcfj_by_key = {}
    for p in rd.periods:
        v = rd.kcfj_raw.get(p.report_date)
        if v is not None:
            kcfj_by_key[p.key] = v

    def kcfj_growth(pk):
        cur = kcfj_by_key.get(pk)
        prev = kcfj_by_key.get(_prev_year_key(pk) or "")
        if cur is None or prev in (None, 0):
            return None
        return (cur - prev) / abs(prev) * 100

    kg_val = kcfj_growth(period_key)
    kg_missing = kg_val is None and not kcfj_by_key
    kg_h, kg_l = [], []
    for p in reversed(rd.periods[:8]):
        kg_h.append(kcfj_growth(p.key))
        kg_l.append(p.label)
    kcur = kcfj_by_key.get(period_key)
    kprev = kcfj_by_key.get(_prev_year_key(period_key) or "")
    if kcur is not None and kprev not in (None, 0):
        kg_process = (f"({_amt(kcur)} − {_amt(kprev)}) ÷ |{_amt(kprev)}| × 100 = "
                      f"{kg_val:.1f}%")
    else:
        kg_process = None
    if kg_missing:
        kg_cal = "东财主要指标未返回扣非数据，暂无法计算"
    else:
        kg_cal = "扣除非经常性损益后的净利润，累计口径同比"
    out.append(MetricResult(
        key="kcfj_growth", label="扣非净利润增速", value=kg_val, unit="%",
        yoy=None, yoy_kind="pct", history=kg_h, history_labels=kg_l,
        caliber=kg_cal,
        formula="（本期扣非净利润 − 去年同期扣非净利润）÷ |去年同期| × 100",
        process=kg_process, category="成长性", source="东方财富",
    ))

    # 按分类排序（稳定排序，保持各类内原有顺序）
    order = {c: i for i, c in enumerate(METRIC_CATEGORY_ORDER)}
    out.sort(key=lambda m: order.get(m.category or "", 99))

    return out, cur_period
