import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import func

from app.config import settings
from app.database import init_db, get_db
from app.models import QueueItem
from app.auth import router as auth_router, get_current_user
from app.routers.queue import router as queue_router
from app.routers.admin import router as admin_router
from app.routers.partials import router as partials_router
from app.sse import event_bus


templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.include_router(auth_router)
app.include_router(queue_router)
app.include_router(admin_router)
app.include_router(partials_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root(request: Request):
    username = get_current_user(request)
    if username:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "app_name": settings.APP_NAME},
    )


@app.get("/dashboard")
async def dashboard(request: Request, db=Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    all_waiting = (
        db.query(QueueItem)
        .filter(QueueItem.status == "waiting")
        .order_by(
            func.coalesce(QueueItem.queue_order, 999999), QueueItem.created_at.asc()
        )
        .all()
    )

    global_position = None
    for idx, item in enumerate(all_waiting, 1):
        if item.username == username:
            global_position = idx
            break

    my_items = (
        db.query(QueueItem)
        .filter(QueueItem.username == username)
        .order_by(QueueItem.created_at.desc())
        .all()
    )

    for item in my_items:
        if item.status == "waiting":
            item.position = next(
                (i for i, w in enumerate(all_waiting, 1) if w.id == item.id), None
            )

    is_admin = username == settings.ADMIN_USERNAME

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "username": username,
            "my_items": my_items,
            "global_position": global_position,
            "is_admin": is_admin,
            "app_name": settings.APP_NAME,
            "admin_username": settings.ADMIN_USERNAME,
        },
    )


@app.get("/events")
async def sse_events(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    q = event_bus.connect()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(q.get(), timeout=30)
                    yield message
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.disconnect(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
