"""Ejecución de archivos SQL versionados desde las revisiones de Alembic.

El DDL vive en archivos .sql legibles (revisables por un DBA). Se envían al servidor
tal cual (protocolo simple de psycopg), sin que SQLAlchemy interprete ':' o '%'.
"""

from pathlib import Path

from alembic import context, op

SQL_DIR = Path(__file__).resolve().parent / "sql"


def run_sql_file(name: str) -> None:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(f"-- >>> {name}\n{sql}\n-- <<< {name}\n")
        return
    driver_connection = op.get_bind().connection.driver_connection
    if driver_connection is None:
        raise RuntimeError("No se pudo obtener la conexión del driver psycopg.")
    driver_connection.execute(sql)  # sin parámetros: admite múltiples sentencias
