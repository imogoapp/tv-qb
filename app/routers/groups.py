"""Grupos de TVs."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from ..controllers import groups
from ..core.templating import redirect, render

router = APIRouter()


@router.get("/groups", response_class=HTMLResponse)
def groups_page(request: Request) -> Response:
    return render(request, "groups.html", base_url=str(request.base_url).rstrip("/"), **groups.page_data())


@router.post("/groups")
def create_group(name: str = Form(...), slug: str = Form(""), playlist_id: str = Form("")) -> Response:
    error = groups.create(name, slug, playlist_id)
    return redirect("/groups", err=error) if error else redirect("/groups", ok="group_created")


@router.post("/groups/{group_id}/update")
def update_group(group_id: int, name: str = Form(...), slug: str = Form(""), playlist_id: str = Form("")) -> Response:
    error = groups.update(group_id, name, slug, playlist_id)
    return redirect("/groups", err=error) if error else redirect("/groups", ok="group_saved")


@router.post("/groups/{group_id}/delete")
def delete_group(group_id: int) -> Response:
    groups.delete(group_id)
    return redirect("/groups", ok="group_deleted")
