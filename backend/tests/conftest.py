"""Fixtures compartidas. Todas las pruebas usan PostgreSQL real (base topico_csj_test).

Al iniciar la sesión se destruye y recrea el esquema y se verifica el ciclo completo de
migraciones (upgrade → downgrade → upgrade). No se usa SQLite: el sistema depende de
FOR UPDATE, índices parciales, EXCLUDE y triggers.
"""

import argparse
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr

from app.core.config import BACKEND_DIR, DB_SCHEMA, Settings, get_settings, to_libpq_url

from .db.helpers import connect


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
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


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    base = get_settings()
    assert base.test_database_url
    return base.model_copy(
        update={
            "environment": "test",
            "database_url": base.test_database_url,
            "jwt_secret": SecretStr("pruebas-" + "x" * 40),
            "log_dir": None,
            "email_backend": "disabled",
            "notifications_worker_enabled": False,
            "cors_origins": [],
            # Independiente de la configuración de despliegue que tenga el .env local
            "cookie_secure": False,
            "trusted_proxy_count": 0,
            "docs_enabled": None,
            "dev_clock_start": None,
            "frontend_dist": None,
            "public_app_url": None,
        }
    )


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
    from .db.helpers import create_user

    return create_user(app_db)
