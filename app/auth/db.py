"""Conexao com o banco de usuarios (users.db) e criacao das tabelas."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

from .passwords import hash_password
from .settings import DEFAULT_PASSWORD, DEFAULT_USERNAME, USERS_DB_PATH


def users_db() -> sqlite3.Connection:
    conn = sqlite3.connect(USERS_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_users_db() -> None:
    """Cria as tabelas de usuarios e, se nao houver nenhum usuario, o admin padrao."""
    with users_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('viewer', 'user', 'admin', 'root')),
                active INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                ip TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS login_attempts (
                key TEXT PRIMARY KEY,
                failures INTEGER NOT NULL,
                first_at INTEGER NOT NULL,
                locked_until INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        total = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if total == 0:
            stamp = now_iso()
            conn.execute(
                """
                INSERT INTO users (username, display_name, password_hash, role, active,
                                   must_change_password, created_at, updated_at)
                VALUES (?, ?, ?, 'root', 1, 1, ?, ?)
                """,
                (DEFAULT_USERNAME, "Administrador", hash_password(DEFAULT_PASSWORD), stamp, stamp),
            )
        conn.commit()
