"""Lectura tipada de parámetros globales (tabla system_parameter)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.sites.models import SystemParameter


def get_param(db: Session, key: str, default: Any) -> Any:
    value = db.scalar(select(SystemParameter.value).where(SystemParameter.key == key))
    return default if value is None else value


def get_int(db: Session, key: str, default: int) -> int:
    value = get_param(db, key, default)
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else default


def get_bool(db: Session, key: str, default: bool) -> bool:
    value = get_param(db, key, default)
    return value if isinstance(value, bool) else default


def get_str(db: Session, key: str, default: str) -> str:
    value = get_param(db, key, default)
    return value if isinstance(value, str) else default
