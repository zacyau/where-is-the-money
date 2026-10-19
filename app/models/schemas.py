from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class PeriodInfo:
    key: str            # 2026H1 / 2025Y / 2026Q1 / 2026Q3
    report_date: str    # 2026-06-30
    label: str          # 2026中报
    days: int
    year: int
    month: int


@dataclass
class SegmentItem:
    name: str
    income: float       # 元
    ratio: float        # 占营收
    yoy: Optional[float] = None


@dataclass
class IncomeStmt:
    revenue: float
    cost: float
    tax_surcharge: float
    selling_expense: float
    admin_expense: float
    rnd_expense: float
    finance_expense: float
    invest_income: float
    fair_value_change: float
    other_income: float
    asset_disposal_income: float
    credit_impairment: float
    asset_impairment: float
    operating_profit: float
    nonbiz_income: float
    nonbiz_expense: float
    total_profit: float
    income_tax: float
    net_profit: float
    parent_net_profit: float
    minority_interest: float


@dataclass
class BalanceStmt:
    total_assets: float
    total_liab: float
    parent_equity: float
    accounts_receivable: float
    inventory: float
    short_loan: float
    noncurrent_liab_1y: float
    long_loan: float
    bond_payable: float
    lease_liab: float
    cash: float


@dataclass
class CashFlowStmt:
    sales_cash: float
    operating_net: float


@dataclass
class Snapshot:
    code: str
    name: str
    period: PeriodInfo
    income: IncomeStmt
    balance: BalanceStmt
    cashflow: CashFlowStmt
    segments: List[SegmentItem]
    prior_balance: Optional[BalanceStmt] = None
    prior_income: Optional[IncomeStmt] = None


@dataclass
class MetricResult:
    key: str
    label: str
    value: Optional[float]
    unit: str                       # '%' / '倍' / '天'
    yoy: Optional[float] = None
    yoy_kind: str = "pct"           # 'pct' 同比百分比 | 'pp' 同比百分点
    history: Optional[List[float]] = None
    history_labels: Optional[List[str]] = None
    caliber: Optional[str] = None
    source: Optional[str] = None


@dataclass
class FlowNode:
    id: str
    col: int
    label: str
    value: float
    role: str                       # gray/green/red/blue/profit/expense...
    signed: bool = False            # 是否展示带符号（如其他经营收益）
    yoy: Optional[float] = None     # 同比%（分部/营收/成本/净利润）
    ratio: Optional[float] = None   # 占营收比（分部）


@dataclass
class FlowLink:
    source: str
    target: str
    value: float
    role: str
    sign: str = "+"                # '+' 计入 / '-' 扣减


@dataclass
class FlowResult:
    nodes: List[FlowNode]
    links: List[FlowLink]
    scale: float
    balance_residual: float
    segments_total: float
    degraded: List[str] = field(default_factory=list)
