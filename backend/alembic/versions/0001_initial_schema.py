"""Esquema inicial: seguridad, sedes, trabajadores, agenda, atenciones, notificaciones, auditoría.

Revision ID: 0001
Revises:
Create Date: 2026-09-29
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0001_initial_schema.up.sql")


def downgrade() -> None:
    run_sql_file("0001_initial_schema.down.sql")
