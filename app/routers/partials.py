from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, is_admin
from app.config import settings
from app.database import get_db
from app.models import QueueItem
from collections import defaultdict

router = APIRouter(prefix="/partial")
templates = Jinja2Templates(directory="app/templates")

USER_NAMES = settings.ALLOWED_USERS


def _waiting_order(query):
    return query.order_by(
        func.coalesce(QueueItem.queue_order, 999999), QueueItem.created_at.asc()
    )


def _target(item):
    return item.target_user if item.target_user else settings.ADMIN_USERNAME.upper()


def _assign_per_target_positions(items):
    groups = defaultdict(list)
    for item in items:
        groups[_target(item)].append(item)
    for group_items in groups.values():
        for idx, item in enumerate(group_items, 1):
            item.position = idx


def _enrich_positions(items, all_waiting):
    groups = defaultdict(list)
    for w in all_waiting:
        groups[_target(w)].append(w)
    for item in items:
        if item.status == "waiting":
            group = groups.get(_target(item), [])
            item.position = next(
                (i for i, w in enumerate(group, 1) if w.id == item.id), None
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
    groups = defaultdict(list)
    for w in all_waiting:
        groups[_target(w)].append(w)

    for target, items in groups.items():
        for idx, item in enumerate(items, 1):
            if item.username == username:
                global_position = idx
                break
        if global_position is not None:
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

    _assign_per_target_positions(waiting)

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
    if not username or not is_admin(username):
        return HTMLResponse("")

    waiting = _waiting_order(
        db.query(QueueItem).filter(QueueItem.status == "waiting")
    ).all()

    _assign_per_target_positions(waiting)

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
    if not username or not is_admin(username):
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
    if not username or not is_admin(username):
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
    if not username or not is_admin(username):
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


@router.get("/incoming-queue", response_class=HTMLResponse)
async def partial_incoming_queue(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    incoming = _waiting_order(
        db.query(QueueItem).filter(
            QueueItem.status == "waiting",
            QueueItem.target_user == username,
            QueueItem.username != username,
        )
    ).all()

    for idx, item in enumerate(incoming, 1):
        item.position = idx

    return templates.TemplateResponse(
        "partials/_incoming_queue.html",
        {
            "request": request,
            "incoming": incoming,
            "user_names": USER_NAMES,
            "current_user": username,
        },
    )


@router.get("/empty", response_class=HTMLResponse)
async def partial_empty():
    return HTMLResponse("")


@router.get("/credits-badge", response_class=HTMLResponse)
async def partial_credits_badge(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return HTMLResponse("")

    from app.models import UserCredit

    uc = db.query(UserCredit).filter(UserCredit.username == username).first()
    credits = uc.credits if uc else 5

    return HTMLResponse(
        f'<span id="credits-badge" style="display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; background: var(--gold-badge-bg); border: 1px solid var(--gold-glow-border); border-radius: 20px; font-size: 11px; font-weight: 700; color: var(--gold-badge-text);">'
        f'<svg width="12" height="12" viewBox="0 0 16 16" style="transform: rotate(45deg);"><rect x="2" y="2" width="12" height="12" rx="2" fill="var(--gold-500)"/></svg>'
        f"{credits} Baklava</span>"
    )
