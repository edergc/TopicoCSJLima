"""Reglas de la atención garantizadas por la base de datos: turnos, capacidad, estados."""

import psycopg
import pytest
from psycopg import errors

from .helpers import (
    create_worker,
    day_counters,
    expect_violation,
    far_future_date,
    open_day,
    register,
    scalar,
    site_id,
    transition,
    unique_date,
)

# ---------------------------------------------------------------------------
# Numeración de turnos
# ---------------------------------------------------------------------------


def test_ticket_numbers_are_sequential_per_site_and_day(app_db: psycopg.Connection, user_id: int) -> None:
    date = unique_date()
    alz = open_day(app_db, site_id(app_db, "ALZ"), date)
    bar = open_day(app_db, site_id(app_db, "BAR"), date)

    tickets_alz = [register(app_db, alz, create_worker(app_db), user_id)[2] for _ in range(3)]
    tickets_bar = [register(app_db, bar, create_worker(app_db), user_id)[2] for _ in range(2)]

    assert tickets_alz == ["A-001", "A-002", "A-003"]
    assert tickets_bar == ["B-001", "B-002"]


def test_ticket_number_assigned_by_db_ignores_client_value(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db))
    worker = create_worker(app_db)
    row = app_db.execute(
        """INSERT INTO appointment (service_day_id, worker_id, status, channel, registered_by,
                                    ticket_number, ticket_code, site_id, service_date)
           VALUES (%s, %s, 'EN_ESPERA', 'PHONE', %s, 999, 'Z-999', %s, DATE '1999-01-01')
           RETURNING ticket_number, ticket_code, site_id, service_date""",
        (day, worker, user_id, site_id(app_db, "BAR")),
    ).fetchone()
    assert row is not None
    service_date = scalar(app_db, "SELECT service_date FROM service_day WHERE id = %s", (day,))
    assert row == (1, "A-001", site_id(app_db, "ALZ"), service_date)


def test_queue_entry_sets_queued_at(app_db: psycopg.Connection, user_id: int) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    assert scalar(app_db, "SELECT queued_at IS NOT NULL FROM appointment WHERE id = %s", (appt,))


# ---------------------------------------------------------------------------
# Capacidad (casos críticos 1, 2 y 3)
# ---------------------------------------------------------------------------


def test_caso_1_rejects_registration_beyond_capacity(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db), capacity=3)
    for _ in range(3):
        register(app_db, day, create_worker(app_db), user_id)

    with expect_violation(errors.CheckViolation, "ck_service_day_capacity"):
        register(app_db, day, create_worker(app_db), user_id)

    assert day_counters(app_db, day) == (3, 3, 3)  # el intento fallido no consume número


def test_caso_2_cancellation_releases_capacity_without_reusing_ticket(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db), capacity=2)
    first, _, _ = register(app_db, day, create_worker(app_db), user_id)
    register(app_db, day, create_worker(app_db), user_id)

    transition(app_db, first, "CANCELADO", user_id)
    assert day_counters(app_db, day)[0] == 1

    _, number, code = register(app_db, day, create_worker(app_db), user_id)
    assert (number, code) == (3, "A-003")
    assert day_counters(app_db, day) == (2, 2, 3)


def test_caso_3_no_show_releases_capacity(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db), capacity=1)
    appt, _, _ = register(app_db, day, create_worker(app_db), user_id)
    transition(app_db, appt, "LLAMADO", user_id)
    transition(app_db, appt, "NO_PRESENTADO", user_id)

    assert scalar(app_db, "SELECT status FROM appointment WHERE id = %s", (appt,)) == "NO_PRESENTADO"
    assert day_counters(app_db, day)[0] == 0
    register(app_db, day, create_worker(app_db), user_id)  # el cupo quedó disponible


def test_void_releases_capacity(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db), capacity=1)
    appt, _, _ = register(app_db, day, create_worker(app_db), user_id)
    transition(app_db, appt, "ANULADO", user_id)
    assert day_counters(app_db, day)[0] == 0


