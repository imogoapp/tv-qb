"""Gestao de usuarios (admin e root)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from .. import auth
from ..core.templating import redirect, render

router = APIRouter()


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request) -> Response:
    actor = request.state.user
    users = auth.list_users()
    for row in users:
        row["manageable"] = auth.can_manage(actor, row["role"], row["id"])
        row["is_me"] = row["id"] == actor.id
    return render(
        request,
        "users.html",
        users=users,
        roles=auth.ROLES,
        role_labels=auth.ROLE_LABELS,
        role_descriptions=auth.ROLE_DESCRIPTIONS,
        assignable=auth.assignable_roles(actor),
        layout_labels=auth.LAYOUT_LABELS,
        min_password=auth.MIN_PASSWORD_LENGTH,
    )


@router.post("/users")
def users_create(
    request: Request,
    username: str = Form(""),
    display_name: str = Form(""),
    password: str = Form(""),
    role: str = Form("viewer"),
) -> Response:
    error = auth.create_user(request.state.user, username, display_name, password, role)
    return redirect("/users", err=error) if error else redirect("/users", ok="user_created")


@router.post("/users/{user_id}/update")
def users_update(
    request: Request,
    user_id: int,
    display_name: str = Form(""),
    role: str = Form("viewer"),
    active: str = Form("0"),
    new_password: str = Form(""),
) -> Response:
    error = auth.update_user(request.state.user, user_id, display_name, role, active == "1", new_password)
    return redirect("/users", err=error) if error else redirect("/users", ok="user_saved")


@router.post("/users/{user_id}/delete")
def users_delete(request: Request, user_id: int) -> Response:
    error = auth.delete_user(request.state.user, user_id)
    return redirect("/users", err=error) if error else redirect("/users", ok="user_deleted")
