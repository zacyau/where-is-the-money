from fastapi import APIRouter

from app.providers import tencent
from app.services.statements import collect
from app.services.company import (
    get_company_view, refresh_company, flow_to_dict, metrics_to_dict,
)
from app.services import flow as flow_svc, metrics as metrics_svc
from app.services.statements import build_snapshot

router = APIRouter(prefix="/api")


@router.get("/search")
async def search(q: str):
    if not q or len(q.strip()) < 1:
        return []
    return await tencent.search(q.strip())


@router.get("/c/{code}/periods")
async def periods(code: str):
    rd = await collect(code)
    return [{"key": p.key, "label": p.label} for p in rd.periods[:12]]


@router.get("/c/{code}/flow")
async def flow(code: str, period: str = None):
    view = await get_company_view(code, period)
    return view["flow"]


@router.get("/c/{code}/metrics")
async def metrics(code: str, period: str = None):
    view = await get_company_view(code, period)
    return {"period": view["period"], "metrics": view["metrics"]}


@router.post("/c/{code}/refresh")
async def refresh(code: str, period: str = None):
    view = await refresh_company(code, period)
    return view
