from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import QueueItem

router = APIRouter(prefix="/queue")


def _item_to_dict(item, position=None):
    return {
        "id": item.id,
        "subject": item.subject,
        "description": item.description,
        "status": item.status,
        "created_at": item.created_at.strftime("%d.%m.%Y %H:%M"),
        "position": position,
    }


@router.post("/add")
async def add_to_queue(
    request: Request,
    subject: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    item = QueueItem(username=username, subject=subject, description=description)
    db.add(item)
    db.commit()
    db.refresh(item)

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        all_waiting = (
            db.query(QueueItem)
            .filter(QueueItem.status == "waiting")
            .order_by(QueueItem.created_at.asc())
            .all()
        )
        position = next(
            (i for i, w in enumerate(all_waiting, 1) if w.id == item.id), None
        )
        return JSONResponse({"ok": True, "item": _item_to_dict(item, position)})

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
    if item and item.status == "waiting":
        db.delete(item)
        db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"ok": True})

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/my")
async def my_queue(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    all_waiting = (
        db.query(QueueItem)
        .filter(QueueItem.status == "waiting")
        .order_by(QueueItem.created_at.asc())
        .all()
    )

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

    return JSONResponse(
        {
            "items": items,
            "global_position": global_position,
        }
    )
