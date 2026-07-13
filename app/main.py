import os
import re
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "signage.db"
MEDIA_DIR = BASE_DIR / "media"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="TV Signage")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def now_ms() -> int:
    return int(time.time() * 1000)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or uuid.uuid4().hex[:8]


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


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                filename TEXT NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
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
                video_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                duration_seconds INTEGER NOT NULL DEFAULT 30,
                play_until_end INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
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
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(playlist_items)").fetchall()]
        if "play_until_end" not in columns:
            conn.execute("ALTER TABLE playlist_items ADD COLUMN play_until_end INTEGER NOT NULL DEFAULT 0")
        conn.commit()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def touch_playlist(playlist_id: int, reset_sync: bool = False) -> None:
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


def get_common_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "path": request.url.path,
        "screens_count": fetch_one("SELECT COUNT(*) AS total FROM screens")["total"],
        "groups_count": fetch_one("SELECT COUNT(*) AS total FROM tv_groups")["total"],
        "videos_count": fetch_one("SELECT COUNT(*) AS total FROM videos")["total"],
        "playlists_count": fetch_one("SELECT COUNT(*) AS total FROM playlists")["total"],
    }


def get_playlists() -> list[sqlite3.Row]:
    return fetch_all("SELECT * FROM playlists ORDER BY name")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    screens = fetch_all(
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
    groups = fetch_all(
        """
        SELECT g.*, p.name AS playlist_name, COUNT(s.id) AS screens_total
        FROM tv_groups g
        LEFT JOIN playlists p ON p.id = g.playlist_id
        LEFT JOIN screens s ON s.group_id = g.id
        GROUP BY g.id
        ORDER BY g.name
        """
    )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            **get_common_context(request),
            "screens": screens,
            "groups": groups,
            "base_url": str(request.base_url).rstrip("/"),
        },
    )


@app.get("/videos", response_class=HTMLResponse)
def videos_page(request: Request) -> HTMLResponse:
    videos = fetch_all("SELECT * FROM videos ORDER BY created_at DESC")
    return templates.TemplateResponse(
        request,
        "videos.html",
        {**get_common_context(request), "videos": videos},
    )


