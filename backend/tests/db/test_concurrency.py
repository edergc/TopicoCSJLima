"""Concurrencia real: varias conexiones simultáneas contra PostgreSQL (caso crítico 4)."""

import threading
from collections.abc import Callable
from typing import Any

import psycopg
from psycopg import errors

from .helpers import connect, create_worker, day_counters, open_day, register, scalar, site_id, unique_date

THREADS = 12


def _run_concurrently(app_url: str, work: Callable[[psycopg.Connection, int], Any]) -> list[Any]:
    """Ejecuta `work` en N hilos (cada uno con su conexión) liberados a la vez por una barrera."""
    barrier = threading.Barrier(THREADS)
    results: list[Any] = [None] * THREADS

    def runner(index: int) -> None:
        with connect(app_url) as conn:
            barrier.wait()
            try:
                results[index] = work(conn, index)
            except psycopg.Error as exc:
                results[index] = exc

    threads = [threading.Thread(target=runner, args=(i,)) for i in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def test_caso_4_concurrent_registrations_for_last_slot(app_db: psycopg.Connection, app_url: str, user_id: int) -> None:
    day = open_day(app_db, site_id(app_db), capacity=5)
    for _ in range(4):
        register(app_db, day, create_worker(app_db), user_id)
    workers = [create_worker(app_db) for _ in range(THREADS)]

    results = _run_concurrently(app_url, lambda conn, i: register(conn, day, workers[i], user_id))

    successes = [r for r in results if isinstance(r, tuple)]
    failures = [r for r in results if isinstance(r, errors.CheckViolation)]
    assert len(successes) == 1
    assert len(failures) == THREADS - 1
    assert all(f.diag.constraint_name == "ck_service_day_capacity" for f in failures)
    assert day_counters(app_db, day) == (5, 5, 5)


def test_concurrent_registrations_get_unique_contiguous_tickets(
    app_db: psycopg.Connection, app_url: str, user_id: int
) -> None:
    day = open_day(app_db, site_id(app_db))  # capacidad 20 > hilos
    workers = [create_worker(app_db) for _ in range(THREADS)]

    results = _run_concurrently(app_url, lambda conn, i: register(conn, day, workers[i], user_id))

    numbers = sorted(r[1] for r in results if isinstance(r, tuple))
    assert numbers == list(range(1, THREADS + 1))


def test_concurrent_registrations_of_same_worker(app_db: psycopg.Connection, app_url: str, user_id: int) -> None:
    """Dos encargadas registran al mismo trabajador a la vez: solo una lo logra y no se pierde cupo."""
    day = open_day(app_db, site_id(app_db))
    worker = create_worker(app_db)

    results = _run_concurrently(app_url, lambda conn, _: register(conn, day, worker, user_id))

    assert sum(isinstance(r, tuple) for r in results) == 1
    assert all(isinstance(r, (tuple, errors.UniqueViolation)) for r in results)
    assert day_counters(app_db, day)[0] == 1


def test_concurrent_service_day_creation(app_db: psycopg.Connection, app_url: str) -> None:
    date, alz = unique_date(), site_id(app_db)
    results = _run_concurrently(app_url, lambda conn, _: scalar(conn, "SELECT ensure_service_day(%s, %s)", (alz, date)))
    assert len(set(results)) == 1
    assert scalar(app_db, "SELECT count(*) FROM service_day WHERE site_id = %s AND service_date = %s", (alz, date)) == 1


def test_call_next_with_skip_locked_never_calls_same_person_twice(
    app_db: psycopg.Connection, app_url: str, user_id: int
) -> None:
    """Patrón que usará 'Llamar siguiente': FOR UPDATE SKIP LOCKED sobre la cola."""
    day = open_day(app_db, site_id(app_db))
    for _ in range(THREADS):
        register(app_db, day, create_worker(app_db), user_id)

    def call_next(conn: psycopg.Connection, _: int) -> int:
        with conn.transaction():
            row = conn.execute(
                """SELECT id FROM appointment WHERE service_day_id = %s AND status = 'EN_ESPERA'
                   ORDER BY ticket_number LIMIT 1 FOR UPDATE SKIP LOCKED""",
                (day,),
            ).fetchone()
            assert row is not None
            conn.execute(
                """UPDATE appointment SET status = 'LLAMADO', called_at = now(), called_by = %s,
                          call_count = call_count + 1 WHERE id = %s""",
                (user_id, row[0]),
            )
            return int(row[0])

    called = _run_concurrently(app_url, call_next)
    assert all(isinstance(c, int) for c in called)
    assert len(set(called)) == THREADS
