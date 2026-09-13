from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_conn

router = APIRouter()


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def _make_token() -> str:
    return secrets.token_urlsafe(32)


def resolve_user_id(request: Request) -> str:
    """Extract user_id from request state (set by middleware). Falls back to 'default'."""
    return getattr(request.state, "user_id", "default")


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/api/auth/register")
async def register(req: AuthRequest):
    if len(req.username) < 2:
        raise HTTPException(422, "用户名至少 2 位")
    if len(req.password) < 4:
        raise HTTPException(422, "密码至少 4 位")

    salt = secrets.token_hex(16)
    pw_hash = f"{salt}:{_hash(req.password, salt)}"
    user_id = secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, req.username.strip(), pw_hash, now),
        )
        conn.commit()
    except Exception:
        raise HTTPException(400, "用户名已存在")

    token = _make_token()
    conn.execute(
        "INSERT INTO auth_tokens (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user_id, now),
    )
    conn.commit()
    return {"token": token, "user_id": user_id, "username": req.username.strip()}


@router.post("/api/auth/login")
async def login(req: AuthRequest):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username=?",
        (req.username.strip(),),
    ).fetchone()
    if not row:
        raise HTTPException(401, "用户名或密码错误")

    salt, key_hex = row["password_hash"].split(":", 1)
    if _hash(req.password, salt) != key_hex:
        raise HTTPException(401, "用户名或密码错误")

    token = _make_token()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO auth_tokens (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, row["id"], now),
    )
    conn.commit()
    return {"token": token, "user_id": row["id"], "username": req.username.strip()}


@router.get("/api/auth/me")
async def get_me(request: Request):
    user_id = resolve_user_id(request)
    if user_id == "default":
        raise HTTPException(401, "未登录")
    row = get_conn().execute(
        "SELECT username FROM users WHERE id=?", (user_id,)
    ).fetchone()
    if not row:
        raise HTTPException(401, "token 无效")
    return {"user_id": user_id, "username": row["username"]}
