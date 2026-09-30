"""Renderizado seguro de plantillas (Jinja2 en sandbox: sin acceso a atributos internos ni código)."""

from typing import Any

from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

from app.core.errors import BusinessRuleError

_env = SandboxedEnvironment(autoescape=False, trim_blocks=False, keep_trailing_newline=True)

SAMPLE_CONTEXT: dict[str, Any] = {
    "worker_first_name": "Juan",
    "ticket_code": "A-007",
    "site_name": "Sede Javier Alzamora Valdez",
    "location_note": "Primer piso, junto a la mesa de partes",
    "service_date": "29/09/2026",
    "registered_time": "09:12",
    "people_ahead": 2,
    "estimated_time": "09:45",
    "reason_label": "Ya no requiere la atención",
    "institution_name": "Corte Superior de Justicia de Lima",
    "public_status_url": "https://topico.csjlima.local/consulta",
}


def render(source: str, context: dict[str, Any]) -> str:
    return _env.from_string(source).render(**context)


def validate_template(*sources: str | None) -> None:
    """Valida sintaxis y renderiza con datos de ejemplo antes de guardar una plantilla."""
    for source in sources:
        if source is None:
            continue
        try:
            render(source, SAMPLE_CONTEXT)
        except TemplateSyntaxError as exc:
            raise BusinessRuleError("TEMPLATE_INVALID", f"Error en la línea {exc.lineno}: {exc.message}") from exc
        except Exception as exc:
            raise BusinessRuleError("TEMPLATE_INVALID", str(exc)[:300]) from exc
