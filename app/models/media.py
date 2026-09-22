"""Tabela `media`: imagens e videos enviados."""

from __future__ import annotations

import sqlite3

from ..core.database import execute, fetch_all, fetch_one


def newest_first() -> list[sqlite3.Row]:
    return fetch_all("SELECT * FROM media ORDER BY created_at DESC")


def by_title() -> list[sqlite3.Row]:
    return fetch_all("SELECT * FROM media ORDER BY title COLLATE NOCASE")


def get(media_id: int) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM media WHERE id = ?", (media_id,))


def get_by_slug(slug: str, media_type: str) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM media WHERE slug = ? AND media_type = ?", (slug, media_type))


def images_missing_loop() -> list[sqlite3.Row]:
    """Imagens enviadas antes do recurso de loop em video existir (ou cuja geracao falhou)."""
    return fetch_all(
        "SELECT * FROM media WHERE media_type = 'image' AND (loop_video_filename IS NULL OR loop_video_filename = '')"
    )


def set_loop_video_filename(media_id: int, loop_video_filename: str) -> None:
    execute("UPDATE media SET loop_video_filename = ? WHERE id = ?", (loop_video_filename, media_id))


def insert(
    *,
    title: str,
    filename: str,
    original_filename: str,
    content_type: str,
    size_bytes: int,
    created_at: str,
    media_type: str,
    default_duration_seconds: int | None,
    slug: str,
    loop_video_filename: str | None = None,
) -> int:
    return execute(
        """
        INSERT INTO media (title, filename, original_filename, content_type, size_bytes, created_at,
                           media_type, default_duration_seconds, slug, loop_video_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title, filename, original_filename, content_type, size_bytes, created_at,
            media_type, default_duration_seconds, slug, loop_video_filename,
        ),
    )


def delete(media_id: int) -> None:
    # Os itens das playlists que usavam a midia saem por cascata (ON DELETE CASCADE).
    execute("DELETE FROM media WHERE id = ?", (media_id,))


def playlist_ids_using(media_id: int) -> list[int]:
    rows = fetch_all("SELECT DISTINCT playlist_id FROM playlist_items WHERE media_id = ?", (media_id,))
    return [row["playlist_id"] for row in rows]
