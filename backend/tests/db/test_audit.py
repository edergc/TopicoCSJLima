"""Auditoría: solo inserción y cadena de hash verificable."""

import threading

import psycopg
import pytest
from psycopg import errors

from .helpers import connect, insert_audit, scalar


def _chain_problems(conn: psycopg.Connection) -> list[tuple[int, str]]:
    return [(int(r[0]), str(r[1])) for r in conn.execute("SELECT * FROM verify_audit_chain()").fetchall()]


def test_events_are_chained(app_db: psycopg.Connection) -> None:
    first = insert_audit(app_db)
    second = insert_audit(app_db)
    assert second == first + 1
    prev_hash, first_hash = (
        scalar(app_db, "SELECT prev_hash FROM audit_event WHERE chain_seq = %s", (second,)),
        scalar(app_db, "SELECT hash FROM audit_event WHERE chain_seq = %s", (first,)),
    )
    assert prev_hash == first_hash
    assert _chain_problems(app_db) == []


def test_client_cannot_forge_chain_fields(app_db: psycopg.Connection) -> None:
    seq = scalar(
        app_db,
        """INSERT INTO audit_event (action, result, chain_seq, hash, prev_hash, occurred_at)
           VALUES ('FORGED_EVENT', 'SUCCESS', 999999, repeat('a', 64), repeat('b', 64), '2000-01-01')
           RETURNING chain_seq""",
    )
    assert seq != 999999
    assert _chain_problems(app_db) == []


def test_app_cannot_modify_or_delete_audit(app_db: psycopg.Connection) -> None:
    seq = insert_audit(app_db)
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("UPDATE audit_event SET reason = 'x' WHERE chain_seq = %s", (seq,))
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("DELETE FROM audit_event WHERE chain_seq = %s", (seq,))
    with pytest.raises(errors.InsufficientPrivilege):
        app_db.execute("TRUNCATE audit_event")


def test_owner_is_blocked_by_trigger(owner_db: psycopg.Connection, app_db: psycopg.Connection) -> None:
    seq = insert_audit(app_db)
    with pytest.raises(errors.InsufficientPrivilege, match="solo inserción"):
        owner_db.execute("UPDATE audit_event SET reason = 'x' WHERE chain_seq = %s", (seq,))
    with pytest.raises(errors.InsufficientPrivilege, match="solo inserción"):
        owner_db.execute("DELETE FROM audit_event WHERE chain_seq = %s", (seq,))


def test_tampering_is_detected(owner_db: psycopg.Connection, app_db: psycopg.Connection) -> None:
    """Aun si alguien con privilegios desactiva los triggers y altera un evento, la verificación lo detecta."""
    seq = insert_audit(app_db, reason="original")
    insert_audit(app_db)
    with owner_db.transaction() as tx:
        owner_db.execute("ALTER TABLE audit_event DISABLE TRIGGER trg_audit_event_forbid_change")
        owner_db.execute("UPDATE audit_event SET reason = 'alterado' WHERE chain_seq = %s", (seq,))
        assert (seq, "HASH_MISMATCH") in _chain_problems(owner_db)

        owner_db.execute("DELETE FROM audit_event WHERE chain_seq = %s", (seq,))
        problems = _chain_problems(owner_db)
        assert (seq + 1, "SEQUENCE_GAP") in problems
        assert (seq + 1, "PREV_HASH_MISMATCH") in problems
        raise psycopg.Rollback(tx)  # deshace la alteración y reactiva el trigger
    assert _chain_problems(app_db) == []


def test_concurrent_inserts_keep_chain_valid(app_db: psycopg.Connection, app_url: str) -> None:
    barrier = threading.Barrier(10)

    def worker() -> None:
        with connect(app_url) as conn:
            barrier.wait()
            for _ in range(5):
                insert_audit(conn, action="CONCURRENT_EVENT")

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert scalar(app_db, "SELECT count(*) FROM audit_event WHERE action = 'CONCURRENT_EVENT'") == 50
    assert _chain_problems(app_db) == []
