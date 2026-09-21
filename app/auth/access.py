"""Quem pode acessar o que: rotas publicas, role minima de cada rota, guard global e `next` seguro."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import Request

from .sessions import CurrentUser, current_user
from .settings import ROLE_RANK


def safe_next(target: str | None) -> str:
    """So aceita caminhos internos (evita redirecionar o usuario para outro site depois do login)."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/"
    if target.startswith("/login") or target.startswith("/logout"):
        return "/"
    return target


# --------------------------------------------------------------------------- permissoes

# Telas de exibicao (abertas nas TVs, sem login) e arquivos usados por elas.
PUBLIC_PREFIXES = ("/player/", "/group/", "/playlist/", "/video/", "/image/", "/api/", "/static/", "/media/")
PUBLIC_PATHS = {"/login", "/logout", "/favicon.ico"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def required_role(method: str, path: str) -> str | None:
    """Menor role que pode acessar `method path`. None = publico (sem login)."""
    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return None
    if path == "/users" or path.startswith("/users/"):
        return "admin"
    if path == "/account" or path.startswith("/account/"):
        return "viewer"
    if method.upper() in SAFE_METHODS:
        return "viewer"
    if path.startswith(("/library", "/playlists")):
        return "user"
    # TVs, grupos e qualquer outra acao de escrita nova: so admin ou root.
    return "admin"


def permissions(user: CurrentUser | None) -> dict[str, bool]:
    rank = user.rank if user else 0
    return {
        "media": rank >= ROLE_RANK["user"],
        "playlists": rank >= ROLE_RANK["user"],
        "screens": rank >= ROLE_RANK["admin"],
        "groups": rank >= ROLE_RANK["admin"],
        "users": rank >= ROLE_RANK["admin"],
    }


class LoginRequired(Exception):
    def __init__(self, next_url: str) -> None:
        self.next_url = next_url


class Forbidden(Exception):
    def __init__(self, needed_role: str) -> None:
        self.needed_role = needed_role


def guard(request: Request) -> None:
    """Dependencia global: bloqueia o que nao e publico para quem nao esta logado ou nao tem permissao."""
    needed = required_role(request.method, request.url.path)
    if needed is None:
        return
    user = current_user(request)
    if user is None:
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise LoginRequired(target if request.method.upper() in SAFE_METHODS else "/")
    if user.rank < ROLE_RANK[needed]:
        raise Forbidden(needed)


def login_url(next_url: str) -> str:
    next_url = safe_next(next_url)
    return "/login" if next_url == "/" else f"/login?next={quote(next_url, safe='')}"
