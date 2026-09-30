import uuid
from typing import Annotated

from pydantic import StringConstraints

from app.shared.schemas import ApiModel, ApiOut


class LoginIn(ApiModel):
    username: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=False)]


class ChangePasswordIn(ApiModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=False)]
    new_password: Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=False)]


class SiteRef(ApiOut):
    id: int
    code: str
    name: str
    short_name: str


class MeOut(ApiOut):
    public_id: uuid.UUID
    username: str
    full_name: str
    email: str | None
    must_change_password: bool
    roles: list[str]
    permissions: list[str]
    sites: list[SiteRef]


class TokenOut(ApiOut):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: MeOut
