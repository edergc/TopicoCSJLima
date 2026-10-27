"""Cierre automático de los días pasados que nadie cerró.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0008_auto_close_day.up.sql")


def downgrade() -> None:
    run_sql_file("0008_auto_close_day.down.sql")
