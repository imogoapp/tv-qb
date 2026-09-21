"""Tabelas `playlists` e `playlist_items`."""

from __future__ import annotations

import sqlite3
from typing import Iterable

from ..core.database import db, execute, fetch_all, fetch_one
from ..core.utils import now_iso, now_ms


# --------------------------------------------------------------------------- playlists

def all_by_name() -> list[sqlite3.Row]:
    return fetch_all("SELECT * FROM playlists ORDER BY name")


def list_with_totals() -> list[sqlite3.Row]:
    """Playlists com quantidade de itens e soma dos tempos fixos (videos "inteiros" contados a parte)."""
    return fetch_all(
        """
        SELECT p.*,
               COALESCE(SUM(CASE WHEN pi.play_until_end = 0 THEN pi.duration_seconds ELSE 0 END), 0) AS duration_seconds,
               COALESCE(SUM(CASE WHEN pi.play_until_end = 1 THEN 1 ELSE 0 END), 0) AS full_video_items,
               COUNT(pi.id) AS items_total
        FROM playlists p
        LEFT JOIN playlist_items pi ON pi.playlist_id = p.id
        GROUP BY p.id
        ORDER BY p.name
        """
    )


def get(playlist_id: int) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM playlists WHERE id = ?", (playlist_id,))


def get_by_slug(slug: str) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM playlists WHERE slug = ?", (slug,))


def exists(playlist_id: int) -> bool:
    return fetch_one("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)) is not None


def insert(name: str, slug: str) -> int:
    stamp = now_ms()
    return execute(
        """
        INSERT INTO playlists (name, slug, sync_epoch_ms, revision_ms, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, slug, stamp, stamp, now_iso(), now_iso()),
    )


def rename(playlist_id: int, name: str, slug: str) -> None:
    execute(
        "UPDATE playlists SET name = ?, slug = ?, updated_at = ? WHERE id = ?",
        (name, slug, now_iso(), playlist_id),
    )


def touch(playlist_id: int, reset_sync: bool = False) -> None:
    """Marca a playlist como alterada (os players recarregam). `reset_sync` reinicia o sincronismo das TVs."""
    stamp = now_ms()
    if reset_sync:
        execute(
            "UPDATE playlists SET sync_epoch_ms = ?, revision_ms = ?, updated_at = ? WHERE id = ?",
            (stamp, stamp, now_iso(), playlist_id),
        )
    else:
        execute(
            "UPDATE playlists SET revision_ms = ?, updated_at = ? WHERE id = ?",
            (stamp, now_iso(), playlist_id),
        )


def delete(playlist_id: int) -> None:
    execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))


# --------------------------------------------------------------------------- itens

def items_with_media(playlist_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        """
        SELECT pi.*, m.title AS media_title, m.filename, m.size_bytes, m.media_type
        FROM playlist_items pi
        JOIN media m ON m.id = pi.media_id
        WHERE pi.playlist_id = ?
        ORDER BY pi.position, pi.id
        """,
        (playlist_id,),
    )


def item_types(playlist_id: int) -> dict[int, str]:
    """id do item -> tipo da midia ("image" ou "video"), na ordem atual da playlist."""
    rows = fetch_all(
        """
        SELECT pi.id, m.media_type
        FROM playlist_items pi JOIN media m ON m.id = pi.media_id
        WHERE pi.playlist_id = ?
        ORDER BY pi.position, pi.id
        """,
        (playlist_id,),
    )
    return {row["id"]: row["media_type"] for row in rows}


def item_media_type(playlist_id: int, item_id: int) -> str | None:
    row = fetch_one(
        """
        SELECT m.media_type
        FROM playlist_items pi
        JOIN media m ON m.id = pi.media_id
        WHERE pi.id = ? AND pi.playlist_id = ?
        """,
        (item_id, playlist_id),
    )
    return row["media_type"] if row else None


def next_position(playlist_id: int) -> int:
    row = fetch_one(
        "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM playlist_items WHERE playlist_id = ?",
        (playlist_id,),
    )
    return int(row["next_position"])


def add_item(playlist_id: int, media_id: int, position: int, duration_seconds: int, play_until_end: bool) -> int:
    return execute(
        """
        INSERT INTO playlist_items (playlist_id, media_id, position, duration_seconds, play_until_end, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (playlist_id, media_id, position, duration_seconds, 1 if play_until_end else 0, now_iso()),
    )


def update_item(playlist_id: int, item_id: int, position: int, duration_seconds: int, play_until_end: bool) -> None:
    execute(
        "UPDATE playlist_items SET position = ?, duration_seconds = ?, play_until_end = ? WHERE id = ? AND playlist_id = ?",
        (position, duration_seconds, 1 if play_until_end else 0, item_id, playlist_id),
    )


def delete_item(playlist_id: int, item_id: int) -> None:
    execute("DELETE FROM playlist_items WHERE id = ? AND playlist_id = ?", (item_id, playlist_id))


def apply_timeline(
    playlist_id: int,
    remove_ids: Iterable[int],
    ordered: list[tuple[int, int, bool]],
    leftover_ids: list[int],
) -> None:
    """Grava a linha do tempo inteira numa transacao so.

    `ordered` = (id do item, segundos, tocar inteiro) na ordem final; `leftover_ids` = itens que a tela
    nao conhecia e que ficam no fim.
    """
    with db() as conn:
        for item_id in remove_ids:
            conn.execute("DELETE FROM playlist_items WHERE id = ? AND playlist_id = ?", (item_id, playlist_id))
        for position, (item_id, seconds, play_full) in enumerate(ordered, start=1):
            conn.execute(
                "UPDATE playlist_items SET position = ?, duration_seconds = ?, play_until_end = ? "
                "WHERE id = ? AND playlist_id = ?",
                (position, seconds, 1 if play_full else 0, item_id, playlist_id),
            )
        for position, item_id in enumerate(leftover_ids, start=len(ordered) + 1):
            conn.execute("UPDATE playlist_items SET position = ? WHERE id = ?", (position, item_id))
        conn.commit()


def item_durations(playlist_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT duration_seconds, play_until_end FROM playlist_items WHERE playlist_id = ?", (playlist_id,)
    )
