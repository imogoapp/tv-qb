"""Tratamento dos erros de acesso: sem login vai para /login; sem permissao mostra a pagina 403."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response

from .. import auth
from .templating import render


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(auth.LoginRequired)
    def handle_login_required(request: Request, exc: auth.LoginRequired) -> Response:
        return RedirectResponse(auth.login_url(exc.next_url), status_code=303)

    @app.exception_handler(auth.Forbidden)
    def handle_forbidden(request: Request, exc: auth.Forbidden) -> Response:
        role = request.state.user.role
        return render(
            request,
            "error.html",
            status_code=403,
            code=403,
            title="Sem permissão",
            message=(
                f"Seu perfil ({auth.ROLE_LABELS.get(role, role)}) "
                f"não permite esta ação. É preciso ser {auth.ROLE_LABELS[exc.needed_role]} ou superior."
            ),
        )
