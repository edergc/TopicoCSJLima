"""Errores de la aplicación y formato uniforme de respuesta de error.

Formato:
    {"success": false, "code": "CAPACITY_REACHED", "message": "...", "details": ..., "request_id": "..."}

- `code` es estable: el frontend lo usa para decidir qué mostrar.
- `message` está en español y es comprensible para el usuario final.
- Nunca se devuelven trazas ni mensajes internos de la BD.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import get_request_context
from app.core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    status_code: int = 400
    code: str = "BAD_REQUEST"
    message: str = "La solicitud no es válida."

    def __init__(self, code: str | None = None, message: str | None = None, *, details: Any = None) -> None:
        self.code = code or self.code
        self.message = message or MESSAGES.get(self.code, self.message)
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class BusinessRuleError(AppError):
    """Regla de negocio incumplida (la solicitud es válida pero no puede ejecutarse)."""

    status_code = 422
    code = "BUSINESS_RULE"


MESSAGES: dict[str, str] = {
    # Genéricos
    "BAD_REQUEST": "La solicitud no es válida.",
    "VALIDATION_ERROR": "Algunos datos ingresados no son válidos. Revise los campos marcados.",
    "NOT_FOUND": "El recurso solicitado no existe.",
    "CONFLICT": "La operación entra en conflicto con el estado actual de los datos.",
    "INTERNAL_ERROR": "Ocurrió un error inesperado. Si persiste, comuníquese con soporte indicando el código de solicitud.",
    "SERVICE_UNAVAILABLE": "El servicio no está disponible temporalmente. Intente nuevamente en unos momentos.",
    "RATE_LIMITED": "Demasiadas solicitudes. Espere un momento e intente nuevamente.",
    "DATA_INTEGRITY_ERROR": "La operación no pudo completarse porque violaría la integridad de los datos.",
    "PAYLOAD_TOO_LARGE": "El archivo excede el tamaño máximo permitido.",
    # Autenticación / autorización
    "UNAUTHORIZED": "Debe iniciar sesión para continuar.",
    "INVALID_CREDENTIALS": "Usuario o contraseña incorrectos.",
    "ACCOUNT_LOCKED": "La cuenta está bloqueada temporalmente por intentos fallidos. Intente más tarde.",
    "ACCOUNT_DISABLED": "La cuenta está desactivada. Comuníquese con el administrador.",
    "TOKEN_EXPIRED": "Su sesión ha expirado. Inicie sesión nuevamente.",
    "TOKEN_INVALID": "La sesión no es válida. Inicie sesión nuevamente.",
    "SESSION_EXPIRED": "Su sesión ha finalizado. Inicie sesión nuevamente.",
    "CSRF_CHECK_FAILED": "Solicitud rechazada por seguridad.",
    "FORBIDDEN": "No tiene permiso para realizar esta acción.",
    "SITE_FORBIDDEN": "No tiene autorización para operar en esta sede.",
    "PASSWORD_CHANGE_REQUIRED": "Debe cambiar su contraseña antes de continuar.",
    "PASSWORD_POLICY": "La contraseña no cumple la política de seguridad.",
    "PASSWORD_INCORRECT": "La contraseña actual es incorrecta.",
    "USERNAME_TAKEN": "Ya existe un usuario con ese nombre de usuario.",
    # Trabajadores
    "WORKER_NOT_FOUND": "No existe un trabajador registrado con el documento indicado.",
    "WORKER_INACTIVE": "El trabajador se encuentra inactivo en el padrón institucional.",
    "WORKER_NOT_ELIGIBLE": "El trabajador no cuenta con cobertura EPS Rímac vigente.",
    "WORKER_DUPLICATE_DOCUMENT": "Ya existe un trabajador con ese documento.",
    "INVALID_DOCUMENT": "El número de documento no es válido. El DNI debe tener 8 dígitos.",
    "COVERAGE_OVERLAP": "La vigencia indicada se superpone con otra cobertura del trabajador.",
    # Sedes / agenda
    "SITE_NOT_FOUND": "La sede no existe.",
    "SITE_INACTIVE": "La sede se encuentra inactiva.",
    "SITE_CLOSED_ON_DATE": "El tópico de esta sede no atiende en la fecha seleccionada.",
    "SITE_NO_SCHEDULE": "La sede no tiene horario de atención para la fecha seleccionada.",
    "REGISTRATION_WINDOW_CLOSED": "El horario de registro de atenciones para hoy ha concluido en esta sede.",
    "DATE_NOT_ALLOWED": "No se pueden registrar atenciones para la fecha seleccionada.",
    "CAPACITY_REACHED": "Se ha alcanzado la capacidad máxima de atención para esta sede en la fecha seleccionada.",
    "SERVICE_DAY_CLOSED": "La atención del día ya fue cerrada para esta sede.",
    "CAPACITY_BELOW_OCCUPIED": "La capacidad no puede ser menor que los cupos ya ocupados.",
    "SETTING_VERSION_IMMUTABLE": "Una configuración ya vigente no puede modificarse; registre una nueva versión.",
    "SCHEDULE_OVERLAP": "Los bloques de horario se superponen.",
    "CLOSURE_EXISTS": "Ya existe un cierre registrado para esa sede y fecha.",
    # Atenciones
    "APPOINTMENT_NOT_FOUND": "La atención no existe.",
    "APPOINTMENT_CHANGED": "La atención fue modificada por otro usuario. Se actualizó la información; revise e intente nuevamente.",
    "WORKER_ALREADY_HAS_APPOINTMENT": "El trabajador ya tiene una atención activa para esa fecha.",
    "REREGISTER_NOT_ALLOWED": "Según la configuración de la sede, el trabajador no puede volver a registrarse hoy.",
    "INVALID_TRANSITION": "La acción no está permitida en el estado actual de la atención.",
    "QUEUE_EMPTY": "No hay trabajadores en espera.",
    "MAX_IN_SERVICE_REACHED": "Ya hay una atención en curso. Finalícela antes de iniciar otra.",
    "TOLERANCE_NOT_ELAPSED": "Aún no vence el tiempo de tolerancia desde el llamado.",
    "REASON_REQUIRED": "Debe seleccionar un motivo.",
    "REASON_INVALID": "El motivo seleccionado no es válido para esta acción.",
    "NOTE_REQUIRED": "El motivo seleccionado requiere una observación.",
    "NOT_TODAY": "Solo se pueden operar atenciones del día en curso.",
    # Notificaciones / plantillas / parámetros
    "TEMPLATE_INVALID": "La plantilla tiene errores de sintaxis.",
    "PARAMETER_NOT_EDITABLE": "Este parámetro no puede modificarse.",
    "PARAMETER_TYPE_MISMATCH": "El valor no corresponde al tipo del parámetro.",
    # Importaciones
    "IMPORT_FILE_INVALID": "El archivo no es un Excel (.xlsx) válido.",
    "IMPORT_COLUMNS_MISSING": "El archivo no contiene las columnas obligatorias.",
    "IMPORT_ALREADY_CONFIRMED": "Este archivo ya fue importado anteriormente.",
    "IMPORT_INVALID_STATE": "El lote de importación no está en un estado que permita esta acción.",
    "IMPORT_EMPTY": "El archivo no contiene filas de datos.",
    # Consulta pública
    "PUBLIC_TICKET_NOT_FOUND": "No se encontró un turno con los datos ingresados. Verifique el DNI y el código de turno.",
    "PUBLIC_STATUS_DISABLED": "La consulta de turnos no está disponible en este momento.",
    "DISPLAY_DISABLED": "La pantalla de turnos no está habilitada.",
}

# Restricciones de la BD → error de negocio (última línea de defensa).
CONSTRAINT_ERRORS: dict[str, tuple[type[AppError], str]] = {
    "ck_service_day_capacity": (ConflictError, "CAPACITY_REACHED"),
    "ck_service_day_open": (ConflictError, "SERVICE_DAY_CLOSED"),
    "uq_appointment_worker_active_day": (ConflictError, "WORKER_ALREADY_HAS_APPOINTMENT"),
    "ck_appointment_status_transition": (ConflictError, "INVALID_TRANSITION"),
    "ck_appointment_final_immutable": (ConflictError, "INVALID_TRANSITION"),
    "uq_worker_document": (ConflictError, "WORKER_DUPLICATE_DOCUMENT"),
    "ck_worker_document_format": (BadRequestError, "INVALID_DOCUMENT"),
    "uq_app_user_username": (ConflictError, "USERNAME_TAKEN"),
    "ex_worker_coverage_overlap": (ConflictError, "COVERAGE_OVERLAP"),
    "ex_site_schedule_block": (ConflictError, "SCHEDULE_OVERLAP"),
    "ex_site_schedule_time_overlap": (ConflictError, "SCHEDULE_OVERLAP"),
    "ck_site_setting_version_effective_immutable": (ConflictError, "SETTING_VERSION_IMMUTABLE"),
    "uq_site_closure_site_date": (ConflictError, "CLOSURE_EXISTS"),
    "uq_import_batch_confirmed_file": (ConflictError, "IMPORT_ALREADY_CONFIRMED"),
}


def constraint_name(exc: Exception) -> str | None:
    diag = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diag, "constraint_name", None)


def translate_integrity_error(exc: Exception) -> AppError:
    name = constraint_name(exc)
    if name and name in CONSTRAINT_ERRORS:
        cls, code = CONSTRAINT_ERRORS[name]
        return cls(code)
    return ConflictError("DATA_INTEGRITY_ERROR")


def _body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "success": False,
        "code": code,
        "message": message,
        "details": details,
        "request_id": get_request_context().request_id,
    }


def error_response(status_code: int, code: str, message: str | None = None, details: Any = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_body(code, message or MESSAGES.get(code, code), details))


_FIELD_MESSAGES = {
    "missing": "Campo obligatorio.",
    "string_too_short": "Texto demasiado corto.",
    "string_too_long": "Texto demasiado largo.",
    "string_pattern_mismatch": "Formato inválido.",
    "value_error": "Valor inválido.",
    "int_parsing": "Debe ser un número entero.",
    "date_from_datetime_parsing": "Fecha inválida.",
    "date_parsing": "Fecha inválida (use AAAA-MM-DD).",
    "uuid_parsing": "Identificador inválido.",
    "enum": "Valor no permitido.",
    "literal_error": "Valor no permitido.",
    "greater_than_equal": "Valor demasiado pequeño.",
    "less_than_equal": "Valor demasiado grande.",
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
            ctx_error = (err.get("ctx") or {}).get("error")
            message = str(ctx_error) if ctx_error else _FIELD_MESSAGES.get(err.get("type", ""), "Valor inválido.")
            fields.append({"field": ".".join(loc), "message": message})
        return error_response(422, "VALIDATION_ERROR", details=fields)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "BAD_REQUEST", 413: "PAYLOAD_TOO_LARGE"}
        return error_response(exc.status_code, code.get(exc.status_code, "BAD_REQUEST"))

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        err = translate_integrity_error(exc)
        log.warning("integrity_error", constraint=constraint_name(exc), code=err.code)
        return error_response(err.status_code, err.code, err.message)

    @app.exception_handler(StaleDataError)
    async def _stale(_: Request, __: StaleDataError) -> JSONResponse:
        return error_response(409, "APPOINTMENT_CHANGED")

    @app.exception_handler(OperationalError)
    async def _operational(_: Request, exc: OperationalError) -> JSONResponse:
        log.error("database_operational_error", error=str(exc.orig) if exc.orig else str(exc))
        return error_response(503, "SERVICE_UNAVAILABLE")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception", error_type=type(exc).__name__)
        return error_response(500, "INTERNAL_ERROR")
