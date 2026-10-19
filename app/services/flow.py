from app.models.schemas import FlowResult, FlowNode, FlowLink, Snapshot

# 列布局：来源(0) 营收(1) 成本/毛利(2) 费用层(3) 营业利润(4)
#          营业外(5) 利润总额(6) 所得税(7) 净利润(8) 少数股东(9) 归母(10)
COL = {
    "seg": 0, "rev": 1, "cost": 2, "gross": 2,
    "expense": 3, "tax": 3, "other": 3, "impair": 3,
    "op": 4, "nonbiz": 5, "tp": 6, "taxfee": 7,
    "np": 8, "minor": 9, "parent": 10,
}

MAX_SEGMENTS = 6


def _prev_year_key(period_key: str):
    for suf in ("H1", "Q1", "Q3", "Y"):
        if period_key.endswith(suf):
            return f"{int(period_key[:4]) - 1}{suf}"
    return None


def _yoy(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / abs(prev) * 100


def build(snap: Snapshot, rd=None) -> FlowResult:
    inc, bal, cf = snap.income, snap.balance, snap.cashflow
    rev = inc.revenue
    cost = inc.cost
    gross = rev - cost
    period_exp = (inc.selling_expense + inc.admin_expense +
                  inc.rnd_expense + inc.finance_expense)
    tax = inc.tax_surcharge
    impair = inc.credit_impairment + inc.asset_impairment   # 损失（正值）
    op = inc.operating_profit
    # 其他经营收益作为平衡项：营业利润 = 毛利 - 费用 - 税金 - 减值 + 其他收益
    base_op = gross - period_exp - tax - impair
    other = op - base_op                                  # 带符号
    nonbiz = inc.nonbiz_income - inc.nonbiz_expense          # 带符号
    tp = inc.total_profit
    it = inc.income_tax
    np_ = inc.net_profit
    parent = inc.parent_net_profit
    minor = inc.minority_interest

    # 同比（营收/成本/净利润，上年同期口径）
    rev_yoy = cost_yoy = np_yoy = None
    if rd is not None:
        pk = _prev_year_key(snap.period.key)
        if pk:
            from app.services.statements import build_snapshot
            prev_snap = build_snapshot(rd, pk) if pk in {
                p.key for p in rd.periods} else None
            if prev_snap is not None:
                rev_yoy = _yoy(rev, prev_snap.income.revenue)
                cost_yoy = _yoy(cost, prev_snap.income.cost)
                np_yoy = _yoy(np_, prev_snap.income.net_profit)

    nodes: list = []
    links: list = []

    # 来源（主营构成）：正值分部按值降序展示；
    # 「其他」「其他(补充)」及含「抵销」的负值项合并为「其他(含抵销)」（对标参考图口径）
    def _is_rest(s):
        nm = s.name or ""
        return s.income < 0 or "抵销" in nm or nm in ("其他", "其他(补充)", "其他（补充）")

    segs = list(snap.segments)
    seg_total = sum(s.income for s in segs)
    main = sorted((s for s in segs if not _is_rest(s)),
                  key=lambda x: -x.income)
    rest_list = [s for s in segs if _is_rest(s)]
    if len(main) > MAX_SEGMENTS:
        rest_list.extend(main[MAX_SEGMENTS:])
        main = main[:MAX_SEGMENTS]
    shown = list(main)
    rest_income = sum(s.income for s in rest_list)
    if rest_list:
        shown.append(type("S", (), {"name": "其他(含抵销)", "income": rest_income,
                                    "ratio": rest_income / seg_total if seg_total else 0,
                                    "yoy": None})())
    for i, s in enumerate(shown):
        nid = f"seg{i}"
        nodes.append(FlowNode(id=nid, col=COL["seg"], label=s.name,
                              value=s.income, role="gray",
                              yoy=s.yoy, ratio=s.ratio))
        links.append(FlowLink(source=nid, target="rev", value=s.income, role="gray"))

    nodes.append(FlowNode(id="rev", col=COL["rev"], label="营业收入", value=rev,
                          role="rev", yoy=rev_yoy))
    nodes.append(FlowNode(id="cost", col=COL["cost"], label="营业成本", value=cost,
                          role="cost", yoy=cost_yoy))
    nodes.append(FlowNode(id="gross", col=COL["cost"], label="毛利", value=gross,
                          role="red"))
    links.append(FlowLink(source="rev", target="cost", value=cost, role="cost"))
    links.append(FlowLink(source="rev", target="gross", value=gross, role="red"))

    nodes.append(FlowNode(id="expense", col=COL["expense"], label="期间费用",
                          value=period_exp, role="cost"))
    nodes.append(FlowNode(id="tax", col=COL["expense"], label="税金及附加",
                          value=tax, role="blue"))
    nodes.append(FlowNode(id="impair", col=COL["expense"], label="减值及处置损失",
                          value=impair, role="cost"))
    nodes.append(FlowNode(id="other", col=COL["expense"], label="其他经营收益",
                          value=other, role="red", signed=True))
    links.append(FlowLink(source="gross", target="expense", value=period_exp, role="cost"))
    links.append(FlowLink(source="gross", target="tax", value=tax, role="blue"))
    links.append(FlowLink(source="gross", target="impair", value=impair, role="cost"))
    if other >= 0:
        # 其他经营收益为收益：从毛利列下方流入营业利润
        links.append(FlowLink(source="other", target="op", value=other,
                              role="red", sign="+"))
        links.append(FlowLink(source="gross", target="op", value=base_op, role="red"))
    else:
        # 为损失：由毛利流出，作为终损节点
        links.append(FlowLink(source="gross", target="other", value=abs(other),
                              role="red", sign="-"))
        links.append(FlowLink(source="gross", target="op", value=op, role="red"))

    nodes.append(FlowNode(id="op", col=COL["op"], label="营业利润", value=op, role="red"))

    nodes.append(FlowNode(id="nonbiz", col=COL["nonbiz"], label="营业外净收入",
                          value=nonbiz, role="red", signed=True))
    nodes.append(FlowNode(id="tp", col=COL["tp"], label="利润总额", value=tp, role="red"))
    if nonbiz >= 0:
        links.append(FlowLink(source="op", target="tp", value=op, role="red"))
        links.append(FlowLink(source="nonbiz", target="tp", value=nonbiz,
                              role="red", sign="+"))
    else:
        links.append(FlowLink(source="op", target="tp", value=tp, role="red"))
        links.append(FlowLink(source="op", target="nonbiz", value=abs(nonbiz),
                              role="red", sign="-"))

    nodes.append(FlowNode(id="taxfee", col=COL["taxfee"], label="所得税费用",
                          value=it, role="blue"))
    nodes.append(FlowNode(id="np", col=COL["np"], label="净利润", value=np_,
                          role="red", yoy=np_yoy))
    links.append(FlowLink(source="tp", target="taxfee", value=it, role="blue"))
    links.append(FlowLink(source="tp", target="np", value=tp - it, role="red"))

    nodes.append(FlowNode(id="minor", col=COL["minor"], label="少数股东权益",
                          value=minor, role="green"))
    nodes.append(FlowNode(id="parent", col=COL["parent"], label="归母净利润",
                          value=parent, role="red"))
    links.append(FlowLink(source="np", target="minor", value=minor, role="cost"))
    links.append(FlowLink(source="np", target="parent", value=parent, role="red"))

    scale = max(rev, op, tp, np_, 1.0)
    residual = op - (base_op + other)
    degraded = []
    if abs(residual) > 0.005 * rev:
        degraded.append(f"营业利润平衡差额 {residual/1e8:,.2f} 亿（已并入其他经营收益）")

    return FlowResult(
        nodes=nodes, links=links, scale=scale,
        balance_residual=residual, segments_total=seg_total, degraded=degraded,
    )
