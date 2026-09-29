"""Datos de referencia: estados, transiciones, permisos, roles, sedes, configuración inicial.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0002_reference_data.up.sql")


def downgrade() -> None:
    run_sql_file("0002_reference_data.down.sql")
