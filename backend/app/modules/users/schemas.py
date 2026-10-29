import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, EmailStr, Field, StringConstraints

from app.modules.auth.schemas import SiteRef
from app.shared.schemas import ApiModel, ApiOut


def _username_is_dni(value: str) -> str:
    if not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError("El usuario es el DNI: exactamente 8 dígitos, solo números.")
    return value


# El usuario de ingreso es el DNI de la persona: 8 dígitos 0-9 (con ceros a la izquierda o a la derecha).
Username = Annotated[
    str,
    BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
    AfterValidator(_username_is_dni),
]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]


class UserCreateIn(ApiModel):
    username: Username
    full_name: FullName
    email: EmailStr | None = None
    role_codes: list[str] = Field(min_length=1)
    site_ids: list[int] = Field(default_factory=list)


class UserUpdateIn(ApiModel):
    full_name: FullName | None = None
    email: EmailStr | None = None
    is_active: bool | None = None
    role_codes: list[str] | None = Field(default=None, min_length=1)
    site_ids: list[int] | None = None


class UserOut(ApiOut):
    public_id: uuid.UUID
    username: str
    full_name: str
    email: str | None
    auth_provider: str
    is_active: bool
    must_change_password: bool
    is_locked: bool
    last_login_at: datetime | None
    roles: list[str]
    sites: list[SiteRef]
    created_at: datetime


class UserWithPasswordOut(UserOut):
    temporary_password: str = Field(description="Se muestra UNA sola vez. El usuario deberá cambiarla al ingresar.")


class PermissionOut(ApiOut):
    code: str
    module: str
    description: str


class RoleOut(ApiOut):
    id: int
    code: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[PermissionOut]


class RolePermissionsIn(ApiModel):
    permission_codes: list[str]
