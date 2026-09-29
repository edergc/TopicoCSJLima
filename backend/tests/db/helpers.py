"""Utilidades de datos de prueba a nivel SQL.

Cada prueba usa fechas y documentos únicos, así no interfiere con otras aunque todas
compartan la misma base (las atenciones no pueden borrarse, por diseño).
"""

import datetime as dt
import itertools
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest

from app.core.config import DB_SCHEMA

_dates = itertools.count()
_documents = itertools.count(40_000_000)
_BASE_DATE = dt.date(2031, 1, 6)
_far_dates = itertools.count()
_FAR_FUTURE = dt.date(2090, 1, 1)

STATUS_REASON_TYPE = {"CANCELADO": "CANCEL", "NO_PRESENTADO": "NO_SHOW", "ANULADO": "VOID"}


def connect(url: str, *, autocommit: bool = True) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=autocommit, options=f"-c search_path={DB_SCHEMA},public")


def unique_date() -> dt.date:
    return _BASE_DATE + dt.timedelta(days=next(_dates))


def far_future_date() -> dt.date:
    """Fecha aislada para pruebas que crean versiones de configuración (no afecta a unique_date)."""
    return _FAR_FUTURE + dt.timedelta(days=next(_far_dates))


def unique_dni() -> str:
    return f"{next(_documents):08d}"


@contextmanager
def expect_violation(error: type[psycopg.Error], constraint: str | None = None) -> Iterator[None]:
    with pytest.raises(error) as exc_info:
        yield
    if constraint is not None:
        assert exc_info.value.diag.constraint_name == constraint, (
            f"Se esperaba la restricción {constraint!r}, se obtuvo {exc_info.value.diag.constraint_name!r}: "
            f"{exc_info.value}"
        )


def scalar(conn: psycopg.Connection, sql: str, params: Any = None) -> Any:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def site_id(conn: psycopg.Connection, code: str = "ALZ") -> int:
    return int(scalar(conn, "SELECT id FROM site WHERE code = %s", (code,)))


def reason_id(conn: psycopg.Connection, reason_type: str, code: str | None = None) -> int:
    if code is None:
        return int(scalar(conn, "SELECT id FROM reason WHERE type = %s ORDER BY sort_order LIMIT 1", (reason_type,)))
    return int(scalar(conn, "SELECT id FROM reason WHERE type = %s AND code = %s", (reason_type, code)))


def create_user(conn: psycopg.Connection) -> int:
    username = f"user.{uuid.uuid4().hex[:12]}"
    return int(
        scalar(
            conn,
            "INSERT INTO app_user (username, full_name, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (username, "Usuario de Prueba", "$argon2id$placeholder"),
        )
    )


def create_worker(conn: psycopg.Connection, *, dni: str | None = None, with_coverage: bool = True) -> int:
    worker_id = int(
        scalar(
            conn,
            """INSERT INTO worker (document_type, document_number, first_names, paternal_surname, maternal_surname,
                                   institutional_email)
               VALUES ('DNI', %s, 'JUAN CARLOS', 'PEREZ', 'QUISPE', 'jperez@pj.gob.pe') RETURNING id""",
            (unique_dni() if dni is None else dni,),
        )
    )
    if with_coverage:
        conn.execute(
            """INSERT INTO worker_coverage (worker_id, insurer_id, valid_from)
               SELECT %s, id, DATE '2020-01-01' FROM insurer WHERE code = 'RIMAC'""",
            (worker_id,),
        )
    return worker_id


def open_day(
    conn: psycopg.Connection, site: int, service_date: dt.date | None = None, *, capacity: int | None = None
) -> int:
    day_id = int(scalar(conn, "SELECT ensure_service_day(%s, %s)", (site, service_date or unique_date())))
    if capacity is not None:
        conn.execute("UPDATE service_day SET capacity = %s WHERE id = %s", (capacity, day_id))
    return day_id


def register(
    conn: psycopg.Connection,
    day_id: int,
    worker_id: int,
    user_id: int,
    *,
    status: str = "EN_ESPERA",
    channel: str = "PHONE",
) -> tuple[int, int, str]:
    row = conn.execute(
        """INSERT INTO appointment (service_day_id, worker_id, status, channel, registered_by)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id, ticket_number, ticket_code""",
        (day_id, worker_id, status, channel, user_id),
    ).fetchone()
    assert row is not None
    return int(row[0]), int(row[1]), str(row[2])


def transition(conn: psycopg.Connection, appointment_id: int, to_status: str, user_id: int) -> None:
    """Aplica una transición con los datos que la aplicación debe registrar en cada caso."""
    sets = ["status = %(status)s"]
    params: dict[str, Any] = {"status": to_status, "user": user_id, "id": appointment_id}
    if to_status == "LLAMADO":
        sets += ["called_at = now()", "called_by = %(user)s", "call_count = call_count + 1"]
    elif to_status == "EN_ESPERA":
        sets += ["queued_at = now()"]
    elif to_status == "EN_ATENCION":
        sets += ["started_at = now()", "started_by = %(user)s"]
    elif to_status == "ATENDIDO":
        sets += ["finished_at = now()", "finished_by = %(user)s"]
    elif to_status in STATUS_REASON_TYPE:
        sets += ["closed_at = now()", "closed_by = %(user)s", "close_reason_id = %(reason)s"]
        params["reason"] = reason_id(conn, STATUS_REASON_TYPE[to_status])
    conn.execute(f"UPDATE appointment SET {', '.join(sets)} WHERE id = %(id)s", params)  # noqa: S608


def day_counters(conn: psycopg.Connection, day_id: int) -> tuple[int, int, int]:
    row = conn.execute(
        "SELECT occupied_count, capacity, last_ticket_number FROM service_day WHERE id = %s", (day_id,)
    ).fetchone()
    assert row is not None
    return int(row[0]), int(row[1]), int(row[2])


def insert_audit(conn: psycopg.Connection, action: str = "TEST_EVENT", **fields: Any) -> int:
    return int(
        scalar(
            conn,
            """INSERT INTO audit_event (action, result, resource_type, resource_id, reason, after_data)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING chain_seq""",
            (
                action,
                fields.get("result", "SUCCESS"),
                fields.get("resource_type", "test"),
                fields.get("resource_id", "1"),
                fields.get("reason"),
                psycopg.types.json.Jsonb(fields.get("after_data", {"k": "v"})),
            ),
        )
    )
