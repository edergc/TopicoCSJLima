"""Paquete operativo: horario y ausencias por médico, pausa, cierre del día, calificación y mensajes de sala.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0006_operations_pack.up.sql")


def downgrade() -> None:
    run_sql_file("0006_operations_pack.down.sql")
