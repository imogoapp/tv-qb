"""Rotas HTTP (finas: leem a requisicao, chamam um controller e devolvem HTML, redirecionamento ou JSON)."""

from __future__ import annotations

from fastapi import FastAPI

from . import accounts, dashboard, groups, media, player, playlists, screens, users


def include_routers(app: FastAPI) -> None:
    for module in (accounts, users, dashboard, media, playlists, groups, screens, player):
        app.include_router(module.router)
