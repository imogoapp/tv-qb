"""Biblioteca de midias: envio, listagem e exclusao."""

from __future__ import annotations

import math
import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from ..core.config import (
    ALLOWED_EXTENSIONS,
    DEFAULT_IMAGE_SECONDS,
    IMAGE_EXTENSIONS,
    MAX_DURATION_SECONDS,
    MEDIA_DIR,
    VIDEO_EXTENSIONS,
    VIDEO_EXTENSIONS_SAFE,
)
from ..core.database import make_slug
from ..core.utils import now_iso
from ..models import media as media_model
from ..models import playlists as playlist_model

try:
    import mutagen
except ImportError:  # duracao automatica e opcional
    mutagen = None


def media_type_for(ext: str) -> str | None:
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def probe_video_seconds(path: Path) -> int | None:
    """Duracao do video em segundos (arredondada para cima) quando o mutagen consegue ler."""
    if mutagen is None:
        return None
    try:
        parsed = mutagen.File(path)
        length = float(parsed.info.length) if parsed is not None and parsed.info else 0.0
    except Exception:
        return None
    if length <= 0:
        return None
    return max(1, math.ceil(length))


def library_context() -> dict[str, Any]:
    """Dados da pagina da biblioteca."""
    media = []
    for row in media_model.newest_first():
        item = dict(row)
        ext = Path(item["filename"]).suffix.lower()
        item["web_safe"] = item["media_type"] == "image" or ext in VIDEO_EXTENSIONS_SAFE
        media.append(item)
    return {
        "media": media,
        "accept": ",".join(sorted(ALLOWED_EXTENSIONS)),
        "image_extensions": sorted(IMAGE_EXTENSIONS),
        "default_image_seconds": DEFAULT_IMAGE_SECONDS,
    }


def upload(
    original_name: str,
    stream: BinaryIO,
    content_type: str | None,
    title: str,
    slug: str,
    default_duration_seconds: str,
) -> str | None:
    """Guarda o arquivo e cadastra a midia. Devolve um codigo de erro ou None se deu certo."""
    original_name = original_name or "arquivo"
    ext = Path(original_name).suffix.lower()
    media_type = media_type_for(ext)
    if media_type is None:
        return "bad_format"

    stored_name = f"{uuid.uuid4().hex}{ext}"
    target = MEDIA_DIR / stored_name
    with target.open("wb") as out:
        shutil.copyfileobj(stream, out)

    if media_type == "image":
        try:
            default_seconds: int | None = int(default_duration_seconds)
        except ValueError:
            default_seconds = None
        if default_seconds is None or default_seconds < 1:
            default_seconds = DEFAULT_IMAGE_SECONDS
        default_seconds = min(default_seconds, MAX_DURATION_SECONDS)
    else:
        default_seconds = probe_video_seconds(target)

    final_title = title.strip() or Path(original_name).stem
    media_model.insert(
        title=final_title,
        filename=stored_name,
        original_filename=original_name,
        content_type=content_type or mimetypes.guess_type(original_name)[0] or "",
        size_bytes=target.stat().st_size,
        created_at=now_iso(),
        media_type=media_type,
        default_duration_seconds=default_seconds,
        slug=make_slug("media", slug or final_title, media_type=media_type),
    )
    return None


def delete(media_id: int) -> bool:
    """Apaga a midia (arquivo e registro). Os players das playlists afetadas sao avisados para recarregar."""
    media = media_model.get(media_id)
    if not media:
        return False
    affected = media_model.playlist_ids_using(media_id)
    path = MEDIA_DIR / media["filename"]
    if path.exists():
        path.unlink()
    media_model.delete(media_id)
    for playlist_id in affected:
        playlist_model.touch(playlist_id, reset_sync=True)
    return True
