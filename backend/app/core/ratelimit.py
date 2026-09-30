"""Rate limiting en memoria (un solo servidor; no requiere Redis).

Se aplica a endpoints sensibles: login, refresh, cambio de contraseña y consulta pública.
"""

from slowapi import Limiter
from starlette.requests import Request

from app.core.context import get_request_context


def _client_key(request: Request) -> str:
    # La IP real ya fue resuelta por RequestContextMiddleware (respetando proxies de confianza).
    return get_request_context().ip or (request.client.host if request.client else "anon")


limiter = Limiter(key_func=_client_key, headers_enabled=False)
