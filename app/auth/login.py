"""Tentativa de login com bloqueio temporario depois de varias senhas erradas."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from .db import now_iso, users_db
from .passwords import burn_time, verify_password
from .sessions import create_session
from .settings import ATTEMPT_WINDOW_SECONDS, LOCK_SECONDS, MAX_FAILURES_PER_IP, MAX_FAILURES_PER_USER


@dataclass
class LoginResult:
    token: str | None = None
    error: str | None = None  # "invalid" | "locked"
    retry_after: int = 0


def _lock_remaining(conn: sqlite3.Connection, key: str, now: int) -> int:
    row = conn.execute("SELECT locked_until FROM login_attempts WHERE key = ?", (key,)).fetchone()
    if row and row["locked_until"] > now:
        return int(row["locked_until"] - now)
    return 0


def _register_failure(conn: sqlite3.Connection, key: str, limit: int, now: int) -> None:
    row = conn.execute("SELECT failures, first_at FROM login_attempts WHERE key = ?", (key,)).fetchone()
    if row is None or now - row["first_at"] > ATTEMPT_WINDOW_SECONDS:
        failures, first_at = 1, now
    else:
        failures, first_at = row["failures"] + 1, row["first_at"]
    locked_until = now + LOCK_SECONDS if failures >= limit else 0
    conn.execute(
        """
        INSERT INTO login_attempts (key, failures, first_at, locked_until) VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET failures = excluded.failures, first_at = excluded.first_at,
                                       locked_until = excluded.locked_until
        """,
        (key, failures, first_at, locked_until),
    )


def attempt_login(username: str, password: str, ip: str, user_agent: str, remember: bool) -> LoginResult:
    username = username.strip().lower()[:64]
    user_key = f"user:{username}|{ip}"
    ip_key = f"ip:{ip}"
    now = int(time.time())

    with users_db() as conn:
        remaining = max(_lock_remaining(conn, user_key, now), _lock_remaining(conn, ip_key, now))
        if remaining:
            return LoginResult(error="locked", retry_after=remaining)

        row = conn.execute(
            "SELECT id, password_hash, active FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            burn_time()
            valid = False
        else:
            valid = verify_password(password, row["password_hash"]) and bool(row["active"])

        if not valid:
            _register_failure(conn, user_key, MAX_FAILURES_PER_USER, now)
            _register_failure(conn, ip_key, MAX_FAILURES_PER_IP, now)
            conn.commit()
            return LoginResult(error="invalid")

        conn.execute("DELETE FROM login_attempts WHERE key = ?", (user_key,))
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso(), row["id"]))
        conn.commit()
        user_id = row["id"]

    token = create_session(user_id, remember, ip, user_agent)
    return LoginResult(token=token)
