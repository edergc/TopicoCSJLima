"""Correo de registro como ticket digital (plantilla de texto).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0014_ticket_email.up.sql")


def downgrade() -> None:
    run_sql_file("0014_ticket_email.down.sql")
