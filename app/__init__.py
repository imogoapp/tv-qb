"""TV Quebê - painel e player de midia indoor (FastAPI + Jinja + SQLite).

Estrutura (cada pasta tem uma responsabilidade):

  core/         configuracao, banco, utilitarios, templates e avisos
  auth/         login, sessoes, roles e gestao de usuarios (users.db proprio)
  models/       SQL: uma tabela por modulo
  schemas/      formatos JSON validados pelo Pydantic
  controllers/  regras de negocio (validam, usam os models, devolvem dados ou um codigo de aviso)
  routers/      rotas HTTP finas: leem a requisicao, chamam o controller e respondem
  templates/    paginas Jinja        static/  CSS, JS e bibliotecas (sem CDN)

Fluxo de uma requisicao:  router -> controller -> model -> SQLite.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Monta a aplicacao (fabrica, no estilo do Flask: `create_app()`)."""
    from fastapi import Depends
    from fastapi.staticfiles import StaticFiles

    from . import auth
    from .core.config import MEDIA_DIR, STATIC_DIR
    from .core.database import init_db
    from .core.errors import register_error_handlers
    from .routers import include_routers

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        init_db()
        auth.init_users_db()
        yield

    # Todas as rotas passam por auth.guard: as telas de administracao exigem login e a role certa;
    # so as paginas de exibicao das TVs (/player, /group, /playlist, /video, /image), a API do player
    # e os arquivos (/static, /media) ficam abertos, porque a TV nao tem como digitar senha.
    app = FastAPI(title="TV Signage", dependencies=[Depends(auth.guard)], lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
    register_error_handlers(app)
    include_routers(app)
    return app
