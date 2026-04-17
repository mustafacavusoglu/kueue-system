from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import QueueItem

router = APIRouter(prefix="/partial")
templates = Jinja2Templates(directory="app/templates")

USER_NAMES = settings.ALLOWED_USERS


def _waiting_order(query):
    return query.order_by(
        func.coalesce(QueueItem.queue_order, 999999), QueueItem.created_at.asc()
    )


def _enrich_positions(items, all_waiting):
    for item in items:
        if item.status == "waiting":
            item.position = next(
                (i for i, w in enumerate(all_waiting, 1) if w.id == item.id), None
            )
        else:
            item.position = None


@router.get("/queue-visual", response_class=HTMLResponse)
async def partial_queue_visual(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    all_waiting = _waiting_order(
        db.query(QueueItem).filter(QueueItem.status == "waiting")
    ).all()

    global_position = None
    for idx, item in enumerate(all_waiting, 1):
        if item.username == username:
            global_position = idx
            break

    return templates.TemplateResponse(
        "partials/_queue_visual.html",
        {
            "request": request,
            "global_position": global_position,
        },
    )


@router.get("/my-items", response_class=HTMLResponse)
async def partial_my_items(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    all_waiting = _waiting_order(
        db.query(QueueItem).filter(QueueItem.status == "waiting")
    ).all()

    my_items = (
        db.query(QueueItem)
        .filter(QueueItem.username == username)
        .order_by(QueueItem.created_at.desc())
        .all()
    )

    _enrich_positions(my_items, all_waiting)

    waiting = [i for i in my_items if i.status != "deleted"]
    deleted = [i for i in my_items if i.status == "deleted"]

    return templates.TemplateResponse(
        "partials/_my_items.html",
        {
            "request": request,
            "username": username,
            "waiting": waiting,
            "deleted": deleted,
            "user_names": USER_NAMES,
        },
    )


@router.get("/all-queue", response_class=HTMLResponse)
async def partial_all_queue(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    waiting = _waiting_order(
        db.query(QueueItem).filter(QueueItem.status == "waiting")
    ).all()

    for idx, item in enumerate(waiting, 1):
        item.position = idx

    return templates.TemplateResponse(
        "partials/_all_queue.html",
        {
            "request": request,
            "waiting": waiting,
            "user_names": USER_NAMES,
            "current_user": username,
        },
    )


@router.get("/completed", response_class=HTMLResponse)
async def partial_completed(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    completed = (
        db.query(QueueItem)
        .filter(QueueItem.status == "completed")
        .order_by(QueueItem.completed_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "partials/_completed_user.html",
        {
            "request": request,
            "completed": completed,
            "user_names": USER_NAMES,
            "current_user": username,
        },
    )


@router.get("/deleted", response_class=HTMLResponse)
async def partial_deleted(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    deleted = (
        db.query(QueueItem)
        .filter(QueueItem.status == "deleted")
        .order_by(QueueItem.deleted_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "partials/_deleted_user.html",
        {
            "request": request,
            "deleted": deleted,
            "user_names": USER_NAMES,
            "current_user": username,
        },
    )


@router.get("/admin/waiting", response_class=HTMLResponse)
async def partial_admin_waiting(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username or username != settings.ADMIN_USERNAME:
        return HTMLResponse("")

    waiting = _waiting_order(
        db.query(QueueItem).filter(QueueItem.status == "waiting")
    ).all()

    for idx, item in enumerate(waiting, 1):
        item.position = idx

    return templates.TemplateResponse(
        "partials/_admin_waiting.html",
        {
            "request": request,
            "waiting": waiting,
            "user_names": USER_NAMES,
            "admin_username": settings.ADMIN_USERNAME,
        },
    )


@router.get("/admin/completed", response_class=HTMLResponse)
async def partial_admin_completed(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username or username != settings.ADMIN_USERNAME:
        return HTMLResponse("")

    completed = (
        db.query(QueueItem)
        .filter(QueueItem.status == "completed")
        .order_by(QueueItem.completed_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "partials/_admin_completed.html",
        {
            "request": request,
            "completed": completed,
            "user_names": USER_NAMES,
        },
    )


@router.get("/admin/deleted", response_class=HTMLResponse)
async def partial_admin_deleted(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username or username != settings.ADMIN_USERNAME:
        return HTMLResponse("")

    deleted = (
        db.query(QueueItem)
        .filter(QueueItem.status == "deleted")
        .order_by(QueueItem.deleted_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "partials/_admin_deleted.html",
        {
            "request": request,
            "deleted": deleted,
            "user_names": USER_NAMES,
        },
    )


@router.get("/admin/stats", response_class=HTMLResponse)
async def partial_admin_stats(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username or username != settings.ADMIN_USERNAME:
        return HTMLResponse("")

    from app.models import QueueItem
    from sqlalchemy import func

    waiting_count = (
        db.query(func.count(QueueItem.id))
        .filter(QueueItem.status == "waiting")
        .scalar()
    )
    completed_count = (
        db.query(func.count(QueueItem.id))
        .filter(QueueItem.status == "completed")
        .scalar()
    )
    deleted_count = (
        db.query(func.count(QueueItem.id))
        .filter(QueueItem.status == "deleted")
        .scalar()
    )

    return templates.TemplateResponse(
        "partials/_admin_stats.html",
        {
            "request": request,
            "waiting_count": waiting_count or 0,
            "completed_count": completed_count or 0,
            "deleted_count": deleted_count or 0,
        },
    )
