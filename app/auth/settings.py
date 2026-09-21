"""Constantes do modulo de autenticacao."""

from __future__ import annotations

import os
import re
from pathlib import Path

# app/users.db (uma pasta acima de app/auth). A variavel TVQB_USERS_DB troca o caminho (testes, backup).
APP_DIR = Path(__file__).resolve().parent.parent
USERS_DB_PATH = Path(os.environ.get("TVQB_USERS_DB") or APP_DIR / "users.db")

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

ROLES = ("viewer", "user", "admin", "root")
ROLE_RANK = {role: index for index, role in enumerate(ROLES, start=1)}
ROLE_LABELS = {
    "viewer": "Visualizador",
    "user": "Usuário",
    "admin": "Administrador",
    "root": "Root",
}
ROLE_DESCRIPTIONS = {
    "viewer": "Só visualiza o painel, TVs, grupos, mídias e playlists.",
    "user": "Visualiza tudo e gerencia mídias e playlists.",
    "admin": "Também gerencia TVs, grupos e usuários (viewer e user).",
    "root": "Acesso total, inclusive gerenciar administradores.",
}

# Preferencias que cada usuario pode guardar: chave -> valores aceitos (o primeiro e o padrao).
PREFERENCE_CHOICES = {"layout": ("side", "top")}
LAYOUT_LABELS = {"side": "Menu lateral", "top": "Menu no topo"}

SESSION_COOKIE = "tvqb_session"
SESSION_HOURS = 12
REMEMBER_DAYS = 30

MIN_PASSWORD_LENGTH = 6
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

# Bloqueio de tentativas: 5 erros para o mesmo usuario+IP (ou 25 no mesmo IP) em 10 minutos
# bloqueiam novos logins por 5 minutos.
ATTEMPT_WINDOW_SECONDS = 10 * 60
LOCK_SECONDS = 5 * 60
MAX_FAILURES_PER_USER = 5
MAX_FAILURES_PER_IP = 25

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
PBKDF2_ITERATIONS = 390_000
