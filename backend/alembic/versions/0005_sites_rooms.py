"""Sedes y consultorios administrables (permiso site:manage, consultorios, consultorio de la atención).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from sqlfile import run_sql_file

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0005_sites_rooms.up.sql")


def downgrade() -> None:
    run_sql_file("0005_sites_rooms.down.sql")
