"""Máquina de estados de la atención.

Espejo de la tabla appointment_status_transition (la BD rechaza cualquier otra transición;
una prueba verifica que ambas definiciones coinciden). Aquí se agrega lo que la BD no sabe:
qué permiso exige cada acción y qué tipo de motivo requiere.
"""

from enum import StrEnum


class Status(StrEnum):
    REGISTRADO = "REGISTRADO"
    EN_ESPERA = "EN_ESPERA"
    LLAMADO = "LLAMADO"
    EN_ATENCION = "EN_ATENCION"
    ATENDIDO = "ATENDIDO"
    CANCELADO = "CANCELADO"
    NO_PRESENTADO = "NO_PRESENTADO"
    ANULADO = "ANULADO"


class Action(StrEnum):
    ACTIVATE = "ACTIVATE"
    CALL = "CALL"
    REQUEUE = "REQUEUE"
    START = "START"
    FINISH = "FINISH"
    CANCEL = "CANCEL"
    NO_SHOW = "NO_SHOW"
    VOID = "VOID"


ACTIVE_STATUSES: frozenset[str] = frozenset({Status.REGISTRADO, Status.EN_ESPERA, Status.LLAMADO, Status.EN_ATENCION})
FINAL_STATUSES: frozenset[str] = frozenset({Status.ATENDIDO, Status.CANCELADO, Status.NO_PRESENTADO, Status.ANULADO})

# acción → (estados de origen permitidos, estado destino)
TRANSITIONS: dict[Action, tuple[frozenset[Status], Status]] = {
    Action.ACTIVATE: (frozenset({Status.REGISTRADO}), Status.EN_ESPERA),
    Action.CALL: (frozenset({Status.EN_ESPERA}), Status.LLAMADO),
    Action.REQUEUE: (frozenset({Status.LLAMADO}), Status.EN_ESPERA),
    Action.START: (frozenset({Status.LLAMADO}), Status.EN_ATENCION),
    Action.FINISH: (frozenset({Status.EN_ATENCION}), Status.ATENDIDO),
    Action.CANCEL: (frozenset({Status.REGISTRADO, Status.EN_ESPERA, Status.LLAMADO}), Status.CANCELADO),
    Action.NO_SHOW: (frozenset({Status.LLAMADO}), Status.NO_PRESENTADO),
    Action.VOID: (frozenset({Status.REGISTRADO, Status.EN_ESPERA}), Status.ANULADO),
}

ACTION_PERMISSION: dict[Action, str] = {
    Action.CALL: "appointment:operate",
    Action.REQUEUE: "appointment:operate",
    Action.START: "appointment:operate",
    Action.FINISH: "appointment:operate",
    Action.CANCEL: "appointment:cancel",
    Action.NO_SHOW: "appointment:no_show",
    Action.VOID: "appointment:void",
}

# Tipo de motivo (tabla reason.type) exigido por la acción.
ACTION_REASON_TYPE: dict[Action, str] = {
    Action.CANCEL: "CANCEL",
    Action.NO_SHOW: "NO_SHOW",
    Action.VOID: "VOID",
    Action.REQUEUE: "REQUEUE",
}

# Acciones operadas por el usuario (ACTIVATE la ejecuta el sistema).
USER_ACTIONS: tuple[Action, ...] = (
    Action.CALL,
    Action.START,
    Action.FINISH,
    Action.REQUEUE,
    Action.NO_SHOW,
    Action.CANCEL,
    Action.VOID,
)


def target_status(status: str, action: Action) -> Status | None:
    sources, target = TRANSITIONS[action]
    return target if status in sources else None


def allowed_actions(status: str, permissions: frozenset[str] | set[str]) -> list[str]:
    return [
        a.value for a in USER_ACTIONS if target_status(status, a) is not None and ACTION_PERMISSION[a] in permissions
    ]
