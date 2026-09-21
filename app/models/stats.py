"""Contadores mostrados no menu do painel."""

from __future__ import annotations

from ..core.database import fetch_one


def counts() -> dict[str, int]:
    return {
        "screens_count": fetch_one("SELECT COUNT(*) AS total FROM screens")["total"],
        "groups_count": fetch_one("SELECT COUNT(*) AS total FROM tv_groups")["total"],
        "media_count": fetch_one("SELECT COUNT(*) AS total FROM media")["total"],
        "playlists_count": fetch_one("SELECT COUNT(*) AS total FROM playlists")["total"],
    }
