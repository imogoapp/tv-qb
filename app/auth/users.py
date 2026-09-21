"""Gestao de usuarios: criar, editar, excluir, perfil e troca de senha."""

from __future__ import annotations

import sqlite3
from typing import Any

from .db import now_iso, users_db
from .passwords import hash_password, password_problem, verify_password
from .sessions import CurrentUser, destroy_user_sessions
from .settings import ROLE_RANK, ROLES, USERNAME_PATTERN


def can_manage(actor: CurrentUser, target_role: str, target_id: int | None = None) -> bool:
    """Root gerencia todos; admin gerencia apenas roles abaixo do dele. Ninguem gerencia a si mesmo aqui."""
    if target_id is not None and target_id == actor.id:
        return False
    if actor.role == "root":
        return True
    return actor.rank > ROLE_RANK.get(target_role, 99)


def assignable_roles(actor: CurrentUser) -> list[str]:
    if actor.role == "root":
        return list(ROLES)
    return [role for role in ROLES if ROLE_RANK[role] < actor.rank]


def list_users() -> list[dict[str, Any]]:
    with users_db() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.display_name, u.role, u.active, u.must_change_password,
                   u.created_at, u.last_login_at,
                   COALESCE(p.value, 'side') AS layout
            FROM users u
            LEFT JOIN user_preferences p ON p.user_id = u.id AND p.key = 'layout'
            ORDER BY CASE u.role WHEN 'root' THEN 0 WHEN 'admin' THEN 1 WHEN 'user' THEN 2 ELSE 3 END,
                     u.username COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_user(user_id: int) -> dict[str, Any] | None:
    with users_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def _active_roots(conn: sqlite3.Connection, exclude_id: int | None = None) -> int:
    sql = "SELECT COUNT(*) AS total FROM users WHERE role = 'root' AND active = 1"
    params: tuple[Any, ...] = ()
    if exclude_id is not None:
        sql += " AND id != ?"
        params = (exclude_id,)
    return conn.execute(sql, params).fetchone()["total"]


def create_user(actor: CurrentUser, username: str, display_name: str, password: str, role: str) -> str | None:
    """Cria um usuario. Devolve um codigo de erro ou None se deu certo."""
    username = username.strip().lower()
    if not USERNAME_PATTERN.match(username):
        return "bad_username"
    if role not in assignable_roles(actor):
        return "bad_role"
    if password_problem(password, username):
        return "weak_password"
    stamp = now_iso()
    try:
        with users_db() as conn:
            conn.execute(
                """
                INSERT INTO users (username, display_name, password_hash, role, active,
                                   must_change_password, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (username, display_name.strip()[:80] or username, hash_password(password), role, stamp, stamp),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return "username_taken"
    return None


def update_user(
    actor: CurrentUser,
    user_id: int,
    display_name: str,
    role: str,
    active: bool,
    new_password: str,
) -> str | None:
    target = get_user(user_id)
    if target is None:
        return "not_found"
    if not can_manage(actor, target["role"], target["id"]):
        return "forbidden"
    if role not in assignable_roles(actor):
        return "bad_role"
    if new_password and password_problem(new_password, target["username"]):
        return "weak_password"

    with users_db() as conn:
        # Nunca deixa o sistema sem nenhum root ativo.
        leaving_root = target["role"] == "root" and (role != "root" or not active)
        if leaving_root and _active_roots(conn, exclude_id=user_id) == 0:
            return "last_root"
        fields = ["display_name = ?", "role = ?", "active = ?", "updated_at = ?"]
        params: list[Any] = [display_name.strip()[:80] or target["username"], role, 1 if active else 0, now_iso()]
        if new_password:
            fields += ["password_hash = ?", "must_change_password = 1"]
            params.append(hash_password(new_password))
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    # Senha nova, conta desativada ou role diferente: derruba as sessoes abertas dele.
    if new_password or not active or role != target["role"]:
        destroy_user_sessions(user_id)
    return None


def delete_user(actor: CurrentUser, user_id: int) -> str | None:
    target = get_user(user_id)
    if target is None:
        return "not_found"
    if not can_manage(actor, target["role"], target["id"]):
        return "forbidden"
    with users_db() as conn:
        if target["role"] == "root" and target["active"] and _active_roots(conn, exclude_id=user_id) == 0:
            return "last_root"
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    return None


def update_profile(user_id: int, display_name: str) -> None:
    with users_db() as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return
        conn.execute(
            "UPDATE users SET display_name = ?, updated_at = ? WHERE id = ?",
            (display_name.strip()[:80] or row["username"], now_iso(), user_id),
        )
        conn.commit()


def change_password(user: CurrentUser, current_password: str, new_password: str) -> str | None:
    with users_db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()
        if row is None or not verify_password(current_password, row["password_hash"]):
            return "wrong_password"
        if password_problem(new_password, user.username):
            return "weak_password"
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = ? WHERE id = ?",
            (hash_password(new_password), now_iso(), user.id),
        )
        conn.commit()
    # Mantem so a sessao atual; as outras (outros aparelhos) precisam entrar de novo.
    destroy_user_sessions(user.id, keep_hash=user.session_hash)
    return None