def test_attended_keeps_consuming_capacity(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db), capacity=1)
    appt, _, _ = register(app_db, day, create_worker(app_db), user_id)
    for status in ("LLAMADO", "EN_ATENCION", "ATENDIDO"):
        transition(app_db, appt, status, user_id)
    assert day_counters(app_db, day)[0] == 1
    with expect_violation(errors.CheckViolation, "ck_service_day_capacity"):
        register(app_db, day, create_worker(app_db), user_id)


def test_requeue_keeps_ticket_and_capacity(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db))
    appt, number, _ = register(app_db, day, create_worker(app_db), user_id)
    transition(app_db, appt, "LLAMADO", user_id)
    transition(app_db, appt, "EN_ESPERA", user_id)
    transition(app_db, appt, "LLAMADO", user_id)
    row = app_db.execute("SELECT ticket_number, call_count FROM appointment WHERE id = %s", (appt,)).fetchone()
    assert row == (number, 2)
    assert day_counters(app_db, day)[0] == 1


def test_capacity_cannot_be_reduced_below_occupied(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db), capacity=3)
    register(app_db, day, create_worker(app_db), user_id)
    register(app_db, day, create_worker(app_db), user_id)
    with expect_violation(errors.CheckViolation, "ck_service_day_capacity"):
        app_db.execute("UPDATE service_day SET capacity = 1 WHERE id = %s", (day,))


def test_app_cannot_tamper_with_day_counters(app_db: psycopg.Connection) -> None:
    day = open_day(app_db, site_id(app_db))
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("UPDATE service_day SET occupied_count = 0 WHERE id = %s", (day,))
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("UPDATE service_day SET last_ticket_number = 0 WHERE id = %s", (day,))


def test_closed_day_rejects_registrations(app_db: psycopg.Connection, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db))
    app_db.execute(
        "UPDATE service_day SET status = 'CLOSED', closed_at = now(), closed_by = %s WHERE id = %s", (user_id, day)
    )
    with expect_violation(errors.CheckViolation, "ck_service_day_open"):
        register(app_db, day, create_worker(app_db), user_id)


# ---------------------------------------------------------------------------
# Día operativo
# ---------------------------------------------------------------------------


def test_service_day_freezes_current_configuration(app_db: psycopg.Connection) -> None:
    alz = site_id(app_db)
    day = open_day(app_db, alz)
    row = app_db.execute(
        "SELECT capacity, slot_minutes, tolerance_minutes, max_concurrent_in_service FROM service_day WHERE id = %s",
        (day,),
    ).fetchone()
    assert row == (20, 15, 10, 1)


def test_ensure_service_day_is_idempotent(app_db: psycopg.Connection) -> None:
    date = unique_date()
    assert open_day(app_db, site_id(app_db), date) == open_day(app_db, site_id(app_db), date)


def test_future_setting_version_applies_only_from_its_date(app_db: psycopg.Connection) -> None:
    bar = site_id(app_db, "BAR")
    before, switch = far_future_date(), far_future_date()
    app_db.execute(
        """INSERT INTO site_setting_version (site_id, valid_from, daily_capacity, slot_minutes, tolerance_minutes)
           VALUES (%s, %s, 35, 20, 5)""",
        (bar, switch),
    )
    cap_before = scalar(app_db, "SELECT capacity FROM service_day WHERE id = %s", (open_day(app_db, bar, before),))
    cap_after = scalar(app_db, "SELECT capacity FROM service_day WHERE id = %s", (open_day(app_db, bar, switch),))
    assert (cap_before, cap_after) == (20, 35)


def test_service_day_requires_configuration(app_db: psycopg.Connection) -> None:
    import datetime as dt

    with expect_violation(errors.CheckViolation, "ck_service_day_setting_required"):
        open_day(app_db, site_id(app_db), dt.date(2020, 1, 1))


# ---------------------------------------------------------------------------
# Unicidad: una atención activa por trabajador y día (RN-17)
# ---------------------------------------------------------------------------


