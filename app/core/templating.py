"""Templates Jinja: contexto comum das paginas do painel e atalhos para renderizar e redirecionar."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .. import auth
from ..models import stats
from .config import TEMPLATES_DIR
from .notices import notice_from

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def common_context(request: Request) -> dict[str, Any]:
    """Dados que todas as paginas do painel usam (menu, permissoes, aviso, contadores)."""
    user = auth.current_user(request)
    return {
        "request": request,
        "path": request.url.path,
        "user": user,
        "can": auth.permissions(user),
        "layout": user.layout if user else "side",
        "role_labels": auth.ROLE_LABELS,
        "notice": notice_from(request),
        **stats.counts(),
    }


def render(request: Request, name: str, status_code: int = 200, **context: Any) -> Response:
    """Renderiza uma pagina do painel (com o contexto comum)."""
    return templates.TemplateResponse(request, name, {**common_context(request), **context}, status_code=status_code)


def render_bare(request: Request, name: str, status_code: int = 200, **context: Any) -> Response:
    """Renderiza uma pagina publica (login, player), sem o contexto do painel."""
    return templates.TemplateResponse(request, name, {"request": request, **context}, status_code=status_code)


def redirect(path: str, ok: str | None = None, err: str | None = None) -> RedirectResponse:
    """Redireciona (303) para `path`, opcionalmente com um aviso (`?ok=codigo` ou `?err=codigo`)."""
    if ok:
        path += f"?ok={ok}"
    elif err:
        path += f"?err={err}"
    return RedirectResponse(path, status_code=303)
