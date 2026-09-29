"""Entorno de Alembic.

Uso:
    alembic upgrade head                 # base principal (DATABASE_MIGRATION_URL)
    alembic -x db=test upgrade head      # base de pruebas (TEST_DATABASE_MIGRATION_URL)
    alembic upgrade head --sql > ../database/schema.sql   # genera el DDL sin conectarse
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import DB_SCHEMA, get_settings

# Permite que las revisiones importen el helper alembic/sqlfile.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Las migraciones son SQL explícito (alembic/sql); no se usa autogenerate como fuente de verdad.
target_metadata = None


def _migration_url() -> str:
    settings = get_settings()
    target = context.get_x_argument(as_dictionary=True).get("db", "main")
    if target == "test":
        if not settings.test_database_migration_url:
            raise RuntimeError("TEST_DATABASE_MIGRATION_URL no está configurada.")
        return settings.test_database_migration_url
    if target != "main":
        raise RuntimeError(f"Valor de -x db desconocido: {target!r} (use 'main' o 'test').")
    return settings.database_migration_url


def run_migrations_offline() -> None:
    context.configure(
        url="postgresql+psycopg://",
        target_metadata=target_metadata,
        literal_binds=True,
        version_table_schema=DB_SCHEMA,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        _migration_url(),
        poolclass=pool.NullPool,
        connect_args={"options": f"-c search_path={DB_SCHEMA},public -c timezone=UTC"},
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=DB_SCHEMA,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
