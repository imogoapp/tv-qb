"""O que cada TV/grupo/playlist/midia deve tocar (usado pelas paginas de exibicao e pela API do player)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..core.config import DEFAULT_IMAGE_SECONDS, DEFAULT_VIDEO_SECONDS, PLAYER_POLL_MS
from ..core.utils import now_ms
from ..models import groups as group_model
from ..models import media as media_model
from ..models import playlists as playlist_model
from ..models import screens as screen_model

NOT_FOUND_MESSAGES = {
    "player": "TV nao cadastrada.",
    "group": "Grupo nao cadastrado.",
    "playlist": "Playlist nao cadastrada.",
    "video": "Video nao cadastrado.",
    "image": "Imagem nao cadastrada.",
}


def legacy_redirect(kind: str, slug: str) -> str | None:
    """Links antigos: /player/<slug> tambem abria grupos e playlists. Devolve a rota certa, se for o caso."""
    if kind != "player" or screen_model.get_by_slug(slug):
        return None
    if group_model.get_by_slug(slug):
        return f"/group/{quote(slug)}"
    if playlist_model.get_by_slug(slug):
        return f"/playlist/{quote(slug)}"
    return None


def resolve_target(kind: str, slug: str) -> dict[str, Any] | None:
    """Encontra o que deve tocar para `kind`/`slug`. So procura no tipo pedido."""
    if kind == "player":
        screen = screen_model.get_enabled_with_group_playlist(slug)
        if screen:
            playlist_id = screen["playlist_id"] or screen["group_playlist_id"]
            return {"type": "screen", "name": screen["name"], "slug": screen["slug"], "playlist_id": playlist_id, "media_id": None}
        # Compatibilidade: TVs antigas abertas em /player/<slug> de um grupo ou playlist continuam
        # funcionando ate a pagina ser recarregada (ai o redirecionamento leva para a rota certa).
        # Uma TV com o mesmo slug sempre tem prioridade.
        if not screen_model.get_by_slug(slug):
            legacy = resolve_target("group", slug) or resolve_target("playlist", slug)
            if legacy:
                return legacy
        return None

    if kind == "group":
        group = group_model.get_by_slug(slug)
        if group:
            return {"type": "group", "name": group["name"], "slug": group["slug"], "playlist_id": group["playlist_id"], "media_id": None}
        return None

    if kind == "playlist":
        playlist = playlist_model.get_by_slug(slug)
        if playlist:
            return {"type": "playlist", "name": playlist["name"], "slug": playlist["slug"], "playlist_id": playlist["id"], "media_id": None}
        return None

    if kind in ("video", "image"):
        media = media_model.get_by_slug(slug, kind)
        if media:
            return {"type": kind, "name": media["title"], "slug": media["slug"], "playlist_id": None, "media_id": media["id"]}
        return None

    return None


def playlist_payload(playlist_id: int) -> dict[str, Any] | None:
    playlist = playlist_model.get(playlist_id)
    if not playlist:
        return None

    payload_items = []
    total_ms = 0
    for item in playlist_model.items_with_media(playlist_id):
        duration_ms = int(item["duration_seconds"]) * 1000
        total_ms += duration_ms
        payload_items.append(
            {
                "item_id": item["id"],
                "media_id": item["media_id"],
                "media_type": item["media_type"],
                "title": item["media_title"],
                "url": f"/media/{item['filename']}",
                "duration_ms": duration_ms,
                # Imagem sempre segue o tempo fixo; so video pode tocar ate o fim.
                "play_until_end": bool(item["play_until_end"]) and item["media_type"] == "video",
                "position": item["position"],
                # Video mudo em loop da mesma imagem (evita TV entrando em modo de economia de
                # energia); None quando a imagem ainda nao tem loop gerado (ou nao e imagem).
                "loop_video_url": f"/media/{item['loop_video_filename']}" if item["loop_video_filename"] else None,
            }
        )

    return {
        "id": playlist["id"],
        "name": playlist["name"],
        "slug": playlist["slug"],
        "sync_epoch_ms": playlist["sync_epoch_ms"],
        "revision_ms": playlist["revision_ms"],
        "total_duration_ms": total_ms,
        "items": payload_items,
    }


def media_payload(media_id: int) -> dict[str, Any] | None:
    """Uma unica midia como se fosse uma playlist de um item (rotas /video e /image)."""
    media = media_model.get(media_id)
    if not media:
        return None
    is_video = media["media_type"] == "video"
    fallback_seconds = DEFAULT_VIDEO_SECONDS if is_video else DEFAULT_IMAGE_SECONDS
    duration_ms = int(media["default_duration_seconds"] or fallback_seconds) * 1000
    return {
        "id": media["id"],
        "name": media["title"],
        "slug": media["slug"],
        "sync_epoch_ms": 0,
        "revision_ms": media["id"],
        "total_duration_ms": duration_ms,
        "items": [
            {
                "item_id": f"media-{media['id']}",
                "media_id": media["id"],
                "media_type": media["media_type"],
                "title": media["title"],
                "url": f"/media/{media['filename']}",
                "duration_ms": duration_ms,
                # Video toca inteiro e recomeca (loop); imagem fica pelo tempo padrao e recarrega.
                "play_until_end": is_video,
                "position": 1,
                "loop_video_url": f"/media/{media['loop_video_filename']}" if media["loop_video_filename"] else None,
            }
        ],
    }


def player_state(kind: str, slug: str) -> dict[str, Any]:
    """Resposta da API do player (`GET /api/<tipo>/<slug>/state`)."""
    target = resolve_target(kind, slug)
    server_time = now_ms()
    if not target:
        return {
            "ok": False,
            "server_time_ms": server_time,
            "reason": "slug_not_found",
            "message": NOT_FOUND_MESSAGES[kind],
            "poll_ms": PLAYER_POLL_MS,
        }

    if target["media_id"]:
        playlist = media_payload(target["media_id"])
    elif target["playlist_id"]:
        playlist = playlist_payload(target["playlist_id"])
    else:
        playlist = None
    if not playlist or not playlist["items"] or playlist["total_duration_ms"] <= 0:
        return {
            "ok": True,
            "server_time_ms": server_time,
            "target": target,
            "playlist": None,
            "message": "Nenhuma playlist com midias foi associada.",
            "poll_ms": PLAYER_POLL_MS,
        }

    return {
        "ok": True,
        "server_time_ms": server_time,
        "target": target,
        "playlist": playlist,
        "poll_ms": PLAYER_POLL_MS,
        "drift_tolerance_ms": 750,
        "hard_drift_ms": 2500,
    }
