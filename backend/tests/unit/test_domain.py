"""Pruebas unitarias del dominio (sin HTTP)."""

import datetime as dt

import psycopg
import pytest

from app.core.clock import INSTITUTION_TZ
from app.modules.appointments.scheduling import estimate_start_times
from app.modules.appointments.state_machine import TRANSITIONS, Action, allowed_actions
from app.shared.text import display_name, mask_name, normalize_document, short_name

T = INSTITUTION_TZ


def at(h: int, m: int = 0) -> dt.datetime:
    return dt.datetime(2040, 1, 2, h, m, tzinfo=T)


BLOCKS = [(at(8), at(12)), (at(14), at(17))]


def test_state_machine_matches_database(app_db: psycopg.Connection) -> None:
    """La máquina de estados de Python debe ser idéntica a la tabla de la BD."""
    db_rows = {
        (r[0], r[1], r[2])
        for r in app_db.execute("SELECT from_status, to_status, action FROM appointment_status_transition").fetchall()
    }
    code = {
        (src.value, target.value, action.value) for action, (sources, target) in TRANSITIONS.items() for src in sources
    }
    assert code == db_rows


def test_allowed_actions_respect_permissions() -> None:
    operator = frozenset({"appointment:operate", "appointment:cancel", "appointment:no_show", "appointment:void"})
    assert allowed_actions("EN_ESPERA", operator) == ["CALL", "CANCEL", "VOID"]
    assert allowed_actions("LLAMADO", operator) == ["START", "REQUEUE", "NO_SHOW", "CANCEL"]
    assert allowed_actions("ATENDIDO", operator) == []
    assert allowed_actions("EN_ESPERA", frozenset({"appointment:cancel"})) == ["CANCEL"]
    assert Action.ACTIVATE.value not in allowed_actions("REGISTRADO", operator)


def test_estimates_follow_slots() -> None:
    result = estimate_start_times(
        now=at(9), blocks=BLOCKS, slot_minutes=15, lanes=1, in_service_started=[], pending_count=3
    )
    assert result == [at(9), at(9, 15), at(9, 30)]


def test_estimates_account_for_person_in_service() -> None:
    result = estimate_start_times(
        now=at(9), blocks=BLOCKS, slot_minutes=15, lanes=1, in_service_started=[at(8, 55)], pending_count=2
    )
    assert result == [at(9, 10), at(9, 25)]


def test_estimates_skip_lunch_gap_and_end_of_day() -> None:
    result = estimate_start_times(
        now=at(11, 40), blocks=BLOCKS, slot_minutes=15, lanes=1, in_service_started=[], pending_count=4
    )
    assert result == [at(11, 40), at(11, 55), at(14), at(14, 15)]
    late = estimate_start_times(
        now=at(16, 50), blocks=BLOCKS, slot_minutes=15, lanes=1, in_service_started=[], pending_count=2
    )
    assert late == [at(16, 50), None]


def test_estimates_before_opening_and_multiple_lanes() -> None:
    result = estimate_start_times(
        now=at(7), blocks=BLOCKS, slot_minutes=20, lanes=2, in_service_started=[], pending_count=3
    )
    assert result == [at(8), at(8), at(8, 20)]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(1234567, "01234567"), (1234567.0, "01234567"), (" 45678901 ", "45678901"), ("4567-8901", "45678901"), (None, "")],
)
def test_normalize_document(raw: object, expected: str) -> None:
    assert normalize_document(raw) == expected


def test_name_formatting_and_masking() -> None:
    assert display_name("JUAN CARLOS", "PEREZ", "QUISPE") == "PEREZ QUISPE, Juan Carlos"
    assert short_name("JUAN CARLOS", "PEREZ", "QUISPE") == "Juan P. Q."
    assert mask_name("JUAN CARLOS", "PEREZ") == "J*** P***"


def test_priority_call_order_respects_fairness_cap() -> None:
    from app.modules.appointments.priority import call_order

    # (turno, prioritario) en orden de registro
    waiting = [(1, False), (2, False), (3, True), (4, True), (5, True), (6, False)]
    order = call_order(waiting, lambda w: w[1], streak=0, limit=2)
    assert [t for t, _ in order] == [3, 4, 1, 5, 2, 6]
    # Si ya hubo 2 prioritarios seguidos, el siguiente es en orden normal
    assert [t for t, _ in call_order(waiting, lambda w: w[1], streak=2, limit=2)][:2] == [1, 3]
    # Sin personas en orden normal, se sigue con los prioritarios
    assert [t for t, _ in call_order([(7, True), (8, True), (9, True)], lambda w: w[1], streak=5, limit=2)] == [7, 8, 9]
