"""Dependencias de autenticación/autorización y contexto de servicio.

Uso en routers:
    ctx: Annotated[ServiceContext, Depends(require("appointment:create"))]

`require` valida: token vigente → usuario activo → contraseña no pendiente de cambio → permiso.
El alcance por sede se valida dentro del servicio con `ctx.require_site(site_id)`, porque la
sede suele conocerse recién al cargar el recurso.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.modules.audit import service as audit
from app.modules.auth.principal import CurrentUser
from app.modules.users.models import AppUser

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def get_session_factory(request: Request) -> sessionmaker[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    return factory


DbDep = Annotated[Session, Depends(get_db)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
FactoryDep = Annotated[sessionmaker[Session], Depends(get_session_factory)]


def to_current_user(user: AppUser) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        public_id=user.public_id,
        username=user.username,
        full_name=user.full_name,
        permissions=frozenset(user.permission_codes),
        site_ids=frozenset(s.id for s in user.sites if s.is_active),
        must_change_password=user.must_change_password,
    )


def get_authenticated_user(
    db: DbDep,
    clock: ClockDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """Usuario autenticado, sin exigir el cambio de contraseña pendiente."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("UNAUTHORIZED")
    payload = decode_access_token(
        credentials.credentials,
        secret=settings.effective_jwt_secret(),
        algorithm=settings.jwt_algorithm,
        now=clock.now(),
    )
    try:
        public_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise UnauthorizedError("TOKEN_INVALID") from exc
    user = db.scalar(select(AppUser).where(AppUser.public_id == public_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("TOKEN_INVALID")
    return to_current_user(user)


AuthenticatedUser = Annotated[CurrentUser, Depends(get_authenticated_user)]


@dataclass
class ServiceContext:
    """Todo lo que un caso de uso necesita: sesión, usuario, reloj, configuración."""

    db: Session
    user: CurrentUser
    clock: Clock
    settings: Settings
    session_factory: sessionmaker[Session]
    permission: str | None = None

    def audit(self, **kwargs: Any) -> None:
        audit.record(self.db, actor=self.user, **kwargs)

    def deny(self, code: str, *, action: str, site_id: int | None = None, resource: str | None = None) -> None:
        audit.record_isolated(
            self.session_factory,
            action="ACCESS_DENIED",
            actor=self.user,
            result="DENIED",
            resource_type=resource,
            site_id=site_id,
            reason=code,
            metadata={"attempted_action": action, "permission": self.permission},
        )
        raise ForbiddenError(code)

    def require_site(self, site_id: int, *, action: str) -> None:
        """Caso crítico 5: un usuario no opera sedes que no tiene asignadas."""
        if not self.user.can_access_site(site_id):
            self.deny("SITE_FORBIDDEN", action=action, site_id=site_id)

    def require_permission(self, permission: str, *, action: str) -> None:
        if not self.user.has(permission):
            self.deny("FORBIDDEN", action=action)


def require(permission: str | None = None) -> Callable[..., ServiceContext]:
    """Dependencia: exige usuario autenticado con el permiso indicado (None = solo autenticado)."""

    def dependency(
        request: Request,
        db: DbDep,
        clock: ClockDep,
        settings: SettingsDep,
        factory: FactoryDep,
        user: AuthenticatedUser,
    ) -> ServiceContext:
        ctx = ServiceContext(
            db=db, user=user, clock=clock, settings=settings, session_factory=factory, permission=permission
        )
        if user.must_change_password:
            raise ForbiddenError("PASSWORD_CHANGE_REQUIRED")
        if permission is not None and not user.has(permission):
            ctx.deny("FORBIDDEN", action=f"{request.method} {request.url.path}")
        return ctx

    return dependency
