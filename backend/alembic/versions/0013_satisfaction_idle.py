"""Reporte de satisfacción (rating:read) y cierre de sesión por inactividad.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0013_satisfaction_idle.up.sql")


def downgrade() -> None:
    run_sql_file("0013_satisfaction_idle.down.sql")
