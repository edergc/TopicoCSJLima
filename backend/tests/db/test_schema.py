"""Estructura, datos de referencia y privilegios del esquema."""

import psycopg
from psycopg import errors

from .helpers import scalar

EXPECTED_TABLES = {
    "app_user",
    "role",
    "permission",
    "role_permission",
    "user_role",
    "site",
    "user_site",
    "refresh_token",
    "system_parameter",
    "site_setting_version",
    "site_schedule",
    "site_closure",
    "import_batch",
    "import_row",
    "department",
    "insurer",
    "worker",
    "worker_coverage",
    "reason",
    "appointment_status",
    "appointment_status_transition",
    "service_day",
    "appointment",
    "appointment_event",
    "notification_template",
    "notification",
    "audit_event",
}


def _tables(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'topico' AND tablename <> 'alembic_version'"
    ).fetchall()
    return {r[0] for r in rows}


def test_all_tables_exist(owner_db: psycopg.Connection) -> None:
    assert _tables(owner_db) == EXPECTED_TABLES


def test_every_table_is_documented(owner_db: psycopg.Connection) -> None:
    undocumented = [
        t
        for t in _tables(owner_db)
        if scalar(owner_db, "SELECT obj_description(%s::regclass)", (f"topico.{t}",)) is None
    ]
    assert undocumented == []


def test_reference_data_loaded(app_db: psycopg.Connection) -> None:
    assert scalar(app_db, "SELECT count(*) FROM appointment_status") == 8
    assert scalar(app_db, "SELECT count(*) FROM appointment_status_transition") == 11
    assert scalar(app_db, "SELECT array_agg(code ORDER BY code) FROM site") == ["ALZ", "BAR"]
    assert scalar(app_db, "SELECT array_agg(code ORDER BY code) FROM role") == [
        "ADMIN",
        "AUDITOR",
        "OPERATOR",
        "SUPERVISOR",
    ]
    assert scalar(app_db, "SELECT count(*) FROM site_setting_version WHERE valid_from = DATE '2026-01-01'") == 2
    assert scalar(app_db, "SELECT count(*) FROM site_schedule") == 20  # 2 sedes x 5 días x 2 bloques
    assert scalar(app_db, "SELECT count(*) FROM notification_template") == 4


def test_every_permission_is_assigned_to_some_role(app_db: psycopg.Connection) -> None:
    orphans = app_db.execute(
        "SELECT code FROM permission p WHERE NOT EXISTS (SELECT 1 FROM role_permission rp WHERE rp.permission_id = p.id)"
    ).fetchall()
    assert orphans == []


def test_admin_does_not_operate_queue_by_default(app_db: psycopg.Connection) -> None:
    """Segregación de funciones: el administrador no registra ni opera atenciones."""
    count = scalar(
        app_db,
        """SELECT count(*) FROM role_permission rp JOIN role r ON r.id = rp.role_id
           JOIN permission p ON p.id = rp.permission_id
           WHERE r.code = 'ADMIN' AND p.code IN ('appointment:create', 'appointment:operate')""",
    )
    assert count == 0


def test_app_role_can_read_every_table(app_db: psycopg.Connection) -> None:
    denied = [
        t for t in EXPECTED_TABLES if not scalar(app_db, "SELECT has_table_privilege(%s, 'SELECT')", (f"topico.{t}",))
    ]
    assert denied == []


def test_app_role_cannot_run_ddl(app_db: psycopg.Connection) -> None:
    try:
        app_db.execute("CREATE TABLE topico.intruso (id int)")
    except errors.InsufficientPrivilege:
        return
    raise AssertionError("El rol de la aplicación no debe poder crear tablas")


def test_app_role_has_no_delete_on_business_tables(app_db: psycopg.Connection) -> None:
    for table in ("appointment", "appointment_event", "audit_event", "worker", "service_day", "app_user"):
        assert scalar(app_db, "SELECT has_table_privilege(%s, 'DELETE')", (f"topico.{table}",)) is False, table
