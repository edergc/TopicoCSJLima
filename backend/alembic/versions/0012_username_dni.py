"""El usuario del sistema es el DNI (8 dígitos).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0012_username_dni.up.sql")


def downgrade() -> None:
    run_sql_file("0012_username_dni.down.sql")
