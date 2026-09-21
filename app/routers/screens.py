"""TVs cadastradas."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from ..controllers import screens
from ..core.templating import redirect, render

router = APIRouter()


@router.get("/screens", response_class=HTMLResponse)
def screens_page(request: Request) -> Response:
    return render(request, "screens.html", base_url=str(request.base_url).rstrip("/"), **screens.page_data())


@router.post("/screens")
def create_screen(
    name: str = Form(...),
    slug: str = Form(""),
    group_id: str = Form(""),
    playlist_id: str = Form(""),
) -> Response:
    error = screens.create(name, slug, group_id, playlist_id)
    return redirect("/screens", err=error) if error else redirect("/screens", ok="screen_created")


@router.post("/screens/{screen_id}/update")
def update_screen(
    screen_id: int,
    name: str = Form(...),
    slug: str = Form(""),
    group_id: str = Form(""),
    playlist_id: str = Form(""),
    enabled: str = Form("0"),
) -> Response:
    error = screens.update(screen_id, name, slug, group_id, playlist_id, enabled == "1")
    return redirect("/screens", err=error) if error else redirect("/screens", ok="screen_saved")


@router.post("/screens/{screen_id}/delete")
def delete_screen(screen_id: int) -> Response:
    screens.delete(screen_id)
    return redirect("/screens", ok="screen_deleted")
