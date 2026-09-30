"""Modelos de seguridad: usuarios, roles, permisos, alcance por sede y sesiones."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    FetchedValue,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.sites.models import Site

role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("role.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permission.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=FetchedValue()),
    Column("created_by", BigInteger, ForeignKey("app_user.id")),
)

user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("app_user.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("role.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=FetchedValue()),
    Column("created_by", BigInteger, ForeignKey("app_user.id")),
)

user_site = Table(
    "user_site",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("app_user.id"), primary_key=True),
    Column("site_id", Integer, ForeignKey("site.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=FetchedValue()),
    Column("created_by", BigInteger, ForeignKey("app_user.id")),
)


class Permission(Base):
    __tablename__ = "permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60))
    module: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(300))


class Role(TimestampMixin, Base):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(300))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    permissions: Mapped[list[Permission]] = relationship(secondary=role_permission, lazy="selectin")


class AppUser(TimestampMixin, Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), server_default=FetchedValue())
    username: Mapped[str] = mapped_column(String(50))
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    auth_provider: Mapped[str] = mapped_column(String(10), default="LOCAL")
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))

    roles: Mapped[list[Role]] = relationship(
        secondary=user_role,
        primaryjoin=lambda: AppUser.id == user_role.c.user_id,
        secondaryjoin=lambda: Role.id == user_role.c.role_id,
        lazy="selectin",
    )
    sites: Mapped[list[Site]] = relationship(
        secondary=user_site,
        primaryjoin=lambda: AppUser.id == user_site.c.user_id,
        secondaryjoin=lambda: Site.id == user_site.c.site_id,
        lazy="selectin",
    )

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for r in self.roles if r.is_active for p in r.permissions}


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    token_hash: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(30))
    replaced_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("refresh_token.id"))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))

    user: Mapped[AppUser] = relationship(lazy="joined", innerjoin=True)
