"""Ponto de entrada: `uvicorn app.main:app` (o run.py faz isso)."""

from . import create_app

app = create_app()
