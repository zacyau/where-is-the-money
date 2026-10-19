from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates
from app.config import WARM_COMPANIES
from app.services.company import get_company_view
from app.providers import tencent

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    warm = []
    for code in WARM_COMPANIES:
        try:
            q = await tencent.get_quote(code)
            warm.append({"code": code, "name": q.get("name", code),
                         "price": q.get("price")})
        except Exception:
            warm.append({"code": code, "name": code, "price": None})
    return templates.TemplateResponse(
        request, "index.html", {"warm": warm}
    )


@router.get("/c/{code}", response_class=HTMLResponse)
async def company(request: Request, code: str, period: str = None):
    try:
        view = await get_company_view(code, period)
    except Exception as e:  # noqa: BLE001
        return templates.TemplateResponse(
            request,
            "error.html",
            {"code": code, "err": str(e)},
            status_code=502,
        )
    return templates.TemplateResponse(
        request, "company.html", {"view": view}
    )


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}
