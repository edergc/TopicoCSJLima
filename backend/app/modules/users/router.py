import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.modules.auth.dependencies import ServiceContext, require
from app.modules.auth.schemas import SiteRef
from app.modules.users import service as users
from app.modules.users.models import AppUser, Permission, Role
from app.modules.users.schemas import (
    PermissionOut,
    RoleOut,
    RolePermissionsIn,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
    UserWithPasswordOut,
)
from app.shared.schemas import Page, PageParams

router = APIRouter(prefix="/admin", tags=["Administración: usuarios y roles"])

ReadCtx = Annotated[ServiceContext, Depends(require("user:read"))]
ManageCtx = Annotated[ServiceContext, Depends(require("user:manage"))]


def user_out(u: AppUser, ctx: ServiceContext) -> UserOut:
    return UserOut(
        public_id=u.public_id,
        username=u.username,
        full_name=u.full_name,
        email=u.email,
        auth_provider=u.auth_provider,
        is_active=u.is_active,
        must_change_password=u.must_change_password,
        is_locked=bool(u.locked_until and u.locked_until > ctx.clock.now()),
        last_login_at=u.last_login_at,
        roles=sorted(r.code for r in u.roles),
        sites=[SiteRef.model_validate(s) for s in sorted(u.sites, key=lambda s: s.id)],
        created_at=u.created_at,
    )


@router.get("/users", response_model=Page[UserOut])
def list_users(
    ctx: ReadCtx,
    paging: Annotated[PageParams, Depends()],
    q: Annotated[str | None, Query(max_length=100)] = None,
    active: bool | None = None,
) -> Page[UserOut]:
    rows, total = users.search_users(ctx.db, q, active, paging.offset, paging.size)
    return Page(items=[user_out(u, ctx) for u in rows], total=total, page=paging.page, size=paging.size)


@router.get("/users/{public_id}", response_model=UserOut)
def get_user(public_id: uuid.UUID, ctx: ReadCtx) -> UserOut:
    return user_out(users.get_user(ctx.db, public_id), ctx)


@router.post(
    "/users", response_model=UserWithPasswordOut, status_code=201, summary="Crear usuario (contraseña temporal)"
)
def create_user(body: UserCreateIn, ctx: ManageCtx) -> UserWithPasswordOut:
    user, temporary = users.UserAdminService(ctx).create(body)
    return UserWithPasswordOut(**user_out(user, ctx).model_dump(), temporary_password=temporary)


@router.patch("/users/{public_id}", response_model=UserOut, summary="Modificar usuario, roles y sedes")
def update_user(public_id: uuid.UUID, body: UserUpdateIn, ctx: ManageCtx) -> UserOut:
    return user_out(users.UserAdminService(ctx).update(public_id, body), ctx)


@router.post("/users/{public_id}/reset-password", response_model=UserWithPasswordOut)
def reset_password(public_id: uuid.UUID, ctx: ManageCtx) -> UserWithPasswordOut:
    user, temporary = users.UserAdminService(ctx).reset_password(public_id)
    return UserWithPasswordOut(**user_out(user, ctx).model_dump(), temporary_password=temporary)


@router.post("/users/{public_id}/unlock", response_model=UserOut)
def unlock(public_id: uuid.UUID, ctx: ManageCtx) -> UserOut:
    return user_out(users.UserAdminService(ctx).unlock(public_id), ctx)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(ctx: Annotated[ServiceContext, Depends(require("role:read"))]) -> list[Role]:
    return list(ctx.db.scalars(select(Role).order_by(Role.id)))


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
def set_role_permissions(
    role_id: int, body: RolePermissionsIn, ctx: Annotated[ServiceContext, Depends(require("role:manage"))]
) -> Role:
    return users.UserAdminService(ctx).set_role_permissions(role_id, body)


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(ctx: Annotated[ServiceContext, Depends(require("role:read"))]) -> list[Permission]:
    return list(ctx.db.scalars(select(Permission).order_by(Permission.module, Permission.code)))
