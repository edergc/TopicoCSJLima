"""Primitivas criptográficas: hash de contraseñas (Argon2id), JWT de acceso y tokens opacos."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.errors import UnauthorizedError

# Parámetros recomendados por OWASP para Argon2id (m=19 MiB, t=2, p=1).
_hasher = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)

# Hash de referencia para igualar tiempos cuando el usuario no existe (evita enumeración de usuarios).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

ACCESS_TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(
    *, subject: str, secret: str, algorithm: str, now: datetime, minutes: int, extra: dict[str, Any] | None = None
) -> tuple[str, int]:
    expires = now + timedelta(minutes=minutes)
    payload = {
        "sub": subject,
        "typ": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": uuid.uuid4().hex,
        **(extra or {}),
    }
    return jwt.encode(payload, secret, algorithm=algorithm), minutes * 60


def decode_access_token(token: str, *, secret: str, algorithm: str, now: datetime) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            options={
                "require": ["sub", "exp", "iat", "typ"],
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("TOKEN_INVALID") from exc
    # Los tiempos se validan con el reloj de la aplicación (única fuente de verdad, inyectable en pruebas).
    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("TOKEN_INVALID")
    if int(payload["exp"]) <= int(now.timestamp()):
        raise UnauthorizedError("TOKEN_EXPIRED")
    return payload


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
