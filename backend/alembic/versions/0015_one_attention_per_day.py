"""Una sola atención por trabajador y día.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0015_one_attention_per_day.up.sql")


def downgrade() -> None:
    run_sql_file("0015_one_attention_per_day.down.sql")
