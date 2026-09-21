"""Corpo do salvamento da linha do tempo da playlist (POST /playlists/<id>/items/save)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    id: int
    duration_seconds: int = 1
    play_until_end: bool = False


class TimelineSave(BaseModel):
    """Estado da linha do tempo enviado pela tela da playlist: itens na ordem final e itens removidos."""

    items: list[TimelineItem] = Field(default_factory=list, max_length=500)
    remove: list[int] = Field(default_factory=list, max_length=500)
