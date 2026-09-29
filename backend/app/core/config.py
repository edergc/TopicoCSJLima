"""Configuración de la aplicación leída desde variables de entorno / archivo .env.

Aquí solo va configuración TÉCNICA (conexiones, secretos, entorno). Los parámetros de
negocio (capacidad, horarios, tolerancias...) viven en la base de datos.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

DB_SCHEMA = "topico"


def _validate_pg_url(value: str | None) -> str | None:
    if value is not None and not value.startswith("postgresql+psycopg://"):
        raise ValueError("Debe usar el driver psycopg 3: 'postgresql+psycopg://usuario:clave@host:puerto/bd'")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"

    database_url: str
    database_migration_url: str
    test_database_url: str | None = None
    test_database_migration_url: str | None = None

    _check_urls = field_validator(
        "database_url",
        "database_migration_url",
        "test_database_url",
        "test_database_migration_url",
    )(_validate_pg_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # los valores obligatorios provienen del entorno / .env


def to_libpq_url(sqlalchemy_url: str) -> str:
    """Convierte 'postgresql+psycopg://...' en una URL libpq utilizable por psycopg/psql."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)