def test_worker_cannot_have_two_active_appointments_same_day(app_db: psycopg.Connection, user_id: int) -> None:
    date = unique_date()
    alz = open_day(app_db, site_id(app_db, "ALZ"), date)
    bar = open_day(app_db, site_id(app_db, "BAR"), date)
    worker = create_worker(app_db)
    appt, _, _ = register(app_db, alz, worker, user_id)

    with expect_violation(errors.UniqueViolation, "uq_appointment_worker_active_day"):
        register(app_db, alz, worker, user_id)
    with expect_violation(errors.UniqueViolation, "uq_appointment_worker_active_day"):
        register(app_db, bar, worker, user_id)  # tampoco en la otra sede

    transition(app_db, appt, "CANCELADO", user_id)
    register(app_db, bar, worker, user_id)  # tras cancelar sí puede volver a registrarse


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "forbidden"),
    [
        ([], "ATENDIDO"),
        ([], "EN_ATENCION"),
        ([], "NO_PRESENTADO"),
        (["LLAMADO"], "ANULADO"),
        (["LLAMADO", "EN_ATENCION"], "CANCELADO"),
        (["LLAMADO", "EN_ATENCION"], "EN_ESPERA"),
    ],
)
def test_forbidden_transitions_are_rejected(
    app_db: psycopg.Connection, user_id: int, path: list[str], forbidden: str
) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    for status in path:
        transition(app_db, appt, status, user_id)
    with expect_violation(errors.CheckViolation, "ck_appointment_status_transition"):
        transition(app_db, appt, forbidden, user_id)


def test_initial_status_must_be_registered_or_waiting(app_db: psycopg.Connection, user_id: int) -> None:
    with expect_violation(errors.CheckViolation, "ck_appointment_initial_status"):
        register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id, status="ATENDIDO")


def test_final_states_are_immutable(app_db: psycopg.Connection, user_id: int) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    transition(app_db, appt, "CANCELADO", user_id)
    with expect_violation(errors.CheckViolation, "ck_appointment_final_immutable"):
        app_db.execute("UPDATE appointment SET admin_note = 'cambio' WHERE id = %s", (appt,))


def test_status_requires_its_timestamps(app_db: psycopg.Connection, user_id: int) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    with expect_violation(errors.CheckViolation, "ck_appointment_called_data"):
        app_db.execute("UPDATE appointment SET status = 'LLAMADO' WHERE id = %s", (appt,))


def test_cancellation_requires_reason(app_db: psycopg.Connection, user_id: int) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    with expect_violation(errors.CheckViolation, "ck_appointment_closed_data"):
        app_db.execute(
            "UPDATE appointment SET status = 'CANCELADO', closed_at = now(), closed_by = %s WHERE id = %s",
            (user_id, appt),
        )


# ---------------------------------------------------------------------------
# Inmutabilidad y no eliminación
# ---------------------------------------------------------------------------


def test_app_cannot_change_identity_columns(app_db: psycopg.Connection, user_id: int) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("UPDATE appointment SET worker_id = worker_id WHERE id = %s", (appt,))


def test_immutable_columns_protected_even_for_owner(
    app_db: psycopg.Connection, owner_db: psycopg.Connection, user_id: int
) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    with expect_violation(errors.CheckViolation, "ck_appointment_immutable_fields"):
        owner_db.execute("UPDATE appointment SET ticket_number = 500 WHERE id = %s", (appt,))


def test_appointments_cannot_be_deleted(app_db: psycopg.Connection, owner_db: psycopg.Connection, user_id: int) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("DELETE FROM appointment WHERE id = %s", (appt,))
    with pytest.raises(errors.InsufficientPrivilege, match="solo inserción"):
        owner_db.execute("DELETE FROM appointment WHERE id = %s", (appt,))


def test_appointment_events_are_append_only(
    app_db: psycopg.Connection, owner_db: psycopg.Connection, user_id: int
) -> None:
    appt, _, _ = register(app_db, open_day(app_db, site_id(app_db)), create_worker(app_db), user_id)
    event = scalar(
        app_db,
        """INSERT INTO appointment_event (appointment_id, action, to_status, user_id)
           VALUES (%s, 'REGISTER', 'EN_ESPERA', %s) RETURNING id""",
        (appt, user_id),
    )
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("UPDATE appointment_event SET note = 'x' WHERE id = %s", (event,))
    with pytest.raises(errors.InsufficientPrivilege, match="solo inserción"):
        owner_db.execute("UPDATE appointment_event SET note = 'x' WHERE id = %s", (event,))
