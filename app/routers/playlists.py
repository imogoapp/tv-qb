"""Playlists: listagem, edicao da linha do tempo (arrastar e salvar) e itens."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ..controllers import playlists
from ..core.templating import redirect, render
from ..schemas.playlists import TimelineSave

router = APIRouter()


def _after_error(playlist_id: int, error: str) -> Response:
    """Playlist que sumiu volta para a lista; os outros erros voltam para a propria playlist."""
    if error == "playlist_missing":
        return redirect("/playlists", err=error)
    return redirect(f"/playlists/{playlist_id}", err=error)


@router.get("/playlists", response_class=HTMLResponse)
def playlists_page(request: Request) -> Response:
    return render(request, "playlists.html", **playlists.list_page())


@router.post("/playlists")
def create_playlist(name: str = Form(...), slug: str = Form("")) -> Response:
    playlist_id, error = playlists.create(name, slug)
    if error:
        return redirect("/playlists", err=error)
    return redirect(f"/playlists/{playlist_id}", ok="playlist_created")


@router.get("/playlists/{playlist_id}", response_class=HTMLResponse)
def edit_playlist(request: Request, playlist_id: int) -> Response:
    data = playlists.editor_page(playlist_id)
    if data is None:
        raise HTTPException(status_code=404)
    return render(request, "playlist_edit.html", **data)


@router.post("/playlists/{playlist_id}/rename")
def rename_playlist(playlist_id: int, name: str = Form(...), slug: str = Form("")) -> Response:
    error = playlists.rename(playlist_id, name, slug)
    return _after_error(playlist_id, error) if error else redirect(f"/playlists/{playlist_id}", ok="playlist_saved")


@router.post("/playlists/{playlist_id}/items")
def add_playlist_item(
    playlist_id: int,
    media_id: int = Form(...),
    duration_seconds: int = Form(30),
    play_until_end: str = Form("0"),
) -> Response:
    error = playlists.add_item(playlist_id, media_id, duration_seconds, play_until_end == "1")
    return _after_error(playlist_id, error) if error else redirect(f"/playlists/{playlist_id}", ok="item_added")


# Salva a linha do tempo inteira de uma vez (ordem, tempos, "tocar inteiro" e remocoes). Responde JSON.
@router.post("/playlists/{playlist_id}/items/save")
def save_timeline(playlist_id: int, payload: TimelineSave) -> JSONResponse:
    try:
        result = playlists.save_timeline(playlist_id, payload)
    except playlists.PlaylistError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.post("/playlists/{playlist_id}/items/{item_id}/update")
def update_playlist_item(
    playlist_id: int,
    item_id: int,
    position: int = Form(...),
    duration_seconds: int = Form(...),
    play_until_end: str = Form("0"),
) -> RedirectResponse:
    playlists.update_item(playlist_id, item_id, position, duration_seconds, play_until_end == "1")
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@router.post("/playlists/{playlist_id}/items/{item_id}/delete")
def delete_playlist_item(playlist_id: int, item_id: int) -> RedirectResponse:
    playlists.remove_item(playlist_id, item_id)
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@router.post("/playlists/{playlist_id}/resync")
def resync_playlist(playlist_id: int) -> Response:
    error = playlists.resync(playlist_id)
    return _after_error(playlist_id, error) if error else redirect(f"/playlists/{playlist_id}", ok="playlist_resynced")


@router.post("/playlists/{playlist_id}/delete")
def delete_playlist(playlist_id: int) -> Response:
    playlists.delete(playlist_id)
    return redirect("/playlists", ok="playlist_deleted")
