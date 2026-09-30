"""Contexto de la solicitud HTTP en curso (request_id, IP, user-agent).

Se propaga con contextvars para que la auditoría y los logs lo obtengan sin pasarlo
explícitamente por todas las capas.
"""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None


_request_context: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())  # noqa: B039


def get_request_context() -> RequestContext:
    return _request_context.get()


def set_request_context(ctx: RequestContext) -> object:
    return _request_context.set(ctx)


def reset_request_context(token: object) -> None:
    _request_context.reset(token)  # type: ignore[arg-type]
