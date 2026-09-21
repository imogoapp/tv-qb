"""TVs cadastradas."""

from __future__ import annotations

from typing import Any

from ..core.database import make_slug
from ..core.utils import optional_int
from ..models import groups as group_model
from ..models import playlists as playlist_model
from ..models import screens as screen_model


def page_data() -> dict[str, Any]:
    return {
        "screens": screen_model.list_with_relations(),
        "groups": group_model.all_by_name(),
        "playlists": playlist_model.all_by_name(),
    }


def _links(group_id: str, playlist_id: str) -> tuple[int | None, int | None, str | None]:
    """Converte e confere o grupo e a playlist escolhidos (podem ter sido excluidos enquanto a tela estava aberta)."""
    group_value = optional_int(group_id)
    playlist_value = optional_int(playlist_id)
    if group_value is not None and not group_model.exists(group_value):
        return None, None, "link_missing"
    if playlist_value is not None and not playlist_model.exists(playlist_value):
        return None, None, "link_missing"
    return group_value, playlist_value, None


def create(name: str, slug: str, group_id: str, playlist_id: str) -> str | None:
    clean_name = name.strip()
    if not clean_name:
        return "bad_name"
    group_value, playlist_value, error = _links(group_id, playlist_id)
    if error:
        return error
    screen_model.insert(clean_name, make_slug("screens", slug or clean_name), group_value, playlist_value)
    return None


def update(screen_id: int, name: str, slug: str, group_id: str, playlist_id: str, enabled: bool) -> str | None:
    clean_name = name.strip()
    if not clean_name:
        return "bad_name"
    group_value, playlist_value, error = _links(group_id, playlist_id)
    if error:
        return error
    screen_model.update(
        screen_id, clean_name, make_slug("screens", slug or clean_name, exclude_id=screen_id), group_value, playlist_value, enabled
    )
    return None


def delete(screen_id: int) -> None:
    screen_model.delete(screen_id)
