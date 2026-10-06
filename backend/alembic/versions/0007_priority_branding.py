"""Prioridad explícita y auditable; identidad visual configurable (logo y color).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0007_priority_branding.up.sql")


def downgrade() -> None:
    run_sql_file("0007_priority_branding.down.sql")
