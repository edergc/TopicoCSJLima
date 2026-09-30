"""Administración de parámetros, motivos y plantillas de notificación (todo auditado)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import Field, StringConstraints
from sqlalchemy import select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.appointments.models import Reason
from app.modules.appointments.schemas import ReasonOut
from app.modules.audit.service import diff, snapshot
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.notifications.models import NotificationTemplate
from app.modules.notifications.templating import SAMPLE_CONTEXT, render, validate_template
from app.modules.sites.models import SystemParameter
from app.shared.schemas import ApiModel, ApiOut

router = APIRouter(prefix="/admin", tags=["Administración: parámetros y catálogos"])

# ---------------------------------------------------------------- parámetros


class ParameterOut(ApiOut):
    key: str
    value: Any
    value_type: str
    description: str
    is_editable: bool
    updated_at: datetime


class ParameterIn(ApiModel):
    value: Any


def _check_type(value_type: str, value: Any) -> None:
    ok = {
        "int": isinstance(value, int) and not isinstance(value, bool),
        "bool": isinstance(value, bool),
        "string": isinstance(value, str),
        "json": isinstance(value, dict | list),
    }.get(value_type, False)
    if not ok:
        raise BusinessRuleError("PARAMETER_TYPE_MISMATCH", details={"expected": value_type})


@router.get("/parameters", response_model=list[ParameterOut])
def list_parameters(ctx: Annotated[ServiceContext, Depends(require("parameter:manage"))]) -> list[SystemParameter]:
    return list(ctx.db.scalars(select(SystemParameter).order_by(SystemParameter.key)))


@router.put("/parameters/{key}", response_model=ParameterOut)
def update_parameter(
    key: str, body: ParameterIn, ctx: Annotated[ServiceContext, Depends(require("parameter:manage"))]
) -> SystemParameter:
    param = ctx.db.get(SystemParameter, key)
    if param is None:
        raise NotFoundError()
    if not param.is_editable:
        raise BusinessRuleError("PARAMETER_NOT_EDITABLE")
    _check_type(param.value_type, body.value)
    if param.value_type == "int" and body.value < 0:
        raise BusinessRuleError("PARAMETER_TYPE_MISMATCH", "El valor no puede ser negativo.")
    before = param.value
    param.value = body.value
    param.updated_by = ctx.user.id
    ctx.audit(
        action="PARAMETER_CHANGE",
        resource_type="system_parameter",
        resource_id=key,
        before={"value": before},
        after={"value": body.value},
    )
    ctx.db.commit()
    ctx.db.refresh(param)
    return param


# ------------------------------------------------------------------- motivos

ReasonType = Literal["CANCEL", "VOID", "NO_SHOW", "REQUEUE"]
_REASON_FIELDS = ("type", "code", "label", "requires_note", "is_active", "sort_order")


class ReasonAdminOut(ReasonOut):
    is_active: bool
    sort_order: int


class ReasonCreateIn(ApiModel):
    type: ReasonType
    code: Annotated[str, StringConstraints(to_upper=True, pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
    label: Annotated[str, StringConstraints(min_length=3, max_length=150)]
    requires_note: bool = False
    sort_order: int = Field(default=50, ge=0, le=999)


class ReasonUpdateIn(ApiModel):
    label: Annotated[str, StringConstraints(min_length=3, max_length=150)] | None = None
    requires_note: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=999)


CatalogCtx = Annotated[ServiceContext, Depends(require("catalog:manage"))]


@router.get("/reasons", response_model=list[ReasonAdminOut])
def list_all_reasons(ctx: CatalogCtx) -> list[Reason]:
    return list(ctx.db.scalars(select(Reason).order_by(Reason.type, Reason.sort_order)))


@router.post("/reasons", response_model=ReasonAdminOut, status_code=201)
def create_reason(body: ReasonCreateIn, ctx: CatalogCtx) -> Reason:
    exists = ctx.db.scalar(select(Reason.id).where(Reason.type == body.type, Reason.code == body.code))
    if exists:
        raise ConflictError("CONFLICT", "Ya existe un motivo con ese código.")
    reason = Reason(**body.model_dump(), is_active=True, updated_by=ctx.user.id)
    ctx.db.add(reason)
    ctx.db.flush()
    ctx.audit(
        action="REASON_CREATE", resource_type="reason", resource_id=reason.id, after=snapshot(reason, _REASON_FIELDS)
    )
    ctx.db.commit()
    return reason


@router.patch("/reasons/{reason_id}", response_model=ReasonAdminOut)
def update_reason(reason_id: int, body: ReasonUpdateIn, ctx: CatalogCtx) -> Reason:
    reason = ctx.db.get(Reason, reason_id)
    if reason is None:
        raise NotFoundError()
    before = snapshot(reason, _REASON_FIELDS)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(reason, field, value)
    reason.updated_by = ctx.user.id
    b, a = diff(before, snapshot(reason, _REASON_FIELDS))
    ctx.audit(action="REASON_UPDATE", resource_type="reason", resource_id=reason.id, before=b, after=a)
    ctx.db.commit()
    return reason


# ------------------------------------------------------------------ plantillas


class TemplateOut(ApiOut):
    id: int
    code: str
    channel: str
    description: str
    subject: str
    body_text: str
    body_html: str | None
    is_active: bool
    updated_at: datetime


class TemplateUpdateIn(ApiModel):
    subject: Annotated[str, StringConstraints(min_length=3, max_length=200)] | None = None
    body_text: Annotated[str, StringConstraints(min_length=10, max_length=10_000, strip_whitespace=False)] | None = None
    body_html: Annotated[str, StringConstraints(max_length=50_000, strip_whitespace=False)] | None = None
    is_active: bool | None = None


class TemplatePreviewOut(ApiOut):
    subject: str
    body_text: str


TemplateCtx = Annotated[ServiceContext, Depends(require("template:manage"))]
_TEMPLATE_FIELDS = ("subject", "body_text", "body_html", "is_active")


@router.get("/notification-templates", response_model=list[TemplateOut])
def list_templates(ctx: TemplateCtx) -> list[NotificationTemplate]:
    return list(ctx.db.scalars(select(NotificationTemplate).order_by(NotificationTemplate.code)))


@router.patch("/notification-templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: int, body: TemplateUpdateIn, ctx: TemplateCtx) -> NotificationTemplate:
    template = ctx.db.get(NotificationTemplate, template_id)
    if template is None:
        raise NotFoundError()
    values = body.model_dump(exclude_unset=True)
    validate_template(values.get("subject"), values.get("body_text"), values.get("body_html"))
    before = snapshot(template, _TEMPLATE_FIELDS)
    for field, value in values.items():
        setattr(template, field, value)
    template.updated_by = ctx.user.id
    b, a = diff(before, snapshot(template, _TEMPLATE_FIELDS))
    ctx.audit(
        action="TEMPLATE_UPDATE", resource_type="notification_template", resource_id=template.code, before=b, after=a
    )
    ctx.db.commit()
    ctx.db.refresh(template)
    return template


@router.get("/notification-templates/{template_id}/preview", response_model=TemplatePreviewOut)
def preview_template(template_id: int, ctx: TemplateCtx) -> TemplatePreviewOut:
    template = ctx.db.get(NotificationTemplate, template_id)
    if template is None:
        raise NotFoundError()
    return TemplatePreviewOut(
        subject=render(template.subject, SAMPLE_CONTEXT), body_text=render(template.body_text, SAMPLE_CONTEXT)
    )
