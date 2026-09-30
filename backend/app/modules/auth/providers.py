"""Proveedores de autenticación.

Fase 1: LocalAuthProvider (contraseña con Argon2id).
Fase 3: se agregará LdapAuthProvider implementando el mismo protocolo, sin cambiar el resto.
"""

from typing import Protocol

from app.core.security import hash_password, password_needs_rehash, verify_password
from app.modules.users.models import AppUser


class AuthProvider(Protocol):
    name: str

    def verify(self, user: AppUser, password: str) -> bool: ...


class LocalAuthProvider:
    name = "LOCAL"

    def verify(self, user: AppUser, password: str) -> bool:
        if not verify_password(password, user.password_hash):
            return False
        if user.password_hash and password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        return True


_PROVIDERS: dict[str, AuthProvider] = {"LOCAL": LocalAuthProvider()}


def provider_for(user: AppUser | None) -> AuthProvider:
    if user is None:
        return _PROVIDERS["LOCAL"]
    provider = _PROVIDERS.get(user.auth_provider)
    if provider is None:  # p. ej., LDAP aún no habilitado
        raise LookupError(f"Proveedor de autenticación no disponible: {user.auth_provider}")
    return provider
