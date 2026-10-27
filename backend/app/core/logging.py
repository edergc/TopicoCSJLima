"""Logging técnico estructurado (JSON) — separado de la auditoría funcional.

- Consola: legible en desarrollo, JSON si LOG_JSON_CONSOLE=true.
- Archivo: JSON, un archivo por día (logs/app-AAAA-MM-DD.log), retención configurable.
Cada línea incluye request_id cuando existe, para correlacionar con la auditoría.
"""

import contextlib
import logging
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from app.core.clock import INSTITUTION_TZ
from app.core.config import Settings
from app.core.context import get_request_context

_DAILY_FILE_RE = re.compile(r"^app-(\d{4}-\d{2}-\d{2})\.log$")


class DailyFileHandler(logging.FileHandler):
    """Escribe en app-AAAA-MM-DD.log (fecha de Lima) y cambia de archivo al cambiar el día.

    No renombra archivos: TimedRotatingFileHandler falla en Windows con varios workers de uvicorn,
    porque un proceso no puede renombrar el archivo que otro mantiene abierto (WinError 32).
    """

    def __init__(self, directory: Path, retention_days: int) -> None:
        self.directory = directory
        self.retention_days = retention_days
        self.day = self._today()
        super().__init__(self._path(self.day), encoding="utf-8", delay=True)

    @staticmethod
    def _today() -> date:
        return datetime.now(INSTITUTION_TZ).date()

    def _path(self, day: date) -> Path:
        return self.directory / f"app-{day.isoformat()}.log"

    def emit(self, record: logging.LogRecord) -> None:
        today = self._today()
        if today != self.day:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            self.day = today
            self.baseFilename = str(self._path(today))
            self._purge()
        super().emit(record)

    def _purge(self) -> None:
        oldest = self.day - timedelta(days=self.retention_days)
        for file in self.directory.glob("app-*.log"):
            match = _DAILY_FILE_RE.match(file.name)
            if match and date.fromisoformat(match.group(1)) < oldest:
                # Si otro proceso aún lo tiene abierto, se borrará en el próximo cambio de día.
                with contextlib.suppress(OSError):
                    file.unlink(missing_ok=True)


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
        file_handler = DailyFileHandler(settings.log_dir, settings.log_retention_days)
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
