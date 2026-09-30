"""Logging técnico estructurado (JSON) — separado de la auditoría funcional.

- Consola: legible en desarrollo, JSON si LOG_JSON_CONSOLE=true.
- Archivo: JSON, rotación diaria, retención configurable (logs/app.log).
Cada línea incluye request_id cuando existe, para correlacionar con la auditoría.
"""

import logging
import logging.handlers
import sys
from typing import Any

import structlog

from app.core.config import Settings
from app.core.context import get_request_context


def _add_request_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    ctx = get_request_context()
    if ctx.request_id and "request_id" not in event_dict:
        event_dict["request_id"] = ctx.request_id
    return event_dict


def configure_logging(settings: Settings) -> None:
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_context,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    json_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )
    console_formatter = (
        json_formatter
        if settings.log_json_console
        else structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=False),
            ],
        )
    )

    handlers: list[logging.Handler] = []
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(console_formatter)
    handlers.append(console)

    if settings.log_dir is not None:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            settings.log_dir / "app.log",
            when="midnight",
            backupCount=settings.log_retention_days,
            encoding="utf-8",
            utc=True,
        )
        file_handler.setFormatter(json_formatter)
        handlers.append(file_handler)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Uvicorn: se usa nuestro access log estructurado (middleware), no el suyo.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)
