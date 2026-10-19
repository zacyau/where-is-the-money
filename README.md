# 钱去哪了 · 资金流向分析站

模仿「XX 的钱去哪了」风格的资金流向桑基图，并叠加 12 项财务质量指标。可换公司、可换报告期。

## 技术栈

- Python 3.13 + venv
- FastAPI（Jinja2 服务端渲染，无前后端分离）
- 数据源：腾讯财经（行情）、东方财富（主营构成 / 分红募资）、新浪财经（三大报表明细）
- 自研 SVG 桑基图（无 ECharts、无前端构建步骤）

## 启动

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows；Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 可选
uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000

## 主要功能

- 首页：搜索公司（代码 / 名称 / 拼音），热门公司入口
- 公司页：`{公司}的钱去哪了` 标题 + 桑基图 + 报告期切换
- 桑基图：主营构成 → 营业收入 → 成本 / 毛利 → 费用 / 税 / 其他收益 / 减值 → 营业利润 → 利润总额 → 净利润 → 归母净利润
- 质量指标（12 项）：ROE、ROA、净现比、收现比、分红募资比、应收账款占比、带息债务占比、存货周转天数、应收账款周转天数、毛利率、营业利润率、净利率；含同比、近 8 期趋势
- 原始科目表（单位：亿元）用于核对口径

## 目录

```
app/
  providers/   腾讯 / 东方财富 / 新浪 适配层（限速、重试、编码统一、失败降级）
  services/    科目合并、12 指标、桑基构建、公司视图聚合
  cache/       SQLite TTL 缓存
  routers/     页面与 JSON 接口
  templates/    Jinja2 模板
  static/       CSS + 桑基/指标/搜索 JS
```

## 说明

- 数据每分钟~6 小时不等做本地缓存；页面右上角可调用 `/api/c/{code}/refresh` 强制刷新。
- 多源数据缺失时自动降级，并在指标卡 / 页面给出口径提示。
- 仅供研究参考，不构成投资建议。
