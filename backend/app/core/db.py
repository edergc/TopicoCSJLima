"""Acceso a PostgreSQL: engine, fábrica de sesiones y base declarativa del ORM.

- El esquema de BD lo definen las migraciones SQL (alembic/sql); los modelos ORM lo reflejan.
- Cada request usa una sesión; los servicios delimitan la transacción del caso de uso (commit).
- Las consultas lentas se registran en el log técnico.
"""

import time
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import DateTime, Engine, FetchedValue, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import DB_SCHEMA, Settings
from app.core.logging import get_logger

log = get_logger("app.db")


class Base(DeclarativeBase):
    metadata = MetaData(schema=DB_SCHEMA)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


def build_engine(url: str, settings: Settings) -> Engine:
    engine = create_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "options": f"-c search_path={DB_SCHEMA},public -c timezone=UTC",
            "application_name": "topico-backend",
            "connect_timeout": 10,
        },
    )
    _install_slow_query_log(engine, settings.db_slow_query_ms)
    return engine


def _install_slow_query_log(engine: Engine, threshold_ms: int) -> None:
    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn: Any, _cursor: Any, _stmt: str, _params: Any, _ctx: Any, _many: bool) -> None:
        conn.info.setdefault("query_start", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn: Any, _cursor: Any, statement: str, _params: Any, _ctx: Any, _many: bool) -> None:
        elapsed_ms = (time.perf_counter() - conn.info["query_start"].pop()) * 1000
        if elapsed_ms >= threshold_ms:
            log.warning("slow_query", elapsed_ms=round(elapsed_ms, 1), statement=statement[:500])


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """Dependencia FastAPI: una sesión por request; rollback ante cualquier error."""
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
