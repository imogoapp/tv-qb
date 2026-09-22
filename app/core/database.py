"""Acesso ao banco de TVs, grupos, midias e playlists (signage.db) e criacao/migracao das tabelas."""

from __future__ import annotations

import sqlite3
from typing import Any

from .config import DB_PATH
from .utils import slugify


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    with db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return int(cur.lastrowid)


def unique_slug(
    conn: sqlite3.Connection,
    table: str,
    base: str,
    exclude_id: int | None = None,
    media_type: str | None = None,
) -> str:
    """Devolve `base` ou `base-2`, `base-3`... ate achar um slug livre na tabela.

    Cada tipo de item tem o proprio espaco de slugs (TVs, grupos, playlists e, dentro das
    midias, videos e imagens), entao o mesmo slug pode existir em tipos diferentes.
    """
    candidate = base
    number = 2
    while True:
        sql = f"SELECT 1 FROM {table} WHERE slug = ?"
        params: list[Any] = [candidate]
        if media_type is not None:
            sql += " AND media_type = ?"
            params.append(media_type)
        if exclude_id is not None:
            sql += " AND id != ?"
            params.append(exclude_id)
        if conn.execute(sql, params).fetchone() is None:
            return candidate
        candidate = f"{base}-{number}"
        number += 1


def make_slug(
    table: str,
    raw: str,
    exclude_id: int | None = None,
    media_type: str | None = None,
) -> str:
    with db() as conn:
        return unique_slug(conn, table, slugify(raw), exclude_id=exclude_id, media_type=media_type)


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def init_db() -> None:
    """Cria as tabelas que faltam e migra bancos de versoes antigas (sem perder dados)."""
    with db() as conn:
        # Migracao: a antiga tabela "videos" passa a ser "media". O SQLite atualiza
        # sozinho as chaves estrangeiras que apontavam para ela, e os dados sao mantidos.
        if table_exists(conn, "videos") and not table_exists(conn, "media"):
            conn.execute("ALTER TABLE videos RENAME TO media")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                filename TEXT NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                media_type TEXT NOT NULL DEFAULT 'video',
                default_duration_seconds INTEGER,
                slug TEXT
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                sync_epoch_ms INTEGER NOT NULL,
                revision_ms INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS playlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                duration_seconds INTEGER NOT NULL DEFAULT 30,
                play_until_end INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tv_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                playlist_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS screens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                group_id INTEGER,
                playlist_id INTEGER,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES tv_groups(id) ON DELETE SET NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE SET NULL
            );
            """
        )
        media_columns = table_columns(conn, "media")
        if "media_type" not in media_columns:
            conn.execute("ALTER TABLE media ADD COLUMN media_type TEXT NOT NULL DEFAULT 'video'")
        if "default_duration_seconds" not in media_columns:
            conn.execute("ALTER TABLE media ADD COLUMN default_duration_seconds INTEGER")
        if "slug" not in media_columns:
            conn.execute("ALTER TABLE media ADD COLUMN slug TEXT")
        if "loop_video_filename" not in media_columns:
            # Video mudo em loop gerado a partir da imagem (corrige TV entrando em modo de
            # economia de energia com imagem parada; veja controllers/media.generate_image_loop).
            conn.execute("ALTER TABLE media ADD COLUMN loop_video_filename TEXT")
        # Midias antigas ganham um slug a partir do titulo (usado em /video/<slug> e /image/<slug>).
        for row in conn.execute("SELECT id, title, media_type FROM media WHERE slug IS NULL OR slug = '' ORDER BY id").fetchall():
            new_slug = unique_slug(conn, "media", slugify(row["title"]), exclude_id=row["id"], media_type=row["media_type"])
            conn.execute("UPDATE media SET slug = ? WHERE id = ?", (new_slug, row["id"]))
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_media_type_slug ON media (media_type, slug)")

        item_columns = table_columns(conn, "playlist_items")
        if "play_until_end" not in item_columns:
            conn.execute("ALTER TABLE playlist_items ADD COLUMN play_until_end INTEGER NOT NULL DEFAULT 0")
        if "video_id" in item_columns and "media_id" not in item_columns:
            conn.execute("ALTER TABLE playlist_items RENAME COLUMN video_id TO media_id")
        conn.commit()
