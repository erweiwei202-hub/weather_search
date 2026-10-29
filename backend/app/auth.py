from __future__ import annotations

import asyncio
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, Response

from .config import Settings


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id; the original password is never persisted."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


async def get_optional_user(request: Request) -> Optional[dict[str, Any]]:
    token = request.cookies.get(request.app.state.settings.session_cookie_name)
    if not token:
        return None

    auth_store = request.app.state.auth_store
    return await asyncio.to_thread(auth_store.get_user_by_session, token)


async def get_current_user(request: Request) -> dict[str, Any]:
    user = await get_optional_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="请先登录",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user
