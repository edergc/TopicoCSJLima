"""Endpoints de autenticación.

El access token (15 min) viaja en el cuerpo y el frontend lo mantiene en memoria.
El refresh token viaja SOLO en una cookie HttpOnly + SameSite=Strict, restringida a /api/v1/auth.
Protección CSRF de /refresh y /logout: SameSite=Strict + cabecera obligatoria X-Requested-With.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.core.config import API_PREFIX, Settings
from app.core.errors import ForbiddenError
from app.core.ratelimit import limiter
from app.modules.auth.dependencies import (
    AuthenticatedUser,
    ClockDep,
    DbDep,
    FactoryDep,
    SettingsDep,
)
from app.modules.auth.schemas import ChangePasswordIn, LoginIn, MeOut, SiteRef, TokenOut
from app.modules.auth.service import AuthService, IssuedSession
from app.modules.users.models import AppUser

router = APIRouter(prefix="/auth", tags=["Autenticación"])

_COOKIE_PATH = f"{API_PREFIX}/auth"


def me_out(user: AppUser) -> MeOut:
    return MeOut(
        public_id=user.public_id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        must_change_password=user.must_change_password,
        roles=sorted(r.code for r in user.roles if r.is_active),
        permissions=sorted(user.permission_codes),
        sites=[SiteRef.model_validate(s) for s in sorted(user.sites, key=lambda s: s.id) if s.is_active],
    )


def _require_xhr(request: Request) -> None:
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise ForbiddenError("CSRF_CHECK_FAILED")


def _set_refresh_cookie(response: Response, session: IssuedSession, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=session.refresh_token,
        expires=session.refresh_expires_at,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )


def _token_out(session: IssuedSession) -> TokenOut:
    return TokenOut(access_token=session.access_token, expires_in=session.expires_in, user=me_out(session.user))


@router.post("/login", response_model=TokenOut, summary="Iniciar sesión")
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    body: LoginIn,
    db: DbDep,
    clock: ClockDep,
    settings: SettingsDep,
    factory: FactoryDep,
) -> TokenOut:
    session = AuthService(db, clock, settings, factory).login(body.username, body.password)
    _set_refresh_cookie(response, session, settings)
    return _token_out(session)


@router.post("/refresh", response_model=TokenOut, summary="Renovar el access token")
@limiter.limit("30/minute")
def refresh(
    request: Request,
    response: Response,
    db: DbDep,
    clock: ClockDep,
    settings: SettingsDep,
    factory: FactoryDep,
    _: Annotated[None, Depends(_require_xhr)],
) -> TokenOut:
    token = request.cookies.get(settings.refresh_cookie_name)
    session = AuthService(db, clock, settings, factory).refresh(token)
    _set_refresh_cookie(response, session, settings)
    return _token_out(session)


@router.post("/logout", status_code=204, summary="Cerrar sesión")
def logout(
    request: Request,
    response: Response,
    db: DbDep,
    clock: ClockDep,
    settings: SettingsDep,
    factory: FactoryDep,
    _: Annotated[None, Depends(_require_xhr)],
) -> Response:
    AuthService(db, clock, settings, factory).logout(request.cookies.get(settings.refresh_cookie_name), None)
    response.status_code = 204
    response.delete_cookie(settings.refresh_cookie_name, path=_COOKIE_PATH)
    return response


@router.get("/me", response_model=MeOut, summary="Usuario actual, permisos y sedes")
def me(user: AuthenticatedUser, db: DbDep) -> MeOut:
    entity = db.scalar(select(AppUser).where(AppUser.id == user.id))
    assert entity is not None
    return me_out(entity)


@router.post("/change-password", response_model=TokenOut, summary="Cambiar la contraseña propia")
@limiter.limit("5/minute")
def change_password(
    request: Request,
    response: Response,
    body: ChangePasswordIn,
    user: AuthenticatedUser,
    db: DbDep,
    clock: ClockDep,
    settings: SettingsDep,
    factory: FactoryDep,
) -> TokenOut:
    session = AuthService(db, clock, settings, factory).change_password(user, body.current_password, body.new_password)
    _set_refresh_cookie(response, session, settings)
    return _token_out(session)
