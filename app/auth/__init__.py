"""Autenticacao, sessoes, papeis (roles) e preferencias de cada usuario.

Tudo aqui fica em um banco proprio, `app/users.db`, separado do `signage.db` (que guarda TVs,
grupos, midias e playlists). Assim da para apagar, copiar ou fazer backup de um sem tocar no outro.

Organizacao do pacote:
- settings.py   constantes: roles, cookie, limites, caminho do users.db
- db.py         conexao com o users.db e criacao das tabelas (+ admin padrao)
- passwords.py  hash (scrypt) e regras de senha
- sessions.py   usuario atual, cookie de sessao, preferencias
- login.py      tentativa de login com bloqueio temporario
- access.py     quem pode acessar o que (roles, guard global, redirecionamento seguro)
- users.py      gestao de usuarios (criar, editar, excluir, perfil, trocar senha)

O resto do sistema usa so o que esta exportado aqui: `from app import auth` e `auth.guard`, `auth.current_user`...
"""

from __future__ import annotations

from .access import (
    PUBLIC_PATHS,
    PUBLIC_PREFIXES,
    Forbidden,
    LoginRequired,
    guard,
    login_url,
    permissions,
    required_role,
    safe_next,
)
from .db import init_users_db, users_db
from .login import LoginResult, attempt_login
from .passwords import hash_password, password_problem, verify_password
from .sessions import (
    CurrentUser,
    clear_session_cookie,
    client_ip,
    create_session,
    current_user,
    destroy_session,
    destroy_user_sessions,
    get_preferences,
    set_preference,
    set_session_cookie,
    user_from_token,
)
from .settings import (
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    LAYOUT_LABELS,
    MIN_PASSWORD_LENGTH,
    PREFERENCE_CHOICES,
    ROLE_DESCRIPTIONS,
    ROLE_LABELS,
    ROLE_RANK,
    ROLES,
    SESSION_COOKIE,
    USERS_DB_PATH,
)
from .users import (
    assignable_roles,
    can_manage,
    change_password,
    create_user,
    delete_user,
    get_user,
    list_users,
    update_profile,
    update_user,
)

__all__ = [
    "CurrentUser",
    "DEFAULT_PASSWORD",
    "DEFAULT_USERNAME",
    "Forbidden",
    "LAYOUT_LABELS",
    "LoginRequired",
    "LoginResult",
    "MIN_PASSWORD_LENGTH",
    "PREFERENCE_CHOICES",
    "PUBLIC_PATHS",
    "PUBLIC_PREFIXES",
    "ROLES",
    "ROLE_DESCRIPTIONS",
    "ROLE_LABELS",
    "ROLE_RANK",
    "SESSION_COOKIE",
    "USERS_DB_PATH",
    "assignable_roles",
    "attempt_login",
    "can_manage",
    "change_password",
    "clear_session_cookie",
    "client_ip",
    "create_session",
    "create_user",
    "current_user",
    "delete_user",
    "destroy_session",
    "destroy_user_sessions",
    "get_preferences",
    "get_user",
    "guard",
    "hash_password",
    "init_users_db",
    "list_users",
    "login_url",
    "password_problem",
    "permissions",
    "required_role",
    "safe_next",
    "set_preference",
    "set_session_cookie",
    "update_profile",
    "update_user",
    "user_from_token",
    "users_db",
    "verify_password",
]
