"""Biblioteca de midias: envio, listagem e exclusao."""

from __future__ import annotations

import logging
import math
import mimetypes
import shutil
import subprocess
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

logger = logging.getLogger(__name__)

# Duracao/qualidade do video mudo gerado para cada imagem (veja generate_image_loop). O tempo de
# exibicao na playlist continua sendo o configurado no item; o loop e so uma forma de mostrar a
# mesma imagem parada que faz a TV entender que ha um video tocando.
IMAGE_LOOP_SECONDS = 4
IMAGE_LOOP_FPS = 15
IMAGE_LOOP_MAX_WIDTH = 1920
IMAGE_LOOP_TIMEOUT_SECONDS = 25


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def generate_image_loop(image_path: Path) -> str | None:
    """Gera um video mudo curto e em loop a partir da imagem, para tocar no <video> em vez do <img>.

    Corrige um bug visto em Smart TVs (confirmado em LG/webOS): o navegador da TV entra em modo de
    economia de energia (relogio) quando fica tempo demais sem nenhum video tocando, mesmo com uma
    imagem estatica normalmente em tela. Se o ffmpeg nao estiver instalado ou a conversao falhar,
    devolve None e a imagem continua sendo mostrada como antes (sem loop de video) - nada quebra.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None

    output_name = f"{image_path.stem}.loop.mp4"
    output_path = image_path.parent / output_name
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(image_path),
        "-t", str(IMAGE_LOOP_SECONDS),
        "-r", str(IMAGE_LOOP_FPS),
        # H.264 exige largura e altura pares; trunc(.../2)*2 arredonda ambas para baixo.
        # A virgula dentro de min(...) precisa ser escapada (senao o ffmpeg le como novo filtro).
        "-vf", f"scale=trunc(min({IMAGE_LOOP_MAX_WIDTH}\\,iw)/2)*2:-2",
        "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-an",
        str(output_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=IMAGE_LOOP_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Nao foi possivel gerar o video em loop de %s: %s", image_path.name, exc)
        return None

    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        logger.warning(
            "ffmpeg falhou ao gerar o loop de %s (codigo %s): %s",
            image_path.name,
            result.returncode,
            result.stderr.decode("utf-8", "ignore")[-400:],
        )
        output_path.unlink(missing_ok=True)
        return None

    return output_name


def backfill_image_loops() -> None:
    """Gera o video em loop das imagens que ainda nao tem (enviadas antes desse recurso existir)."""
    pending = media_model.images_missing_loop()
    if not pending or not ffmpeg_available():
        return
    for row in pending:
        image_path = MEDIA_DIR / row["filename"]
        if not image_path.exists():
            continue
        loop_filename = generate_image_loop(image_path)
        if loop_filename:
            media_model.set_loop_video_filename(row["id"], loop_filename)


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
        item["has_loop"] = bool(item.get("loop_video_filename"))
        media.append(item)
    return {
        "media": media,
        "accept": ",".join(sorted(ALLOWED_EXTENSIONS)),
        "image_extensions": sorted(IMAGE_EXTENSIONS),
        "default_image_seconds": DEFAULT_IMAGE_SECONDS,
        "ffmpeg_available": ffmpeg_available(),
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

    loop_video_filename = None
    if media_type == "image":
        try:
            default_seconds: int | None = int(default_duration_seconds)
        except ValueError:
            default_seconds = None
        if default_seconds is None or default_seconds < 1:
            default_seconds = DEFAULT_IMAGE_SECONDS
        default_seconds = min(default_seconds, MAX_DURATION_SECONDS)
        loop_video_filename = generate_image_loop(target)
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
        loop_video_filename=loop_video_filename,
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
    if media["loop_video_filename"]:
        loop_path = MEDIA_DIR / media["loop_video_filename"]
        if loop_path.exists():
            loop_path.unlink()
    media_model.delete(media_id)
    for playlist_id in affected:
        playlist_model.touch(playlist_id, reset_sync=True)
    return True
