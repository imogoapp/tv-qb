"""Caminhos e constantes do sistema (um lugar so para ajustar limites e formatos aceitos)."""

from __future__ import annotations

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent          # .../app
DB_PATH = APP_DIR / "signage.db"                           # TVs, grupos, midias e playlists
MEDIA_DIR = APP_DIR / "media"                              # arquivos enviados (servidos em /media/<arquivo>)
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

# Tipos de midia aceitos no upload.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
# Formatos que os navegadores das TVs costumam tocar sem problema.
VIDEO_EXTENSIONS_SAFE = {".mp4", ".m4v", ".webm", ".ogv"}
# Aceitos, mas dependem do codec (ou nao tocam em navegador): recomendado converter para MP4/H.264.
VIDEO_EXTENSIONS_CHECK = {".mov", ".mkv", ".3gp", ".avi", ".wmv", ".mpg", ".mpeg", ".flv"}
VIDEO_EXTENSIONS = VIDEO_EXTENSIONS_SAFE | VIDEO_EXTENSIONS_CHECK
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

DEFAULT_IMAGE_SECONDS = 30
DEFAULT_VIDEO_SECONDS = 30
MAX_DURATION_SECONDS = 24 * 60 * 60

# Cada tipo de item tem o proprio prefixo de URL (veja routers/player.py).
PLAYER_KINDS = ("player", "group", "playlist", "video", "image")
PLAYER_POLL_MS = 5000
