"""Painel inicial."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from ..controllers import dashboard
from ..core.templating import render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request) -> Response:
    return render(request, "dashboard.html", base_url=str(request.base_url).rstrip("/"), **dashboard.overview())
