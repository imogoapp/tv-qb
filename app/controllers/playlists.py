"""Playlists: criar, renomear, montar a linha do tempo (adicionar, ordenar, remover) e excluir."""

from __future__ import annotations

from typing import Any

from ..core.config import DEFAULT_IMAGE_SECONDS, DEFAULT_VIDEO_SECONDS, MAX_DURATION_SECONDS
from ..core.database import make_slug
from ..models import media as media_model
from ..models import playlists as playlist_model
from ..schemas.playlists import TimelineSave


class PlaylistError(Exception):
    """Erro de regra de negocio com o codigo HTTP que a rota JSON deve devolver."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def clamp_seconds(seconds: int) -> int:
    return min(MAX_DURATION_SECONDS, max(1, seconds))


# --------------------------------------------------------------------------- telas

def list_page() -> dict[str, Any]:
    return {"playlists": playlist_model.list_with_totals()}


def editor_page(playlist_id: int) -> dict[str, Any] | None:
    """Dados da tela de edicao, ou None se a playlist nao existe."""
    playlist = playlist_model.get(playlist_id)
    if not playlist:
        return None
    items = playlist_model.items_with_media(playlist_id)
    media = media_model.by_title()
    return {
        "playlist": playlist,
        "items": items,
        "videos": [m for m in media if m["media_type"] == "video"],
        "images": [m for m in media if m["media_type"] == "image"],
        "default_image_seconds": DEFAULT_IMAGE_SECONDS,
        "default_video_seconds": DEFAULT_VIDEO_SECONDS,
        "total_seconds": sum(int(item["duration_seconds"]) for item in items if not item["play_until_end"]),
        "full_video_items": sum(1 for item in items if item["play_until_end"]),
    }


# --------------------------------------------------------------------------- dados da playlist

def create(name: str, slug: str) -> tuple[int | None, str | None]:
    """Cria a playlist. Devolve (id, None) ou (None, codigo de erro)."""
    clean_name = name.strip()
    if not clean_name:
        return None, "bad_name"
    return playlist_model.insert(clean_name, make_slug("playlists", slug or clean_name)), None


def rename(playlist_id: int, name: str, slug: str) -> str | None:
    if not playlist_model.exists(playlist_id):
        return "playlist_missing"
    clean_name = name.strip()
    if not clean_name:
        return "bad_name"
    playlist_model.rename(playlist_id, clean_name, make_slug("playlists", slug or clean_name, exclude_id=playlist_id))
    playlist_model.touch(playlist_id)
    return None


def resync(playlist_id: int) -> str | None:
    if not playlist_model.exists(playlist_id):
        return "playlist_missing"
    playlist_model.touch(playlist_id, reset_sync=True)
    return None


def delete(playlist_id: int) -> None:
    playlist_model.delete(playlist_id)


# --------------------------------------------------------------------------- itens

def add_item(playlist_id: int, media_id: int, duration_seconds: int, play_until_end: bool) -> str | None:
    if not playlist_model.exists(playlist_id):
        return "playlist_missing"
    media = media_model.get(media_id)
    if not media:
        return "media_missing"
    # "Tocar inteiro" so faz sentido para video; imagem sempre usa o tempo definido.
    playlist_model.add_item(
        playlist_id,
        media_id,
        playlist_model.next_position(playlist_id),
        clamp_seconds(duration_seconds),
        play_until_end and media["media_type"] == "video",
    )
    playlist_model.touch(playlist_id, reset_sync=True)
    return None


def update_item(playlist_id: int, item_id: int, position: int, duration_seconds: int, play_until_end: bool) -> None:
    """Edicao de um item por vez (a tela nova salva tudo junto por `save_timeline`)."""
    media_type = playlist_model.item_media_type(playlist_id, item_id)
    if media_type is None:
        return
    playlist_model.update_item(
        playlist_id, item_id, max(1, position), clamp_seconds(duration_seconds), play_until_end and media_type == "video"
    )
    playlist_model.touch(playlist_id, reset_sync=True)


def remove_item(playlist_id: int, item_id: int) -> None:
    playlist_model.delete_item(playlist_id, item_id)
    playlist_model.touch(playlist_id, reset_sync=True)


def save_timeline(playlist_id: int, payload: TimelineSave) -> dict[str, Any]:
    """Salva de uma vez a ordem (arrastar e soltar), os tempos, o "tocar inteiro" e as remocoes."""
    if not playlist_model.exists(playlist_id):
        raise PlaylistError(404, "Playlist nao encontrada.")
    existing = playlist_model.item_types(playlist_id)
    ids = [item.id for item in payload.items]
    if len(set(ids)) != len(ids) or any(item_id not in existing for item_id in ids):
        raise PlaylistError(400, "A lista tem itens que nao pertencem a esta playlist.")
    remove = {item_id for item_id in payload.remove if item_id in existing}
    if remove & set(ids):
        raise PlaylistError(400, "Um item nao pode ser mantido e removido ao mesmo tempo.")
    # Itens que a tela nao conhecia (adicionados em outra aba) ficam no fim, na ordem em que estavam.
    leftover = [item_id for item_id in existing if item_id not in set(ids) and item_id not in remove]

    ordered = [
        (item.id, clamp_seconds(item.duration_seconds), item.play_until_end and existing[item.id] == "video")
        for item in payload.items
    ]
    playlist_model.apply_timeline(playlist_id, remove, ordered, leftover)
    playlist_model.touch(playlist_id, reset_sync=True)

    rows = playlist_model.item_durations(playlist_id)
    return {
        "ok": True,
        "items": len(rows),
        "total_seconds": sum(int(row["duration_seconds"]) for row in rows if not row["play_until_end"]),
        "full_video_items": sum(1 for row in rows if row["play_until_end"]),
    }
