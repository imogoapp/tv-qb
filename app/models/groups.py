"""Tabela `tv_groups`: grupos de TVs."""

from __future__ import annotations

import sqlite3

from ..core.database import execute, fetch_all, fetch_one
from ..core.utils import now_iso


def list_with_counts() -> list[sqlite3.Row]:
    return fetch_all(
        """
        SELECT g.*, p.name AS playlist_name, COUNT(s.id) AS screens_total
        FROM tv_groups g
        LEFT JOIN playlists p ON p.id = g.playlist_id
        LEFT JOIN screens s ON s.group_id = g.id
        GROUP BY g.id
        ORDER BY g.name
        """
    )


def all_by_name() -> list[sqlite3.Row]:
    return fetch_all("SELECT * FROM tv_groups ORDER BY name")


def get_by_slug(slug: str) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM tv_groups WHERE slug = ?", (slug,))


def exists(group_id: int) -> bool:
    return fetch_one("SELECT 1 FROM tv_groups WHERE id = ?", (group_id,)) is not None


def insert(name: str, slug: str, playlist_id: int | None) -> int:
    return execute(
        "INSERT INTO tv_groups (name, slug, playlist_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, slug, playlist_id, now_iso(), now_iso()),
    )


def update(group_id: int, name: str, slug: str, playlist_id: int | None) -> None:
    execute(
        "UPDATE tv_groups SET name = ?, slug = ?, playlist_id = ?, updated_at = ? WHERE id = ?",
        (name, slug, playlist_id, now_iso(), group_id),
    )


def delete(group_id: int) -> None:
    execute("DELETE FROM tv_groups WHERE id = ?", (group_id,))
