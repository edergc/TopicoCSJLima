"""Administración de usuarios, roles y permisos (todo auditado)."""

import secrets
import string
import uuid

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.modules.audit.service import diff
from app.modules.auth.dependencies import ServiceContext
from app.modules.sites.models import Site
from app.modules.users.models import AppUser, Permission, RefreshToken, Role
from app.modules.users.schemas import RolePermissionsIn, UserCreateIn, UserUpdateIn

# Permisos que el rol ADMIN no puede perder (evita que el sistema quede sin administración).
_ADMIN_LOCKOUT_GUARD = frozenset({"user:manage", "role:manage"})


def generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in candidate) and any(c.isalpha() for c in candidate):
            return candidate


def _user_state(user: AppUser) -> dict[str, object]:
    return {
        "full_name": user.full_name,
        "email": user.email,
        "is_active": user.is_active,
        "roles": sorted(r.code for r in user.roles),
        "sites": sorted(s.code for s in user.sites),
    }


def get_user(db: Session, public_id: uuid.UUID) -> AppUser:
    user = db.scalar(select(AppUser).where(AppUser.public_id == public_id))
    if user is None:
        raise NotFoundError("NOT_FOUND", "El usuario no existe.")
    return user


def search_users(db: Session, q: str | None, active: bool | None, offset: int, limit: int) -> tuple[list[AppUser], int]:
    stmt = select(AppUser)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(AppUser.username.ilike(pattern), AppUser.full_name.ilike(pattern)))
    if active is not None:
        stmt = stmt.where(AppUser.is_active.is_(active))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    return list(db.scalars(stmt.order_by(AppUser.username).offset(offset).limit(limit))), int(total)


class UserAdminService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.db = ctx.db

    def _roles(self, codes: list[str]) -> list[Role]:
        roles = list(self.db.scalars(select(Role).where(Role.code.in_(codes), Role.is_active)))
        if len(roles) != len(set(codes)):
            raise BusinessRuleError("VALIDATION_ERROR", "Uno o más roles no existen o están inactivos.")
        return roles

    def _sites(self, ids: list[int]) -> list[Site]:
        sites = list(self.db.scalars(select(Site).where(Site.id.in_(ids))))
        if len(sites) != len(set(ids)):
            raise BusinessRuleError("VALIDATION_ERROR", "Una o más sedes no existen.")
        return sites

    def create(self, data: UserCreateIn) -> tuple[AppUser, str]:
        if self.db.scalar(select(AppUser.id).where(AppUser.username == data.username)):
            raise ConflictError("USERNAME_TAKEN")
        temporary = generate_temporary_password()
        user = AppUser(
            username=data.username,
            full_name=data.full_name,
            email=data.email,
            auth_provider="LOCAL",
            password_hash=hash_password(temporary),
            must_change_password=True,
            is_active=True,
            failed_login_attempts=0,
            created_by=self.ctx.user.id,
            updated_by=self.ctx.user.id,
        )
        user.roles = self._roles(data.role_codes)
        user.sites = self._sites(data.site_ids)
        self.db.add(user)
        self.db.flush()
        self.ctx.audit(
            action="USER_CREATE",
            resource_type="user",
            resource_id=user.public_id,
            after={"username": user.username, **_user_state(user)},
        )
        self.db.commit()
        return user, temporary

    def update(self, public_id: uuid.UUID, data: UserUpdateIn) -> AppUser:
        user = get_user(self.db, public_id)
        before = _user_state(user)
        is_self = user.id == self.ctx.user.id
        values = data.model_dump(exclude_unset=True)
        if is_self and values.get("is_active") is False:
            raise BusinessRuleError("VALIDATION_ERROR", "No puede desactivar su propia cuenta.")
        if "full_name" in values:
            user.full_name = values["full_name"]
        if "email" in values:
            user.email = values["email"]
        if "is_active" in values:
            user.is_active = values["is_active"]
        if data.role_codes is not None:
            roles = self._roles(data.role_codes)
            if is_self and "ADMIN" in before["roles"] and "ADMIN" not in {r.code for r in roles}:  # type: ignore[operator]
                raise BusinessRuleError("VALIDATION_ERROR", "No puede quitarse a sí mismo el rol de administrador.")
            user.roles = roles
        if data.site_ids is not None:
            user.sites = self._sites(data.site_ids)
        user.updated_by = self.ctx.user.id
        if values.get("is_active") is False:
            self._revoke_sessions(user.id, "ADMIN")
        self.db.flush()
        b, a = diff(before, _user_state(user))
        if a:
            action = "USER_PERMISSIONS_CHANGE" if {"roles", "sites"} & a.keys() else "USER_UPDATE"
            self.ctx.audit(action=action, resource_type="user", resource_id=user.public_id, before=b, after=a)
        self.db.commit()
        return user

    def reset_password(self, public_id: uuid.UUID) -> tuple[AppUser, str]:
        user = get_user(self.db, public_id)
        if user.auth_provider != "LOCAL":
            raise BusinessRuleError("VALIDATION_ERROR", "El usuario se autentica con la cuenta institucional.")
        temporary = generate_temporary_password()
        user.password_hash = hash_password(temporary)
        user.must_change_password = True
        user.failed_login_attempts = 0
        user.locked_until = None
        user.password_changed_at = self.ctx.clock.now()
        user.updated_by = self.ctx.user.id
        self._revoke_sessions(user.id, "ADMIN")
        self.ctx.audit(action="USER_PASSWORD_RESET", resource_type="user", resource_id=user.public_id)
        self.db.commit()
        return user, temporary

    def unlock(self, public_id: uuid.UUID) -> AppUser:
        user = get_user(self.db, public_id)
        user.failed_login_attempts = 0
        user.locked_until = None
        self.ctx.audit(action="USER_UNLOCK", resource_type="user", resource_id=user.public_id)
        self.db.commit()
        return user

    def set_role_permissions(self, role_id: int, data: RolePermissionsIn) -> Role:
        role = self.db.get(Role, role_id)
        if role is None:
            raise NotFoundError()
        permissions = list(self.db.scalars(select(Permission).where(Permission.code.in_(data.permission_codes))))
        if len(permissions) != len(set(data.permission_codes)):
            raise BusinessRuleError("VALIDATION_ERROR", "Uno o más permisos no existen.")
        new_codes = {p.code for p in permissions}
        if role.code == "ADMIN" and not new_codes >= _ADMIN_LOCKOUT_GUARD:
            raise BusinessRuleError(
                "VALIDATION_ERROR", "El rol Administrador debe conservar la gestión de usuarios y roles."
            )
        before = sorted(p.code for p in role.permissions)
        role.permissions = permissions
        self.ctx.audit(
            action="ROLE_PERMISSIONS_CHANGE",
            resource_type="role",
            resource_id=role.code,
            before={"permissions": before},
            after={"permissions": sorted(new_codes)},
        )
        self.db.commit()
        return role

    def _revoke_sessions(self, user_id: int, reason: str) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=self.ctx.clock.now(), revoked_reason=reason)
        )
