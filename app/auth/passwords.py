"""Hash e regras de senha. Senhas nunca ficam em texto puro: scrypt (ou PBKDF2) com sal individual."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from .settings import DEFAULT_PASSWORD, MIN_PASSWORD_LENGTH, PBKDF2_ITERATIONS, SCRYPT_N, SCRYPT_P, SCRYPT_R


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    if hasattr(hashlib, "scrypt"):
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
        return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"
    # Python sem scrypt (compilado sem OpenSSL 1.1): PBKDF2 tambem e seguro.
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32)
    return f"pbkdf2${PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if parts[0] == "scrypt":
            _, n, r, p, salt, expected = parts
            digest = hashlib.scrypt(
                password.encode("utf-8"),
                salt=base64.b64decode(salt),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=32,
            )
        elif parts[0] == "pbkdf2":
            _, iterations, salt, expected = parts
            digest = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), base64.b64decode(salt), int(iterations), dklen=32
            )
        else:
            return False
        return hmac.compare_digest(digest, base64.b64decode(expected))
    except (ValueError, TypeError, AttributeError):
        return False


_dummy_hash: str | None = None


def burn_time() -> None:
    """Gasta o mesmo tempo de uma verificacao real, para nao revelar se o usuario existe."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("tv-qb-dummy")
    verify_password("x", _dummy_hash)


def password_problem(password: str, username: str = "") -> str | None:
    """Regras para senhas novas. Devolve o motivo da recusa ou None se estiver ok."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
    if len(password) > 200:
        return "A senha é longa demais (máximo de 200 caracteres)."
    if username and password.lower() == username.lower():
        return "A senha não pode ser igual ao nome de usuário."
    if password.lower() == DEFAULT_PASSWORD:
        return "Escolha uma senha diferente da senha padrão."
    return None
