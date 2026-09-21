"""Tabela `screens`: TVs cadastradas."""

from __future__ import annotations

import sqlite3

from ..core.database import execute, fetch_all, fetch_one
from ..core.utils import now_iso


def list_with_relations() -> list[sqlite3.Row]:
    """TVs com o nome do grupo, da playlist propria e da playlist herdada do grupo."""
    return fetch_all(
        """
        SELECT s.*, g.name AS group_name, p.name AS playlist_name,
               gp.name AS inherited_playlist_name
        FROM screens s
        LEFT JOIN tv_groups g ON g.id = s.group_id
        LEFT JOIN playlists p ON p.id = s.playlist_id
        LEFT JOIN playlists gp ON gp.id = g.playlist_id
        ORDER BY s.name
        """
    )


def get_by_slug(slug: str) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM screens WHERE slug = ?", (slug,))


def get_enabled_with_group_playlist(slug: str) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT s.*, g.playlist_id AS group_playlist_id
        FROM screens s
        LEFT JOIN tv_groups g ON g.id = s.group_id
        WHERE s.slug = ? AND s.enabled = 1
        """,
        (slug,),
    )


def insert(name: str, slug: str, group_id: int | None, playlist_id: int | None) -> int:
    return execute(
        "INSERT INTO screens (name, slug, group_id, playlist_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, slug, group_id, playlist_id, now_iso(), now_iso()),
    )


def update(screen_id: int, name: str, slug: str, group_id: int | None, playlist_id: int | None, enabled: bool) -> None:
    execute(
        """
        UPDATE screens
        SET name = ?, slug = ?, group_id = ?, playlist_id = ?, enabled = ?, updated_at = ?
        WHERE id = ?
        """,
        (name, slug, group_id, playlist_id, 1 if enabled else 0, now_iso(), screen_id),
    )


def delete(screen_id: int) -> None:
    execute("DELETE FROM screens WHERE id = ?", (screen_id,))
