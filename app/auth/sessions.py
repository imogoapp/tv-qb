"""Usuario atual, sessoes no servidor (cookie com token aleatorio; o banco guarda so o hash) e preferencias."""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response

from .db import users_db
from .settings import (
    PREFERENCE_CHOICES,
    REMEMBER_DAYS,
    ROLE_LABELS,
    ROLE_RANK,
    SESSION_COOKIE,
    SESSION_HOURS,
)


@dataclass
class CurrentUser:
    id: int
    username: str
    display_name: str
    role: str
    must_change_password: bool
    layout: str = "side"
    session_hash: str = ""

    @property
    def rank(self) -> int:
        return ROLE_RANK.get(self.role, 0)

    @property
    def initial(self) -> str:
        return (self.display_name or self.username or "?").strip()[:1].upper()

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_preferences(user_id: int) -> dict[str, str]:
    prefs = {key: choices[0] for key, choices in PREFERENCE_CHOICES.items()}
    with users_db() as conn:
        rows = conn.execute("SELECT key, value FROM user_preferences WHERE user_id = ?", (user_id,)).fetchall()
    for row in rows:
        if row["key"] in PREFERENCE_CHOICES and row["value"] in PREFERENCE_CHOICES[row["key"]]:
            prefs[row["key"]] = row["value"]
    return prefs


def set_preference(user_id: int, key: str, value: str) -> bool:
    if key not in PREFERENCE_CHOICES or value not in PREFERENCE_CHOICES[key]:
        return False
    with users_db() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (user_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
            """,
            (user_id, key, value),
        )
        conn.commit()
    return True


def user_from_token(token: str | None) -> CurrentUser | None:
    if not token:
        return None
    token_hash = _hash_token(token)
    with users_db() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.display_name, u.role, u.must_change_password
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1
            """,
            (token_hash, int(time.time())),
        ).fetchone()
    if row is None:
        return None
    prefs = get_preferences(row["id"])
    return CurrentUser(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
        must_change_password=bool(row["must_change_password"]),
        layout=prefs["layout"],
        session_hash=token_hash,
    )


def current_user(request: Request) -> CurrentUser | None:
    """Usuario logado na requisicao (ou None). O resultado fica guardado na propria requisicao."""
    if hasattr(request.state, "user"):
        return request.state.user
    user = user_from_token(request.cookies.get(SESSION_COOKIE))
    request.state.user = user
    return user


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


# --------------------------------------------------------------------------- sessoes e login


def create_session(user_id: int, remember: bool, ip: str, user_agent: str) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    lifetime = REMEMBER_DAYS * 86400 if remember else SESSION_HOURS * 3600
    with users_db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)",
            (_hash_token(token), user_id, now, now + lifetime, ip, user_agent[:200]),
        )
        conn.commit()
    return token


def set_session_cookie(response: Response, token: str, remember: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=REMEMBER_DAYS * 86400 if remember else None,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def destroy_session(token: str | None) -> None:
    if not token:
        return
    with users_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
        conn.commit()


def destroy_user_sessions(user_id: int, keep_hash: str | None = None) -> None:
    with users_db() as conn:
        if keep_hash:
            conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, keep_hash))
        else:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
