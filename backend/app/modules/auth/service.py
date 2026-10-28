"""Casos de uso de autenticación: login, refresh rotativo, logout, cambio y recuperación de contraseña."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.context import get_request_context
from app.core.errors import BusinessRuleError, ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, hash_password, new_opaque_token, sha256_hex, verify_password
from app.modules.admin.parameters import get_int, get_str
from app.modules.audit import service as audit
from app.modules.auth.dependencies import to_current_user
from app.modules.auth.principal import CurrentUser
from app.modules.auth.providers import provider_for
from app.modules.users.models import AppUser, PasswordReset, RefreshToken

# Entre dos pedidos de enlace de recuperación del mismo usuario (evita llenar su buzón).
_RESET_REQUEST_INTERVAL = timedelta(minutes=2)
RESET_TEMPLATE = "PASSWORD_RESET"

# Si dos pestañas refrescan a la vez, la segunda usa un token recién rotado: no es un robo.
_ROTATION_GRACE = timedelta(seconds=30)


@dataclass(frozen=True)
class IssuedSession:
    user: AppUser
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


class AuthService:
    def __init__(self, db: Session, clock: Clock, settings: Settings, factory: sessionmaker[Session]) -> None:
        self.db = db
        self.clock = clock
        self.settings = settings
        self.factory = factory

    # ------------------------------------------------------------------ login
    def login(self, username: str, password: str) -> IssuedSession:
        now = self.clock.now()
        username = username.strip().lower()
        user = self.db.scalar(
            select(AppUser).where(AppUser.username == username).with_for_update(of=AppUser, key_share=True)
        )

        if user is None:
            verify_password(password, None)  # tiempo constante: no revela si el usuario existe
            self._audit_login_failure(username, None, "USER_NOT_FOUND")
            raise UnauthorizedError("INVALID_CREDENTIALS")

        if user.locked_until and user.locked_until > now:
            self._audit_login_failure(username, user, "ACCOUNT_LOCKED", result="DENIED")
            raise UnauthorizedError("ACCOUNT_LOCKED")

        try:
            valid = provider_for(user).verify(user, password)
        except LookupError:
            valid = False

        if not valid:
            max_attempts = get_int(self.db, "auth.max_failed_attempts", 5)
            user.failed_login_attempts += 1
            locked = user.failed_login_attempts >= max_attempts
            if locked:
                user.locked_until = now + timedelta(minutes=get_int(self.db, "auth.lockout_minutes", 15))
                user.failed_login_attempts = 0
            self.db.commit()
            self._audit_login_failure(username, user, "ACCOUNT_LOCKED_NOW" if locked else "BAD_PASSWORD")
            raise UnauthorizedError("ACCOUNT_LOCKED" if locked else "INVALID_CREDENTIALS")

        if not user.is_active:
            self.db.rollback()
            self._audit_login_failure(username, user, "ACCOUNT_DISABLED", result="DENIED")
            raise ForbiddenError("ACCOUNT_DISABLED")

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        hours = get_int(self.db, "auth.refresh_token_hours", 10)
        session = self._issue(user, family_id=uuid.uuid4(), expires_at=now + timedelta(hours=hours))
        audit.record(
            self.db, action="LOGIN", actor=to_current_user(user), resource_type="user", resource_id=user.public_id
        )
        self.db.commit()
        return session

    # ---------------------------------------------------------------- refresh
    def refresh(self, refresh_token: str | None) -> IssuedSession:
        if not refresh_token:
            raise UnauthorizedError("SESSION_EXPIRED")
        now = self.clock.now()
        token = self.db.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == sha256_hex(refresh_token))
            .with_for_update(of=RefreshToken, key_share=True)
        )
        if token is None:
            raise UnauthorizedError("SESSION_EXPIRED")

        if token.revoked_at is not None:
            if token.revoked_reason == "ROTATED" and now - token.revoked_at > _ROTATION_GRACE:
                # Reutilización de un token ya rotado: posible robo → se revoca toda la sesión.
                self._revoke_family(token.family_id, "REUSE_DETECTED", now)
                audit.record(
                    self.db,
                    action="SESSION_REUSE_DETECTED",
                    actor=to_current_user(token.user),
                    result="DENIED",
                    resource_type="user",
                    resource_id=token.user.public_id,
                )
                self.db.commit()
            raise UnauthorizedError("SESSION_EXPIRED")

        if token.expires_at <= now or not token.user.is_active:
            token.revoked_at, token.revoked_reason = now, "LOGOUT"
            self.db.commit()
            raise UnauthorizedError("SESSION_EXPIRED")

        session = self._issue(token.user, family_id=token.family_id, expires_at=token.expires_at)
        new_token = self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(session.refresh_token))
        )
        token.revoked_at, token.revoked_reason = now, "ROTATED"
        token.replaced_by_id = new_token.id if new_token else None
        self.db.commit()
        return session

    # ----------------------------------------------------------------- logout
    def logout(self, refresh_token: str | None, actor: CurrentUser | None) -> None:
        now = self.clock.now()
        if refresh_token:
            token = self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(refresh_token)))
            if token is not None and token.revoked_at is None:
                token.revoked_at, token.revoked_reason = now, "LOGOUT"
                actor = actor or to_current_user(token.user)
        if actor is not None:
            audit.record(self.db, action="LOGOUT", actor=actor, resource_type="user", resource_id=actor.public_id)
        self.db.commit()

    # -------------------------------------------------------- change password
    def change_password(self, actor: CurrentUser, current_password: str, new_password: str) -> IssuedSession:
        user = self.db.get(AppUser, actor.id, with_for_update={"key_share": True})
        if user is None or user.auth_provider != "LOCAL":
            raise ForbiddenError()
        if not verify_password(current_password, user.password_hash):
            audit.record_isolated(
                self.factory, action="PASSWORD_CHANGE", actor=actor, result="FAILURE", reason="PASSWORD_INCORRECT"
            )
            raise BusinessRuleError("PASSWORD_INCORRECT")
        validate_password_policy(self.db, new_password, user.username)
        if verify_password(new_password, user.password_hash):
            raise BusinessRuleError("PASSWORD_POLICY", "La nueva contraseña debe ser distinta de la actual.")

        now = self.clock.now()
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.must_change_password = False
        # Cierra todas las demás sesiones del usuario.
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason="PASSWORD_CHANGED")
        )
        hours = get_int(self.db, "auth.refresh_token_hours", 10)
        session = self._issue(user, family_id=uuid.uuid4(), expires_at=now + timedelta(hours=hours))
        audit.record(self.db, action="PASSWORD_CHANGE", actor=actor, resource_type="user", resource_id=user.public_id)
        self.db.commit()
        return session

    # ------------------------------------------------------ recuperar contraseña
    def request_password_reset(self, username: str) -> None:
        """Envía por correo un enlace de un solo uso. Nunca revela si el usuario existe o tiene correo."""
        from app.modules.notifications import service as notifications
        from app.modules.ratings.service import public_base_url

        now = self.clock.now()
        username = username.strip().lower()
        user = self.db.scalar(select(AppUser).where(AppUser.username == username).with_for_update(of=AppUser))
        base = public_base_url(self.settings)
        reason = None
        if user is None:
            reason = "USER_NOT_FOUND"
        elif not user.is_active:
            reason = "ACCOUNT_DISABLED"
        elif user.auth_provider != "LOCAL":
            reason = "EXTERNAL_PROVIDER"
        elif not user.email:
            reason = "NO_EMAIL"
        elif not base:
            reason = "NO_PUBLIC_URL"
        elif self.db.scalar(
            select(PasswordReset.id).where(
                PasswordReset.user_id == user.id,
                PasswordReset.used_at.is_(None),
                PasswordReset.requested_at > now - _RESET_REQUEST_INTERVAL,
            )
        ):
            reason = "RECENT_REQUEST"
        if reason is not None:
            self.db.rollback()
            self._audit_reset_failure(username, user, reason)
            return
        assert user is not None
        assert user.email is not None
        assert base is not None

        self._invalidate_resets(user.id, now)
        minutes = max(get_int(self.db, "auth.password_reset_minutes", 30), 5)
        plain = new_opaque_token()
        self.db.add(
            PasswordReset(
                user_id=user.id,
                token_hash=sha256_hex(plain),
                requested_at=now,
                expires_at=now + timedelta(minutes=minutes),
                ip=get_request_context().ip,
            )
        )
        sent = notifications.enqueue_direct(
            self.db,
            template_code=RESET_TEMPLATE,
            recipient=user.email,
            context={
                "full_name": user.full_name,
                "username": user.username,
                "reset_url": f"{base}/recuperar-clave#{plain}",
                "valid_minutes": minutes,
                "institution_name": get_str(self.db, "institution.name", "Corte Superior de Justicia de Lima"),
            },
            now=now,
            created_by=None,
        )
        if not sent:
            self.db.rollback()
            self._audit_reset_failure(username, user, "TEMPLATE_INACTIVE")
            return
        audit.record(
            self.db,
            action="PASSWORD_RESET_REQUEST",
            actor=to_current_user(user),
            resource_type="user",
            resource_id=user.public_id,
        )
        self.db.commit()

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        now = self.clock.now()
        reset = self.db.scalar(
            select(PasswordReset)
            .where(PasswordReset.token_hash == sha256_hex(token.strip()))
            .with_for_update(of=PasswordReset)
        )
        if reset is None or reset.used_at is not None:
            raise BusinessRuleError("RESET_LINK_INVALID")
        if reset.expires_at <= now:
            raise BusinessRuleError("RESET_LINK_EXPIRED")
        user = reset.user
        if not user.is_active or user.auth_provider != "LOCAL":
            raise BusinessRuleError("RESET_LINK_INVALID")
        validate_password_policy(self.db, new_password, user.username)

        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.must_change_password = False
        # Quien recupera su contraseña también recupera el acceso si estaba bloqueado por intentos fallidos.
        user.failed_login_attempts = 0
        user.locked_until = None
        self._invalidate_resets(user.id, now)
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason="PASSWORD_CHANGED")
        )
        audit.record(
            self.db,
            action="PASSWORD_RESET_CONFIRM",
            actor=to_current_user(user),
            resource_type="user",
            resource_id=user.public_id,
        )
        self.db.commit()

    # -------------------------------------------------------------- internos
    def _invalidate_resets(self, user_id: int, now: datetime) -> None:
        self.db.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user_id, PasswordReset.used_at.is_(None))
            .values(used_at=now)
        )

    def _audit_reset_failure(self, username: str, user: AppUser | None, reason: str) -> None:
        audit.record_isolated(
            self.factory,
            action="PASSWORD_RESET_REQUEST",
            actor=to_current_user(user) if user else None,
            username=username[:50],
            result="FAILURE",
            resource_type="user",
            resource_id=user.public_id if user else None,
            reason=reason,
        )

    def _issue(self, user: AppUser, *, family_id: uuid.UUID, expires_at: datetime) -> IssuedSession:
        now = self.clock.now()
        access, expires_in = create_access_token(
            subject=str(user.public_id),
            secret=self.settings.effective_jwt_secret(),
            algorithm=self.settings.jwt_algorithm,
            now=now,
            minutes=self.settings.access_token_minutes,
        )
        plain = new_opaque_token()
        ctx = get_request_context()
        self.db.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id,
                token_hash=sha256_hex(plain),
                issued_at=now,
                expires_at=expires_at,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
            )
        )
        self.db.flush()
        return IssuedSession(user, access, expires_in, plain, expires_at)

    def _revoke_family(self, family_id: uuid.UUID, reason: str, now: datetime) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason)
        )

    def _audit_login_failure(
        self, username: str, user: AppUser | None, reason: str, *, result: str = "FAILURE"
    ) -> None:
        audit.record_isolated(
            self.factory,
            action="LOGIN",
            actor=to_current_user(user) if user else None,
            username=username[:50],
            result=result,
            resource_type="user",
            resource_id=user.public_id if user else None,
            reason=reason,
        )


_HAS_LETTER = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]")
_HAS_DIGIT = re.compile(r"\d")


def validate_password_policy(db: Session, password: str, username: str) -> None:
    min_length = get_int(db, "auth.password_min_length", 10)
    problems = []
    if len(password) < min_length:
        problems.append(f"Debe tener al menos {min_length} caracteres.")
    if not _HAS_LETTER.search(password) or not _HAS_DIGIT.search(password):
        problems.append("Debe combinar letras y números.")
    if username.lower() in password.lower():
        problems.append("No debe contener el nombre de usuario.")
    if len(password) > 128:
        problems.append("No debe superar 128 caracteres.")
    if problems:
        raise BusinessRuleError("PASSWORD_POLICY", details=problems)


def count_active_sessions(db: Session, user_id: int, now: datetime) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)
        )
        or 0
    )
