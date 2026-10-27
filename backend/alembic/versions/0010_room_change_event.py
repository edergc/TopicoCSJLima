"""Evento «cambio de consultorio» en la línea de tiempo de la atención.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0010_room_change_event.up.sql")


def downgrade() -> None:
    run_sql_file("0010_room_change_event.down.sql")
