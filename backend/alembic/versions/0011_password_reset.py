"""Recuperación de contraseña por correo (enlace de un solo uso).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0011_password_reset.up.sql")


def downgrade() -> None:
    run_sql_file("0011_password_reset.down.sql")
