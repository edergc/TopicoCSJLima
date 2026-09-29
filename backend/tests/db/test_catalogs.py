"""Trabajadores, coberturas EPS, horarios y configuración."""

import datetime as dt

import psycopg
import pytest
from psycopg import errors
from psycopg.types.json import Jsonb

from .helpers import (
    create_worker,
    expect_violation,
    far_future_date,
    scalar,
    site_id,
    unique_date,
    unique_dni,
)

# ---------------------------------------------------------------------------
# Trabajadores
# ---------------------------------------------------------------------------


def test_dni_preserves_leading_zeros(app_db: psycopg.Connection) -> None:
    worker = create_worker(app_db, dni="00012345")
    assert scalar(app_db, "SELECT document_number FROM worker WHERE id = %s", (worker,)) == "00012345"


@pytest.mark.parametrize("dni", ["1234567", "123456789", "1234567A", "12 45678", ""])
def test_invalid_dni_is_rejected(app_db: psycopg.Connection, dni: str) -> None:
    with expect_violation(errors.CheckViolation, "ck_worker_document_format"):
        create_worker(app_db, dni=dni)


def test_duplicate_document_is_rejected(app_db: psycopg.Connection) -> None:
    dni = unique_dni()
    create_worker(app_db, dni=dni)
    with expect_violation(errors.UniqueViolation, "uq_worker_document"):
        create_worker(app_db, dni=dni)


def test_invalid_email_is_rejected(app_db: psycopg.Connection) -> None:
    worker = create_worker(app_db)
    with expect_violation(errors.CheckViolation, "ck_worker_email_format"):
        app_db.execute("UPDATE worker SET institutional_email = 'sin-arroba' WHERE id = %s", (worker,))


def test_search_by_name_uses_generated_column(app_db: psycopg.Connection) -> None:
    worker = create_worker(app_db)
    assert scalar(app_db, "SELECT search_name FROM worker WHERE id = %s", (worker,)) == "PEREZ QUISPE JUAN CARLOS"


def test_coverages_cannot_overlap(app_db: psycopg.Connection) -> None:
    worker = create_worker(app_db)  # cobertura vigente desde 2020-01-01 sin término
    with expect_violation(errors.ExclusionViolation, "ex_worker_coverage_overlap"):
        app_db.execute(
            """INSERT INTO worker_coverage (worker_id, insurer_id, valid_from)
               SELECT %s, id, DATE '2024-01-01' FROM insurer WHERE code = 'RIMAC'""",
            (worker,),
        )


def test_consecutive_coverages_are_allowed(app_db: psycopg.Connection) -> None:
    worker = create_worker(app_db, with_coverage=False)
    app_db.execute(
        """INSERT INTO worker_coverage (worker_id, insurer_id, valid_from, valid_to)
           SELECT %s, id, DATE '2024-01-01', DATE '2024-12-31' FROM insurer WHERE code = 'RIMAC'""",
        (worker,),
    )
    app_db.execute(
        """INSERT INTO worker_coverage (worker_id, insurer_id, valid_from)
           SELECT %s, id, DATE '2025-01-01' FROM insurer WHERE code = 'RIMAC'""",
        (worker,),
    )
    assert scalar(app_db, "SELECT count(*) FROM worker_coverage WHERE worker_id = %s", (worker,)) == 2


def test_deactivated_worker_requires_date(app_db: psycopg.Connection) -> None:
    worker = create_worker(app_db)
    with expect_violation(errors.CheckViolation, "ck_worker_deactivation"):
        app_db.execute("UPDATE worker SET is_active = false WHERE id = %s", (worker,))


# ---------------------------------------------------------------------------
# Horarios y configuración de sede
# ---------------------------------------------------------------------------


def test_schedule_blocks_cannot_overlap_in_time(app_db: psycopg.Connection) -> None:
    with expect_violation(errors.ExclusionViolation, "ex_site_schedule_time_overlap"):
        app_db.execute(
            """INSERT INTO site_schedule (site_id, weekday, block, start_time, end_time, valid_from)
               VALUES (%s, 6, 'AM', '08:00', '12:00', DATE '2026-01-01'),
                      (%s, 6, 'PM', '11:00', '15:00', DATE '2026-01-01')""",
            (site_id(app_db), site_id(app_db)),
        )


def test_same_block_cannot_be_defined_twice(app_db: psycopg.Connection) -> None:
    with expect_violation(errors.ExclusionViolation, "ex_site_schedule_block"):
        app_db.execute(
            """INSERT INTO site_schedule (site_id, weekday, block, start_time, end_time, valid_from)
               VALUES (%s, 1, 'AM', '07:00', '07:30', DATE '2026-06-01')""",
            (site_id(app_db),),
        )


def test_effective_setting_version_is_immutable(app_db: psycopg.Connection) -> None:
    with expect_violation(errors.CheckViolation, "ck_site_setting_version_effective_immutable"):
        app_db.execute("UPDATE site_setting_version SET daily_capacity = 99 WHERE valid_from = DATE '2026-01-01'")


def test_future_setting_version_is_editable(app_db: psycopg.Connection) -> None:
    version = scalar(
        app_db,
        """INSERT INTO site_setting_version (site_id, valid_from, daily_capacity, slot_minutes, tolerance_minutes)
           VALUES (%s, %s, 25, 15, 10) RETURNING id""",
        (site_id(app_db), far_future_date()),
    )
    app_db.execute("UPDATE site_setting_version SET daily_capacity = 30 WHERE id = %s", (version,))
    assert scalar(app_db, "SELECT daily_capacity FROM site_setting_version WHERE id = %s", (version,)) == 30


@pytest.mark.parametrize(("column", "value"), [("daily_capacity", 0), ("slot_minutes", 3), ("tolerance_minutes", -1)])
def test_setting_values_are_bounded(app_db: psycopg.Connection, column: str, value: int) -> None:
    params = {"daily_capacity": 20, "slot_minutes": 15, "tolerance_minutes": 10, column: value}
    with pytest.raises(errors.CheckViolation):
        app_db.execute(
            """INSERT INTO site_setting_version (site_id, valid_from, daily_capacity, slot_minutes, tolerance_minutes)
               VALUES (%(site)s, %(date)s, %(daily_capacity)s, %(slot_minutes)s, %(tolerance_minutes)s)""",
            {**params, "site": site_id(app_db), "date": unique_date()},
        )


def test_system_parameter_value_must_match_type(app_db: psycopg.Connection) -> None:
    with expect_violation(errors.CheckViolation, "ck_system_parameter_value_type"):
        app_db.execute(
            "INSERT INTO system_parameter (key, value, value_type, description) VALUES (%s, %s, 'int', 'x')",
            ("test.bad_param", Jsonb("no-es-numero")),
        )


def test_site_closure_unique_per_day(app_db: psycopg.Connection) -> None:
    date = unique_date()
    app_db.execute(
        "INSERT INTO site_closure (site_id, closure_date, reason) VALUES (%s, %s, 'Feriado')", (site_id(app_db), date)
    )
    with expect_violation(errors.UniqueViolation, "uq_site_closure_site_date"):
        app_db.execute(
            "INSERT INTO site_closure (site_id, closure_date, reason) VALUES (%s, %s, 'Otro')", (site_id(app_db), date)
        )


def test_birth_date_sanity(app_db: psycopg.Connection) -> None:
    worker = create_worker(app_db)
    with expect_violation(errors.CheckViolation, "ck_worker_birth_date"):
        app_db.execute("UPDATE worker SET birth_date = %s WHERE id = %s", (dt.date(1850, 1, 1), worker))
