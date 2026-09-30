"""Middlewares: contexto de solicitud (request_id/IP), access log estructurado y cabeceras de seguridad."""

import ipaddress
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.context import RequestContext, reset_request_context, set_request_context
from app.core.logging import get_logger

access_log = get_logger("app.access")

_REQUEST_ID_HEADER = "X-Request-ID"


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def client_ip(request: Request, trusted_proxy_count: int) -> str | None:
    """IP real del cliente. Solo confía en X-Forwarded-For si hay proxies de confianza configurados."""
    if trusted_proxy_count > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if len(hops) >= trusted_proxy_count:
                return _valid_ip(hops[-trusted_proxy_count])
    return _valid_ip(request.client.host if request.client else None)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, trusted_proxy_count: int = 0) -> None:
        super().__init__(app)
        self.trusted_proxy_count = trusted_proxy_count

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get(_REQUEST_ID_HEADER, "")
        request_id = incoming if 8 <= len(incoming) <= 40 and incoming.isascii() else uuid.uuid4().hex
        ctx = RequestContext(
            request_id=request_id,
            ip=client_ip(request, self.trusted_proxy_count),
            user_agent=(request.headers.get("user-agent") or "")[:500] or None,
        )
        token = set_request_context(ctx)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[_REQUEST_ID_HEADER] = request_id
            return response
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            if request.url.path != "/api/v1/health":
                access_log.info(
                    "http_request",
                    method=request.method,
                    path=request.url.path,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    ip=ctx.ip,
                )
            reset_request_context(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")
            headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response