@app.post("/videos")
def upload_video(
    title: str = Form(""),
    file: UploadFile = File(...),
) -> RedirectResponse:
    original_name = file.filename or "video.mp4"
    ext = Path(original_name).suffix.lower()
    if ext not in {".mp4", ".webm", ".mov", ".m4v"}:
        raise HTTPException(status_code=400, detail="Formato de video nao suportado.")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    target = MEDIA_DIR / stored_name
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    final_title = title.strip() or Path(original_name).stem
    execute(
        """
        INSERT INTO videos (title, filename, original_filename, content_type, size_bytes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (final_title, stored_name, original_name, file.content_type or "", target.stat().st_size, now_iso()),
    )
    return RedirectResponse("/videos", status_code=303)


@app.post("/videos/{video_id}/delete")
def delete_video(video_id: int) -> RedirectResponse:
    video = fetch_one("SELECT * FROM videos WHERE id = ?", (video_id,))
    if video:
        path = MEDIA_DIR / video["filename"]
        if path.exists():
            path.unlink()
        execute("DELETE FROM videos WHERE id = ?", (video_id,))
    return RedirectResponse("/videos", status_code=303)


@app.get("/playlists", response_class=HTMLResponse)
def playlists_page(request: Request) -> HTMLResponse:
    playlists = fetch_all(
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
    return templates.TemplateResponse(
        request,
        "playlists.html",
        {**get_common_context(request), "playlists": playlists},
    )


@app.post("/playlists")
def create_playlist(name: str = Form(...), slug: str = Form("")) -> RedirectResponse:
    clean_name = name.strip()
    clean_slug = slugify(slug or clean_name)
    stamp = now_ms()
    playlist_id = execute(
        """
        INSERT INTO playlists (name, slug, sync_epoch_ms, revision_ms, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (clean_name, clean_slug, stamp, stamp, now_iso(), now_iso()),
    )
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@app.get("/playlists/{playlist_id}", response_class=HTMLResponse)
def edit_playlist(request: Request, playlist_id: int) -> HTMLResponse:
    playlist = fetch_one("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
    if not playlist:
        raise HTTPException(status_code=404)
    items = fetch_all(
        """
        SELECT pi.*, v.title AS video_title, v.filename, v.size_bytes
        FROM playlist_items pi
        JOIN videos v ON v.id = pi.video_id
        WHERE pi.playlist_id = ?
        ORDER BY pi.position, pi.id
        """,
        (playlist_id,),
    )
    videos = fetch_all("SELECT * FROM videos ORDER BY title")
    total_seconds = sum(int(item["duration_seconds"]) for item in items if not item["play_until_end"])
    full_video_items = sum(1 for item in items if item["play_until_end"])
    return templates.TemplateResponse(
        request,
        "playlist_edit.html",
        {
            **get_common_context(request),
            "playlist": playlist,
            "items": items,
            "videos": videos,
            "total_seconds": total_seconds,
            "full_video_items": full_video_items,
        },
    )


@app.post("/playlists/{playlist_id}/rename")
def rename_playlist(playlist_id: int, name: str = Form(...), slug: str = Form("")) -> RedirectResponse:
    clean_name = name.strip()
    clean_slug = slugify(slug or clean_name)
    execute(
        "UPDATE playlists SET name = ?, slug = ?, updated_at = ? WHERE id = ?",
        (clean_name, clean_slug, now_iso(), playlist_id),
    )
    touch_playlist(playlist_id)
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@app.post("/playlists/{playlist_id}/items")
def add_playlist_item(
    playlist_id: int,
    video_id: int = Form(...),
    duration_seconds: int = Form(30),
    play_until_end: str = Form("0"),
) -> RedirectResponse:
    play_full = 1 if play_until_end == "1" else 0
    next_position = fetch_one(
        "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM playlist_items WHERE playlist_id = ?",
        (playlist_id,),
    )["next_position"]
    execute(
        """
        INSERT INTO playlist_items (playlist_id, video_id, position, duration_seconds, play_until_end, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (playlist_id, video_id, next_position, max(1, duration_seconds), play_full, now_iso()),
    )
    touch_playlist(playlist_id, reset_sync=True)
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@app.post("/playlists/{playlist_id}/items/{item_id}/update")
def update_playlist_item(
    playlist_id: int,
    item_id: int,
    position: int = Form(...),
    duration_seconds: int = Form(...),
    play_until_end: str = Form("0"),
) -> RedirectResponse:
    play_full = 1 if play_until_end == "1" else 0
    execute(
        "UPDATE playlist_items SET position = ?, duration_seconds = ?, play_until_end = ? WHERE id = ? AND playlist_id = ?",
        (max(1, position), max(1, duration_seconds), play_full, item_id, playlist_id),
    )
    touch_playlist(playlist_id, reset_sync=True)
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@app.post("/playlists/{playlist_id}/items/{item_id}/delete")
def delete_playlist_item(playlist_id: int, item_id: int) -> RedirectResponse:
    execute("DELETE FROM playlist_items WHERE id = ? AND playlist_id = ?", (item_id, playlist_id))
    touch_playlist(playlist_id, reset_sync=True)
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@app.post("/playlists/{playlist_id}/resync")
def resync_playlist(playlist_id: int) -> RedirectResponse:
    touch_playlist(playlist_id, reset_sync=True)
    return RedirectResponse(f"/playlists/{playlist_id}", status_code=303)


@app.post("/playlists/{playlist_id}/delete")
def delete_playlist(playlist_id: int) -> RedirectResponse:
    execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    return RedirectResponse("/playlists", status_code=303)


@app.get("/groups", response_class=HTMLResponse)
def groups_page(request: Request) -> HTMLResponse:
    groups = fetch_all(
        """
        SELECT g.*, p.name AS playlist_name, COUNT(s.id) AS screens_total
        FROM tv_groups g
        LEFT JOIN playlists p ON p.id = g.playlist_id
        LEFT JOIN screens s ON s.group_id = g.id
        GROUP BY g.id
        ORDER BY g.name
        """
    )
    return templates.TemplateResponse(
        request,
        "groups.html",
        {**get_common_context(request), "groups": groups, "playlists": get_playlists(), "base_url": str(request.base_url).rstrip("/")},
    )


@app.post("/groups")
def create_group(
    name: str = Form(...),
    slug: str = Form(""),
    playlist_id: str = Form(""),
) -> RedirectResponse:
    clean_name = name.strip()
    clean_slug = slugify(slug or clean_name)
    playlist_value = int(playlist_id) if playlist_id else None
    execute(
        """
        INSERT INTO tv_groups (name, slug, playlist_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (clean_name, clean_slug, playlist_value, now_iso(), now_iso()),
    )
    return RedirectResponse("/groups", status_code=303)


@app.post("/groups/{group_id}/update")
def update_group(
    group_id: int,
    name: str = Form(...),
    slug: str = Form(""),
    playlist_id: str = Form(""),
) -> RedirectResponse:
    clean_name = name.strip()
    clean_slug = slugify(slug or clean_name)
    playlist_value = int(playlist_id) if playlist_id else None
    execute(
        "UPDATE tv_groups SET name = ?, slug = ?, playlist_id = ?, updated_at = ? WHERE id = ?",
        (clean_name, clean_slug, playlist_value, now_iso(), group_id),
    )
    return RedirectResponse("/groups", status_code=303)


@app.post("/groups/{group_id}/delete")
def delete_group(group_id: int) -> RedirectResponse:
    execute("DELETE FROM tv_groups WHERE id = ?", (group_id,))
    return RedirectResponse("/groups", status_code=303)


@app.get("/screens", response_class=HTMLResponse)
def screens_page(request: Request) -> HTMLResponse:
    screens = fetch_all(
        """
        SELECT s.*, g.name AS group_name, p.name AS playlist_name
        FROM screens s
        LEFT JOIN tv_groups g ON g.id = s.group_id
        LEFT JOIN playlists p ON p.id = s.playlist_id
        ORDER BY s.name
        """
    )
    groups = fetch_all("SELECT * FROM tv_groups ORDER BY name")
    return templates.TemplateResponse(
        request,
        "screens.html",
        {
            **get_common_context(request),
            "screens": screens,
            "groups": groups,
            "playlists": get_playlists(),
            "base_url": str(request.base_url).rstrip("/"),
        },
    )


@app.post("/screens")
def create_screen(
    name: str = Form(...),
    slug: str = Form(""),
    group_id: str = Form(""),
    playlist_id: str = Form(""),
) -> RedirectResponse:
    clean_name = name.strip()
    clean_slug = slugify(slug or clean_name)
    group_value = int(group_id) if group_id else None
    playlist_value = int(playlist_id) if playlist_id else None
    execute(
        """
        INSERT INTO screens (name, slug, group_id, playlist_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (clean_name, clean_slug, group_value, playlist_value, now_iso(), now_iso()),
    )
    return RedirectResponse("/screens", status_code=303)


@app.post("/screens/{screen_id}/update")
def update_screen(
    screen_id: int,
    name: str = Form(...),
    slug: str = Form(""),
    group_id: str = Form(""),
    playlist_id: str = Form(""),
    enabled: str = Form("0"),
) -> RedirectResponse:
    clean_name = name.strip()
    clean_slug = slugify(slug or clean_name)
    group_value = int(group_id) if group_id else None
    playlist_value = int(playlist_id) if playlist_id else None
    execute(
        """
        UPDATE screens
        SET name = ?, slug = ?, group_id = ?, playlist_id = ?, enabled = ?, updated_at = ?
        WHERE id = ?
        """,
        (clean_name, clean_slug, group_value, playlist_value, 1 if enabled == "1" else 0, now_iso(), screen_id),
    )
    return RedirectResponse("/screens", status_code=303)


@app.post("/screens/{screen_id}/delete")
def delete_screen(screen_id: int) -> RedirectResponse:
    execute("DELETE FROM screens WHERE id = ?", (screen_id,))
    return RedirectResponse("/screens", status_code=303)


@app.get("/player/{slug}", response_class=HTMLResponse)
def player(request: Request, slug: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "player.html",
        {"request": request, "slug": slug, "base_url": str(request.base_url).rstrip("/")},
    )


def resolve_target(slug: str) -> dict[str, Any] | None:
    screen = fetch_one(
        """
        SELECT s.*, g.name AS group_name, g.slug AS group_slug, g.playlist_id AS group_playlist_id
        FROM screens s
        LEFT JOIN tv_groups g ON g.id = s.group_id
        WHERE s.slug = ? AND s.enabled = 1
        """,
        (slug,),
    )
    if screen:
        playlist_id = screen["playlist_id"] or screen["group_playlist_id"]
        return {"type": "screen", "name": screen["name"], "slug": screen["slug"], "playlist_id": playlist_id}

    group = fetch_one("SELECT * FROM tv_groups WHERE slug = ?", (slug,))
    if group:
        return {"type": "group", "name": group["name"], "slug": group["slug"], "playlist_id": group["playlist_id"]}

    playlist = fetch_one("SELECT * FROM playlists WHERE slug = ?", (slug,))
    if playlist:
        return {"type": "playlist", "name": playlist["name"], "slug": playlist["slug"], "playlist_id": playlist["id"]}

    return None


def playlist_payload(playlist_id: int) -> dict[str, Any] | None:
    playlist = fetch_one("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
    if not playlist:
        return None

    items = fetch_all(
        """
        SELECT pi.*, v.title AS video_title, v.filename
        FROM playlist_items pi
        JOIN videos v ON v.id = pi.video_id
        WHERE pi.playlist_id = ?
        ORDER BY pi.position, pi.id
        """,
        (playlist_id,),
    )
    payload_items = []
    total_ms = 0
    for item in items:
        duration_ms = int(item["duration_seconds"]) * 1000
        total_ms += duration_ms
        payload_items.append(
            {
                "item_id": item["id"],
                "video_id": item["video_id"],
                "title": item["video_title"],
                "url": f"/media/{item['filename']}",
                "duration_ms": duration_ms,
                "play_until_end": bool(item["play_until_end"]),
                "position": item["position"],
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


@app.get("/api/time")
def api_time() -> JSONResponse:
    return JSONResponse({"server_time_ms": now_ms()}, headers={"Cache-Control": "no-store"})


@app.get("/api/player/{slug}/state")
def api_player_state(slug: str) -> JSONResponse:
    target = resolve_target(slug)
    server_time = now_ms()
    if not target:
        return JSONResponse(
            {
                "ok": False,
                "server_time_ms": server_time,
                "reason": "slug_not_found",
                "message": "Player nao cadastrado.",
                "poll_ms": 5000,
            },
            headers={"Cache-Control": "no-store"},
        )

    playlist = playlist_payload(target["playlist_id"]) if target["playlist_id"] else None
    if not playlist or not playlist["items"] or playlist["total_duration_ms"] <= 0:
        return JSONResponse(
            {
                "ok": True,
                "server_time_ms": server_time,
                "target": target,
                "playlist": None,
                "message": "Nenhuma playlist com videos foi associada.",
                "poll_ms": 5000,
            },
            headers={"Cache-Control": "no-store"},
        )

    return JSONResponse(
        {
            "ok": True,
            "server_time_ms": server_time,
            "target": target,
            "playlist": playlist,
            "poll_ms": 5000,
            "drift_tolerance_ms": 750,
            "hard_drift_ms": 2500,
        },
        headers={"Cache-Control": "no-store"},
    )
