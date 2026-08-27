from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from backend.errors import AppError
from backend.responses import ok

COOKIE_NAME = "db_console_session"


class LoginRequest(BaseModel):
    username: str
    password: str


def _signature(username: str) -> str:
    secret = os.getenv("SESSION_SECRET", "change-this-session-secret")
    payload = f"{username}:{int(time.time()) // 86400}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def make_token(username: str) -> str:
    return f"{username}:{_signature(username)}"


def verify_token(token: str | None) -> bool:
    if not token or ":" not in token:
        return False
    username, signature = token.split(":", 1)
    expected_username = os.getenv("AUTH_USERNAME", "admin")
    return hmac.compare_digest(username, expected_username) and any(
        hmac.compare_digest(signature, _signature(username))
        for _ in (0,)
    )


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, response: Response):
    expected_username = os.getenv("AUTH_USERNAME", "admin")
    expected_password = os.getenv("AUTH_PASSWORD", "admin123")
    if not hmac.compare_digest(body.username, expected_username) or not hmac.compare_digest(body.password, expected_password):
        raise AppError(401, "INVALID_CREDENTIALS", "用户名或密码错误")
    response.set_cookie(COOKIE_NAME, make_token(expected_username), httponly=True, samesite="lax", max_age=86400 * 7)
    return ok({"username": expected_username})


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return ok({"logged_out": True})


@router.get("/me")
def me():
    return ok({"username": os.getenv("AUTH_USERNAME", "admin")})
