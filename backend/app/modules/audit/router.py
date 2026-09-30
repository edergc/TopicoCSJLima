from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text

from app.modules.audit.models import AuditEvent
from app.modules.auth.dependencies import ServiceContext, require
from app.shared.schemas import ApiOut, Page, PageParams

router = APIRouter(prefix="/audit-events", tags=["Auditoría"])


class AuditEventOut(ApiOut):
    chain_seq: int
    occurred_at: datetime
    username: str | None
    ip: str | None
    request_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    site_id: int | None
    result: str
    reason: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    metadata: dict[str, Any] | None


class ChainProblemOut(ApiOut):
    chain_seq: int
    problem: str


class ChainVerificationOut(ApiOut):
    intact: bool
    events_checked: int
    problems: list[ChainProblemOut]
    verified_at: datetime


@router.get("", response_model=Page[AuditEventOut], summary="Consultar la auditoría")
def list_events(
    ctx: Annotated[ServiceContext, Depends(require("audit:read"))],
    paging: Annotated[PageParams, Depends()],
    date_from: date | None = None,
    date_to: date | None = None,
    username: Annotated[str | None, Query(max_length=50)] = None,
    action: Annotated[str | None, Query(max_length=60)] = None,
    resource_type: Annotated[str | None, Query(max_length=40)] = None,
    resource_id: Annotated[str | None, Query(max_length=64)] = None,
    site_id: int | None = None,
    result: Annotated[str | None, Query(max_length=10)] = None,
) -> Page[AuditEventOut]:
    stmt = select(AuditEvent)
    tz = ctx.clock.tz
    if date_from:
        stmt = stmt.where(AuditEvent.occurred_at >= datetime.combine(date_from, datetime.min.time(), tz))
    if date_to:
        stmt = stmt.where(
            AuditEvent.occurred_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tz)
        )
    if username:
        stmt = stmt.where(AuditEvent.username == username.lower())
    if action:
        stmt = stmt.where(AuditEvent.action == action.upper())
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditEvent.resource_id == resource_id)
    if site_id is not None:
        stmt = stmt.where(AuditEvent.site_id == site_id)
    if result:
        stmt = stmt.where(AuditEvent.result == result.upper())
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = ctx.db.scalars(stmt.order_by(AuditEvent.chain_seq.desc()).offset(paging.offset).limit(paging.size))
    items = [
        AuditEventOut(
            chain_seq=e.chain_seq,
            occurred_at=e.occurred_at,
            username=e.username,
            ip=str(e.ip) if e.ip else None,
            request_id=e.request_id,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            site_id=e.site_id,
            result=e.result,
            reason=e.reason,
            before_data=e.before_data,
            after_data=e.after_data,
            metadata=e.metadata_,
        )
        for e in rows
    ]
    return Page(items=items, total=total, page=paging.page, size=paging.size)


@router.post(
    "/verify", response_model=ChainVerificationOut, summary="Verificar la integridad de la cadena de auditoría"
)
def verify_chain(ctx: Annotated[ServiceContext, Depends(require("audit:verify"))]) -> ChainVerificationOut:
    problems = ctx.db.execute(text("SELECT chain_seq, problem FROM topico.verify_audit_chain()")).all()
    checked = ctx.db.scalar(select(func.count()).select_from(AuditEvent)) or 0
    ctx.audit(
        action="AUDIT_CHAIN_VERIFY",
        resource_type="audit_event",
        result="SUCCESS" if not problems else "FAILURE",
        metadata={"events_checked": checked, "problems": len(problems)},
    )
    ctx.db.commit()
    return ChainVerificationOut(
        intact=not problems,
        events_checked=checked,
        problems=[ChainProblemOut(chain_seq=p[0], problem=p[1]) for p in problems[:100]],
        verified_at=ctx.clock.now(),
    )
