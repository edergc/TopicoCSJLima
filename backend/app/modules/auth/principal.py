"""Usuario autenticado de la solicitud en curso (inmutable, sin dependencias del ORM)."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: int
    public_id: uuid.UUID
    username: str
    full_name: str
    permissions: frozenset[str]
    site_ids: frozenset[int]
    must_change_password: bool

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def can_access_site(self, site_id: int) -> bool:
        return site_id in self.site_ids
