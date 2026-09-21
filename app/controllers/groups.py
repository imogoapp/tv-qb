"""Grupos de TVs."""

from __future__ import annotations

from typing import Any

from ..core.database import make_slug
from ..core.utils import optional_int
from ..models import groups as group_model
from ..models import playlists as playlist_model


def page_data() -> dict[str, Any]:
    return {"groups": group_model.list_with_counts(), "playlists": playlist_model.all_by_name()}


def _playlist_or_error(playlist_id: str) -> tuple[int | None, str | None]:
    value = optional_int(playlist_id)
    if value is not None and not playlist_model.exists(value):
        return None, "link_missing"
    return value, None


def create(name: str, slug: str, playlist_id: str) -> str | None:
    clean_name = name.strip()
    if not clean_name:
        return "bad_name"
    playlist_value, error = _playlist_or_error(playlist_id)
    if error:
        return error
    group_model.insert(clean_name, make_slug("tv_groups", slug or clean_name), playlist_value)
    return None


def update(group_id: int, name: str, slug: str, playlist_id: str) -> str | None:
    clean_name = name.strip()
    if not clean_name:
        return "bad_name"
    if not group_model.exists(group_id):
        return "link_missing"
    playlist_value, error = _playlist_or_error(playlist_id)
    if error:
        return error
    group_model.update(group_id, clean_name, make_slug("tv_groups", slug or clean_name, exclude_id=group_id), playlist_value)
    return None


def delete(group_id: int) -> None:
    group_model.delete(group_id)
