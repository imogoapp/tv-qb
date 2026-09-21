"""Paginas de exibicao (abertas nas TVs, sem login) e a API que elas consultam.

Cada tipo de item tem o proprio prefixo de URL, entao o mesmo slug pode existir em tipos diferentes
sem conflito. No singular ficam as paginas de exibicao; no plural, as telas de administracao
(/screens, /groups, /playlists, /library).

  /player/<slug>    -> TV (tela cadastrada)
  /group/<slug>     -> grupo de TVs
  /playlist/<slug>  -> playlist
  /video/<slug>     -> um unico video, em loop
  /image/<slug>     -> uma unica imagem
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ..controllers import player
from ..core.config import PLAYER_KINDS
from ..core.templating import render_bare
from ..core.utils import now_ms

router = APIRouter()


def _render_player(request: Request, kind: str, slug: str) -> Response:
    legacy = player.legacy_redirect(kind, slug)
    if legacy:
        return RedirectResponse(legacy, status_code=307)
    return render_bare(request, "player.html", kind=kind, slug=slug, player_path=f"/{kind}/{slug}")


@router.get("/player/{slug}", response_class=HTMLResponse)
def player_screen(request: Request, slug: str) -> Response:
    return _render_player(request, "player", slug)


@router.get("/group/{slug}", response_class=HTMLResponse)
def player_group(request: Request, slug: str) -> Response:
    return _render_player(request, "group", slug)


@router.get("/playlist/{slug}", response_class=HTMLResponse)
def player_playlist(request: Request, slug: str) -> Response:
    return _render_player(request, "playlist", slug)


@router.get("/video/{slug}", response_class=HTMLResponse)
def player_video(request: Request, slug: str) -> Response:
    return _render_player(request, "video", slug)


@router.get("/image/{slug}", response_class=HTMLResponse)
def player_image(request: Request, slug: str) -> Response:
    return _render_player(request, "image", slug)


@router.get("/api/time")
def api_time() -> JSONResponse:
    return JSONResponse({"server_time_ms": now_ms()}, headers={"Cache-Control": "no-store"})


@router.get("/api/{kind}/{slug}/state")
def api_player_state(kind: str, slug: str) -> JSONResponse:
    if kind not in PLAYER_KINDS:
        raise HTTPException(status_code=404)
    return JSONResponse(player.player_state(kind, slug), headers={"Cache-Control": "no-store"})
