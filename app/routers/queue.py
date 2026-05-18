from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import QueueItem, Comment, UserCredit, ISTANBUL_TZ
from app.sse import event_bus

router = APIRouter(prefix="/queue")

USER_NAMES = settings.ALLOWED_USERS


def _get_credits(db: Session, username: str) -> int:
    uc = db.query(UserCredit).filter(UserCredit.username == username).first()
    if not uc:
        uc = UserCredit(username=username, credits=5)
        db.add(uc)
        db.commit()
        db.refresh(uc)
    return uc.credits


def _comment_to_dict(c):
    display_name = USER_NAMES.get(c.username, c.username)
    return {
        "id": c.id,
        "username": c.username,
        "display_name": display_name,
        "text": c.text,
        "created_at": c.created_at.strftime("%d.%m.%Y %H:%M"),
    }


def _item_to_dict(item, position=None):
    display_name = USER_NAMES.get(item.username, item.username)
    target_display = USER_NAMES.get(item.target_user, item.target_user)
    return {
        "id": item.id,
        "subject": item.subject,
        "description": item.description,
        "status": item.status,
        "display_name": display_name,
        "username": item.username,
        "target_user": item.target_user,
        "target_display": target_display,
        "created_at": item.created_at.strftime("%d.%m.%Y %H:%M"),
        "completed_at": item.completed_at.strftime("%d.%m.%Y %H:%M")
        if item.completed_at
        else None,
        "deleted_at": item.deleted_at.strftime("%d.%m.%Y %H:%M")
        if item.deleted_at
        else None,
        "position": position,
        "comments": [_comment_to_dict(c) for c in item.comments],
    }


def _waiting_order(query):
    return query.order_by(
        func.coalesce(QueueItem.queue_order, 999999), QueueItem.created_at.asc()
    )


@router.post("/add")
async def add_to_queue(
    request: Request,
    subject: str = Form(...),
    description: str = Form(""),
    target_user: str = Form(""),
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    target = target_user.strip() if target_user.strip() else settings.ADMIN_USERNAME

    item = QueueItem(
        username=username,
        target_user=target,
        subject=subject,
        description=description,
    )
    db.add(item)

    uc = db.query(UserCredit).filter(UserCredit.username == username).first()
    if not uc:
        uc = UserCredit(username=username, credits=5)
        db.add(uc)
        db.flush()
    if uc.credits > 0:
        uc.credits -= 1

    db.commit()
    db.refresh(item)

    await event_bus.broadcast("queue_updated")
    await event_bus.broadcast("notification", f"{target}:queue")

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        all_waiting = _waiting_order(
            db.query(QueueItem).filter(QueueItem.status == "waiting")
        ).all()
        position = next(
            (i for i, w in enumerate(all_waiting, 1) if w.id == item.id), None
        )
        credits = _get_credits(db, username)
        return JSONResponse(
            {"ok": True, "item": _item_to_dict(item, position), "credits": credits}
        )

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/{item_id}/delete")
async def delete_from_queue(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    item = (
        db.query(QueueItem)
        .filter(QueueItem.id == item_id, QueueItem.username == username)
        .first()
    )
    if item and item.status != "deleted":
        item.status = "deleted"
        item.deleted_at = datetime.now(ISTANBUL_TZ)
        db.commit()
        await event_bus.broadcast("queue_updated")

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"ok": True})

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/my")
async def my_queue(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    all_waiting = _waiting_order(
        db.query(QueueItem).filter(QueueItem.status == "waiting")
    ).all()

    global_position = None
    for idx, w in enumerate(all_waiting, 1):
        if w.username == username:
            global_position = idx
            break

    my_items = (
        db.query(QueueItem)
        .filter(QueueItem.username == username)
        .order_by(QueueItem.created_at.desc())
        .all()
    )

    items = []
    for item in my_items:
        pos = None
        if item.status == "waiting":
            pos = next(
                (i for i, w in enumerate(all_waiting, 1) if w.id == item.id), None
            )
        items.append(_item_to_dict(item, pos))

    credits = _get_credits(db, username)

    return JSONResponse(
        {
            "items": items,
            "global_position": global_position,
            "credits": credits,
        }
    )


@router.get("/incoming")
async def incoming_queue(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    incoming = _waiting_order(
        db.query(QueueItem).filter(
            QueueItem.status == "waiting",
            QueueItem.target_user == username,
            QueueItem.username != username,
        )
    ).all()

    items = [_item_to_dict(item, i + 1) for i, item in enumerate(incoming)]
    return JSONResponse({"items": items})


@router.get("/all")
async def all_queue(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    waiting = _waiting_order(
        db.query(QueueItem).filter(QueueItem.status == "waiting")
    ).all()

    items = [_item_to_dict(item, i + 1) for i, item in enumerate(waiting)]

    return JSONResponse({"items": items})


@router.get("/completed")
async def all_completed(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    completed = (
        db.query(QueueItem)
        .filter(QueueItem.status == "completed")
        .order_by(QueueItem.completed_at.desc())
        .all()
    )

    items = [_item_to_dict(item) for item in completed]

    return JSONResponse({"items": items})


@router.get("/credits")
async def get_credits(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    return JSONResponse({"credits": _get_credits(db, username)})


@router.post("/{item_id}/comment")
async def add_comment(
    request: Request,
    item_id: int,
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    item = (
        db.query(QueueItem)
        .filter(QueueItem.id == item_id, QueueItem.username == username)
        .first()
    )
    if not item:
        return JSONResponse({"error": "not found"}, status_code=404)

    comment = Comment(item_id=item_id, username=username, text=text)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    await event_bus.broadcast("comment_added")
    await event_bus.broadcast("notification", f"{item.username}:comment")

    return JSONResponse({"ok": True, "comment": _comment_to_dict(comment)})
