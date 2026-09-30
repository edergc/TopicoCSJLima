"""Parámetros de la pantalla pública de turnos (sala de espera).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0003_display_parameters.up.sql")


def downgrade() -> None:
    run_sql_file("0003_display_parameters.down.sql")
