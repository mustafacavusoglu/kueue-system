from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import FeatureRequest

router = APIRouter(prefix="/feature-requests")
templates = Jinja2Templates(directory="app/templates")

USER_NAMES = settings.ALLOWED_USERS


def _fr_to_dict(fr):
    display_name = USER_NAMES.get(fr.requested_by, fr.requested_by)
    return {
        "id": fr.id,
        "title": fr.title,
        "summary": fr.summary,
        "requested_by": fr.requested_by,
        "display_name": display_name,
        "created_at": fr.created_at.strftime("%d.%m.%Y %H:%M"),
    }


@router.get("")
async def feature_requests_page(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    is_admin = username == settings.ADMIN_USERNAME
    all_requests = (
        db.query(FeatureRequest)
        .order_by(FeatureRequest.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "feature_requests.html",
        {
            "request": request,
            "username": username,
            "is_admin": is_admin,
            "feature_requests": all_requests,
            "user_names": USER_NAMES,
            "app_name": settings.APP_NAME,
        },
    )


@router.post("/add")
async def add_feature_request(
    request: Request,
    title: str = Form(...),
    summary: str = Form(...),
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    fr = FeatureRequest(title=title, summary=summary, requested_by=username)
    db.add(fr)
    db.commit()
    db.refresh(fr)

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"ok": True, "item": _fr_to_dict(fr)})

    return RedirectResponse(url="/feature-requests", status_code=303)


@router.get("/data")
async def feature_requests_data(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    all_requests = (
        db.query(FeatureRequest)
        .order_by(FeatureRequest.created_at.desc())
        .all()
    )

    return JSONResponse({"items": [_fr_to_dict(fr) for fr in all_requests]})


@router.get("/partial", response_class=HTMLResponse)
async def partial_feature_requests(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    all_requests = (
        db.query(FeatureRequest)
        .order_by(FeatureRequest.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "partials/_feature_requests.html",
        {
            "request": request,
            "feature_requests": all_requests,
            "user_names": USER_NAMES,
            "current_user": username,
        },
    )
