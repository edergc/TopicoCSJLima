"""Fábrica de la aplicación FastAPI.

Ejecución:
    uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

import app.modules.registry  # noqa: F401  (registra todos los modelos ORM)
from app.core.clock import Clock, OffsetClock
from app.core.config import API_PREFIX, Settings, get_settings
from app.core.db import build_engine, build_session_factory
from app.core.errors import error_response, register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.ratelimit import limiter

log = get_logger("app")

VERSION = "0.1.0"


def _routers() -> list[APIRouter]:
    from app.modules.admin.router import router as admin_router
    from app.modules.appointments.router import catalog_router as appointment_catalogs
    from app.modules.appointments.router import router as appointments_router
    from app.modules.audit.router import router as audit_router
    from app.modules.auth.router import router as auth_router
    from app.modules.imports.router import router as imports_router
    from app.modules.notifications.router import router as notifications_router
    from app.modules.public.router import router as public_router
    from app.modules.reports.router import router as reports_router
    from app.modules.sites.router import router as sites_router
    from app.modules.users.router import router as users_router
    from app.modules.workers.router import catalog_router as worker_catalogs
    from app.modules.workers.router import router as workers_router

    return [
        auth_router,
        sites_router,
        workers_router,
        appointments_router,
        appointment_catalogs,
        worker_catalogs,
        notifications_router,
        imports_router,
        reports_router,
        audit_router,
        users_router,
        admin_router,
        public_router,
    ]


def create_app(settings: Settings | None = None, *, clock: Clock | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    engine = build_engine(settings.database_url, settings)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from app.modules.notifications.worker import BackgroundDispatcher

        dispatcher = None
        if settings.notifications_worker_enabled:
            dispatcher = BackgroundDispatcher(session_factory, settings, app.state.clock)
            dispatcher.start()
        log.info("app_started", environment=settings.environment, version=VERSION)
        yield
        if dispatcher is not None:
            dispatcher.stop()
        engine.dispose()
        log.info("app_stopped")

    docs = settings.api_docs_enabled
    app = FastAPI(
        title="Tópico de Salud — CSJ Lima",
        description="API del Sistema Integral de Gestión de Atención del Tópico de Salud.",
        version=VERSION,
        docs_url=f"{API_PREFIX}/docs" if docs else None,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    if clock is None and settings.dev_clock_start is not None and not settings.is_production:
        clock = OffsetClock(settings.dev_clock_start)
        log.warning("dev_clock_enabled", start=settings.dev_clock_start.isoformat())
    app.state.clock = clock or Clock()
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.limiter = limiter

    # El último middleware agregado es el más externo.
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-ID"],
            expose_headers=["X-Request-ID", "Content-Disposition"],
        )
    app.add_middleware(RequestContextMiddleware, trusted_proxy_count=settings.trusted_proxy_count)

    register_exception_handlers(app)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, __: RateLimitExceeded) -> JSONResponse:
        return error_response(429, "RATE_LIMITED")

    health = APIRouter(tags=["Salud"])

    @health.get("/health", summary="Liveness + hora del sistema (sincroniza los relojes de los clientes)")
    def liveness(request: Request) -> dict[str, str]:
        return {"status": "ok", "version": VERSION, "server_time": request.app.state.clock.now().isoformat()}

    @health.get("/health/ready", summary="Readiness (verifica PostgreSQL)")
    def readiness() -> JSONResponse:
        try:
            with engine.connect() as conn:
                revision = conn.execute(text("SELECT version_num FROM topico.alembic_version")).scalar()
            return JSONResponse({"status": "ok", "database": "ok", "schema_revision": revision})
        except Exception:
            log.exception("readiness_failed")
            return error_response(503, "SERVICE_UNAVAILABLE")

    app.include_router(health, prefix=API_PREFIX)
    for router in _routers():
        app.include_router(router, prefix=API_PREFIX)
    if settings.frontend_dist is not None:
        from app.core.frontend import mount_frontend

        mount_frontend(app, settings.frontend_dist)  # debe ir al final: incluye la ruta comodín del SPA
    return app
