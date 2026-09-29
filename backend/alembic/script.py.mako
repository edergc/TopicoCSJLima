"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Recuerde: toda tabla nueva debe otorgar explícitamente sus privilegios a topico_app
y topico_readonly (mínimo privilegio). Ver database/README.md.
"""

from collections.abc import Sequence

from sqlfile import run_sql_file  # noqa: F401

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
