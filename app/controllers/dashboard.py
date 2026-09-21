"""Painel inicial."""

from __future__ import annotations

from typing import Any

from ..models import groups, screens


def overview() -> dict[str, Any]:
    return {"screens": screens.list_with_relations(), "groups": groups.list_with_counts()}
