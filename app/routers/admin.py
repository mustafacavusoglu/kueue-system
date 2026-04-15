from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import QueueItem

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def _item_to_dict(item, position=None):
    return {
        "id": item.id,
        "username": item.username,
        "subject": item.subject,
        "description": item.description,
        "status": item.status,
        "created_at": item.created_at.strftime("%d.%m.%Y %H:%M"),
        "completed_at": item.completed_at.strftime("%d.%m.%Y %H:%M")
        if item.completed_at
        else None,
        "position": position,
    }


@router.get("")
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)
    if username != settings.ADMIN_USERNAME:
        return RedirectResponse(url="/dashboard", status_code=303)

    waiting = (
        db.query(QueueItem)
        .filter(QueueItem.status == "waiting")
        .order_by(QueueItem.created_at.asc())
        .all()
    )

    completed = (
        db.query(QueueItem)
        .filter(QueueItem.status == "completed")
        .order_by(QueueItem.completed_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "username": username,
            "admin_username": settings.ADMIN_USERNAME,
            "waiting": waiting,
            "completed": completed,
        },
    )


@router.get("/data")
async def admin_data(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username or username != settings.ADMIN_USERNAME:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    waiting = (
        db.query(QueueItem)
        .filter(QueueItem.status == "waiting")
        .order_by(QueueItem.created_at.asc())
        .all()
    )

    completed = (
        db.query(QueueItem)
        .filter(QueueItem.status == "completed")
        .order_by(QueueItem.completed_at.desc())
        .all()
    )

    return JSONResponse(
        {
            "waiting": [_item_to_dict(item, i + 1) for i, item in enumerate(waiting)],
            "completed": [_item_to_dict(item) for item in completed],
        }
    )


@router.post("/{item_id}/complete")
async def complete_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username or username != settings.ADMIN_USERNAME:
        return RedirectResponse(url="/", status_code=303)

    item = (
        db.query(QueueItem)
        .filter(QueueItem.id == item_id, QueueItem.status == "waiting")
        .first()
    )
    if item:
        item.status = "completed"
        item.completed_at = datetime.now(timezone.utc)
        db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"ok": True})

    return RedirectResponse(url="/admin", status_code=303)
