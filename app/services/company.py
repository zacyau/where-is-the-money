from app.cache.store import cached, clear_code
from app.providers import tencent
from app.services.statements import collect, build_snapshot, RawData
from app.services import flow as flow_svc, metrics as metrics_svc
from app.models.schemas import FlowResult, MetricResult, Snapshot


def flow_to_dict(fr: FlowResult) -> dict:
    return {
        "nodes": [
            {"id": n.id, "col": n.col, "label": n.label,
             "value": n.value, "role": n.role, "signed": n.signed}
            for n in fr.nodes
        ],
        "links": [
            {"source": l.source, "target": l.target, "value": l.value,
             "role": l.role, "sign": l.sign}
            for l in fr.links
        ],
        "scale": fr.scale,
        "balance_residual": fr.balance_residual,
        "segments_total": fr.segments_total,
        "degraded": fr.degraded,
    }


def metrics_to_dict(m: MetricResult) -> dict:
    return {
        "key": m.key, "label": m.label, "value": m.value, "unit": m.unit,
        "yoy": m.yoy, "yoy_kind": m.yoy_kind,
        "history": m.history, "history_labels": m.history_labels,
        "caliber": m.caliber, "source": m.source,
    }


async def get_company_view(code: str, period_key: str = None) -> dict:
    rd: RawData = await collect(code)
    if not rd.periods:
        raise ValueError("未获取到财报数据，可能代码有误或该公司无公开财报")
    keys = [p.key for p in rd.periods]
    if period_key not in keys:
        period_key = keys[0]
    snap: Snapshot = build_snapshot(rd, period_key)
    fr = flow_svc.build(snap)
    ms, cur_period = metrics_svc.build(rd, period_key)
    quote = await cached(f"q:{code}", 60, lambda: tencent.get_quote(code))

    flow_dict = flow_to_dict(fr)
    flow_dict["period"] = {
        "key": cur_period.key, "label": cur_period.label,
        "report_date": cur_period.report_date,
    }
    return {
        "code": rd.code,
        "name": rd.name,
        "quote": quote,
        "period": {"key": cur_period.key, "label": cur_period.label,
                   "report_date": cur_period.report_date},
        "periods": [{"key": p.key, "label": p.label} for p in rd.periods[:12]],
        "flow": flow_dict,
        "metrics": [metrics_to_dict(m) for m in ms],
        "raw": _raw_table(snap),
        "degraded": fr.degraded,
    }


def _raw_table(snap: Snapshot) -> list:
    inc, bal, cf = snap.income, snap.balance, snap.cashflow
    rows = [
        ("营业收入", inc.revenue), ("营业成本", inc.cost),
        ("税金及附加", inc.tax_surcharge),
        ("销售费用", inc.selling_expense), ("管理费用", inc.admin_expense),
        ("研发费用", inc.rnd_expense), ("财务费用", inc.finance_expense),
        ("投资收益", inc.invest_income),
        ("公允价值变动收益", inc.fair_value_change),
        ("其他收益", inc.other_income),
        ("资产减值损失", inc.asset_impairment),
        ("信用减值损失", inc.credit_impairment),
        ("营业利润", inc.operating_profit),
        ("营业外收入", inc.nonbiz_income), ("营业外支出", inc.nonbiz_expense),
        ("利润总额", inc.total_profit), ("所得税费用", inc.income_tax),
        ("净利润", inc.net_profit),
        ("归母净利润", inc.parent_net_profit),
        ("少数股东损益", inc.minority_interest),
        ("资产总计", bal.total_assets), ("负债合计", bal.total_liab),
        ("归母净资产", bal.parent_equity),
        ("应收账款", bal.accounts_receivable), ("存货", bal.inventory),
        ("销售商品收现", cf.sales_cash),
        ("经营活动现金流净额", cf.operating_net),
    ]
    return [{"name": n, "value": v} for n, v in rows]


async def refresh_company(code: str, period_key: str = None) -> dict:
    clear_code(code)
    return await get_company_view(code, period_key)
