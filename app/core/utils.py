"""Funcoes pequenas sem dependencia do resto do sistema."""

from __future__ import annotations

import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone


def now_ms() -> int:
    return int(time.time() * 1000)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    # "Recepção" -> "recepcao" (sem isso o "ç" e os acentos virariam hifens).
    value = unicodedata.normalize("NFKD", value.strip().lower())
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or uuid.uuid4().hex[:8]


def optional_int(value: str | None) -> int | None:
    """Converte o valor de um <select> ("" = nenhum) em inteiro ou None. Lixo vira None."""
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None
