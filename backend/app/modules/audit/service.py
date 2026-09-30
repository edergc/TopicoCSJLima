"""Registro de auditoría funcional.

- `record` agrega el evento a la transacción del caso de uso (se confirma o revierte junto con él).
- `record_isolated` lo confirma en una transacción propia: se usa para eventos que deben
  persistir aunque la operación falle (accesos denegados, logins fallidos).
"""

import datetime as dt
import decimal
import enum
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.context import get_request_context
from app.core.logging import get_logger
from app.modules.audit.models import AuditEvent
from app.modules.auth.principal import CurrentUser

log = get_logger(__name__)

# Nunca deben aparecer en la auditoría.
_SENSITIVE_FIELDS = frozenset({"password", "password_hash", "token", "token_hash", "refresh_token", "secret"})


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, uuid.UUID | decimal.Decimal):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items() if str(k) not in _SENSITIVE_FIELDS}
    if isinstance(value, list | tuple | set | frozenset):
        return [_jsonable(v) for v in value]
    return str(value)


def snapshot(obj: Any, fields: Iterable[str]) -> dict[str, Any]:
    """Foto de los campos indicados de un objeto (para before/after)."""
    return {f: _jsonable(getattr(obj, f, None)) for f in fields if f not in _SENSITIVE_FIELDS}


def diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reduce before/after a los campos que cambiaron."""
    changed = [k for k in after if before.get(k) != after.get(k)]
    return {k: before.get(k) for k in changed}, {k: after.get(k) for k in changed}


def record(
    db: Session,
    *,
    action: str,
    actor: CurrentUser | None = None,
    username: str | None = None,
    result: str = "SUCCESS",
    resource_type: str | None = None,
    resource_id: object = None,
    site_id: int | None = None,
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    ctx = get_request_context()
    db.add(
        AuditEvent(
            user_id=actor.id if actor else None,
            username=(actor.username if actor else username),
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            request_id=ctx.request_id,
            action=action,
            resource_type=resource_type,
            resource_id=None if resource_id is None else str(resource_id)[:64],
            site_id=site_id,
            result=result,
            reason=reason[:500] if reason else None,
            before_data=_jsonable(before) if before is not None else None,
            after_data=_jsonable(after) if after is not None else None,
            metadata_=_jsonable(metadata) if metadata is not None else None,
        )
    )


def record_isolated(session_factory: sessionmaker[Session], **kwargs: Any) -> None:
    try:
        with session_factory() as session:
            record(session, **kwargs)
            session.commit()
    except Exception:  # la auditoría aislada nunca debe romper la respuesta al usuario
        log.exception("audit_isolated_failed", action=kwargs.get("action"))
