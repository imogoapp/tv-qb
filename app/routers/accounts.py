"""Login, logout e "Minha conta" (perfil, senha e preferencias)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .. import auth
from ..core.templating import redirect, render, render_bare

router = APIRouter()


# ---------------------------------------------------------------------- login e logout

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/") -> Response:
    target = auth.safe_next(next)
    if auth.current_user(request):
        return RedirectResponse(target, status_code=303)
    return render_bare(request, "login.html", next=target, error=None, username="")


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
    remember: str = Form(""),
) -> Response:
    target = auth.safe_next(next)
    result = auth.attempt_login(
        username,
        password,
        auth.client_ip(request),
        request.headers.get("user-agent", ""),
        remember == "1",
    )
    if result.token:
        response = RedirectResponse(target, status_code=303)
        auth.set_session_cookie(response, result.token, remember == "1")
        return response
    if result.error == "locked":
        minutes = max(1, -(-result.retry_after // 60))
        message = f"Muitas tentativas. Tente novamente em {minutes} min."
        status = 429
    else:
        message = "Usuário ou senha incorretos."
        status = 401
    return render_bare(request, "login.html", status_code=status, next=target, error=message, username=username.strip()[:64])


@router.post("/logout")
def logout(request: Request) -> Response:
    auth.destroy_session(request.cookies.get(auth.SESSION_COOKIE))
    response = RedirectResponse("/login", status_code=303)
    auth.clear_session_cookie(response)
    return response


@router.get("/logout")
def logout_get() -> Response:
    # Sair muda o estado, entao so vale por POST (botao "Sair"); quem digita o link cai no painel.
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------------- minha conta

@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request) -> Response:
    return render(
        request,
        "account.html",
        layout_labels=auth.LAYOUT_LABELS,
        layout_choices=auth.PREFERENCE_CHOICES["layout"],
        role_description=auth.ROLE_DESCRIPTIONS[request.state.user.role],
        min_password=auth.MIN_PASSWORD_LENGTH,
    )


@router.post("/account/profile")
def account_profile(request: Request, display_name: str = Form("")) -> Response:
    auth.update_profile(request.state.user.id, display_name)
    return redirect("/account", ok="profile_saved")


@router.post("/account/password")
def account_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
) -> Response:
    if new_password != confirm_password:
        return redirect("/account", err="mismatch")
    error = auth.change_password(request.state.user, current_password, new_password)
    if error:
        return redirect("/account", err=error)
    return redirect("/account", ok="password_changed")


@router.post("/account/preferences")
def account_preferences(request: Request, layout: str = Form(""), next: str = Form("")) -> Response:
    if not auth.set_preference(request.state.user.id, "layout", layout):
        return redirect("/account", err="bad_layout")
    # Com `next` volta para a mesma pagina; vindo da tela de conta, mostra o aviso.
    if next:
        return RedirectResponse(auth.safe_next(next), status_code=303)
    return redirect("/account", ok="prefs_saved")
