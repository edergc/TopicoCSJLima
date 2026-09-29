"""Fixtures para pruebas de la base de datos contra PostgreSQL real.

Al iniciar la sesión se destruye y recrea el esquema de la base de PRUEBAS, y se
verifica el ciclo completo de migraciones (upgrade → downgrade → upgrade).
No se usa SQLite: las pruebas dependen de FOR UPDATE, índices parciales, EXCLUDE y triggers.
"""

import argparse
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR, DB_SCHEMA, get_settings, to_libpq_url

from .helpers import connect


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/db/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.db)


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.cmd_opts = argparse.Namespace(x=["db=test"])  # type: ignore[assignment]
    return cfg


@pytest.fixture(scope="session")
def db_urls() -> tuple[str, str]:
    settings = get_settings()
    if not settings.test_database_url or not settings.test_database_migration_url:
        pytest.fail("Configure TEST_DATABASE_URL y TEST_DATABASE_MIGRATION_URL en backend/.env")
    return to_libpq_url(settings.test_database_url), to_libpq_url(settings.test_database_migration_url)


@pytest.fixture(scope="session", autouse=True)
def migrated_db(db_urls: tuple[str, str]) -> None:
    _, owner_url = db_urls
    with psycopg.connect(owner_url, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {DB_SCHEMA} CASCADE")
        conn.execute(f"CREATE SCHEMA {DB_SCHEMA}")
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture
def app_db(db_urls: tuple[str, str]) -> Iterator[psycopg.Connection]:
    """Conexión con el rol de la APLICACIÓN (privilegios mínimos), en autocommit."""
    with connect(db_urls[0]) as conn:
        yield conn


@pytest.fixture
def owner_db(db_urls: tuple[str, str]) -> Iterator[psycopg.Connection]:
    """Conexión con el rol PROPIETARIO, en autocommit."""
    with connect(db_urls[1]) as conn:
        yield conn


@pytest.fixture
def app_url(db_urls: tuple[str, str]) -> str:
    return db_urls[0]


@pytest.fixture
def user_id(app_db: psycopg.Connection) -> int:
    from .helpers import create_user

    return create_user(app_db)
