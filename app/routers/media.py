"""Biblioteca de midias."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..controllers import media
from ..core.templating import redirect, render

router = APIRouter()


# A biblioteca fica em /library porque /media/<arquivo> e o mount dos arquivos enviados.
@router.get("/library", response_class=HTMLResponse)
def library_page(request: Request) -> Response:
    return render(request, "media.html", **media.library_context())


@router.get("/videos")
def legacy_videos_redirect() -> RedirectResponse:
    # Link antigo, de quando a biblioteca so tinha videos.
    return RedirectResponse("/library", status_code=307)


@router.post("/library")
def upload_media(
    title: str = Form(""),
    slug: str = Form(""),
    default_duration_seconds: str = Form(""),
    file: UploadFile = File(...),
) -> Response:
    error = media.upload(file.filename or "", file.file, file.content_type, title, slug, default_duration_seconds)
    return redirect("/library", err=error) if error else redirect("/library", ok="media_uploaded")


@router.post("/library/{media_id}/delete")
def delete_media(media_id: int) -> Response:
    if media.delete(media_id):
        return redirect("/library", ok="media_deleted")
    return redirect("/library", err="media_missing")
