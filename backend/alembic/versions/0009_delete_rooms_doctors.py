"""Eliminar consultorios y médicos que nunca se usaron en una atención.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0009_delete_rooms_doctors.up.sql")


def downgrade() -> None:
    run_sql_file("0009_delete_rooms_doctors.down.sql")
