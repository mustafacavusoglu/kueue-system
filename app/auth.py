import logging
from typing import Optional

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

oauth = OAuth()
oauth.register(
    name="openshift",
    client_id=settings.OPENSHIFT_OAUTH_CLIENT_ID,
    client_secret=settings.OPENSHIFT_OAUTH_CLIENT_SECRET,
    authorize_url=settings.authorize_url,
    access_token_url=settings.token_url,
    client_kwargs={"scope": settings.OPENSHIFT_OAUTH_SCOPE},
)


def get_current_user(request: Request) -> Optional[str]:
    return request.session.get("username")


@router.get("/login")
async def login(request: Request):
    redirect_uri = f"{settings.APP_URL}/auth/callback"
    try:
        return await oauth.openshift.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(f"Login redirect error: {e}")
        return RedirectResponse(url="/", status_code=303)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        code = request.query_params.get("code")
        if not code:
            return RedirectResponse(url="/", status_code=303)

        async with httpx.AsyncClient(verify=False) as client:
            token_resp = await client.post(
                settings.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.OPENSHIFT_OAUTH_CLIENT_ID,
                    "client_secret": settings.OPENSHIFT_OAUTH_CLIENT_SECRET,
                    "redirect_uri": f"{settings.APP_URL}/auth/callback",
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            user_resp = await client.get(
                settings.user_api_url,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            user_resp.raise_for_status()
            user_info = user_resp.json()

        username = user_info.get("metadata", {}).get("name") or user_info.get("name")
        logger.info(f"Logged in user: {username}")
        if username:
            request.session["username"] = username
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        logger.error(f"Auth callback error: {e}", exc_info=True)
        return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
