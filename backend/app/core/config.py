"""Configuración de la aplicación leída desde variables de entorno / archivo .env.

Aquí solo va configuración TÉCNICA (conexiones, secretos, entorno, SMTP). Los parámetros de
negocio (capacidad, horarios, tolerancias...) viven en la base de datos.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

DB_SCHEMA = "topico"
API_PREFIX = "/api/v1"


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

    # --- Base de datos ------------------------------------------------------
    database_url: str
    database_migration_url: str
    test_database_url: str | None = None
    test_database_migration_url: str | None = None
    db_pool_size: int = 10
    db_slow_query_ms: int = 500

    # --- Seguridad ----------------------------------------------------------
    jwt_secret: SecretStr = Field(default=SecretStr(""))
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_minutes: int = Field(default=15, ge=1, le=120)
    refresh_cookie_name: str = "topico_refresh"
    cookie_secure: bool | None = None  # None → True solo en producción
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trusted_proxy_count: int = Field(default=0, ge=0, le=5)
    docs_enabled: bool | None = None  # None → deshabilitado en producción

    # --- Logs ---------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_dir: Path | None = BACKEND_DIR / "logs"
    log_json_console: bool = False
    log_retention_days: int = 90

    # --- Notificaciones -----------------------------------------------------
    email_backend: Literal["smtp", "console", "file", "disabled"] = "console"
    email_file_dir: Path = BACKEND_DIR / "logs" / "emails"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_timeout_seconds: int = 15
    notifications_worker_enabled: bool = True
    notifications_poll_seconds: float = 5.0

    # --- Aplicación ---------------------------------------------------------
    public_app_url: str | None = None  # URL de la consulta pública (se incluye en correos)
    max_upload_mb: int = 10

    _check_urls = field_validator(
        "database_url",
        "database_migration_url",
        "test_database_url",
        "test_database_migration_url",
    )(_validate_pg_url)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @model_validator(mode="after")
    def _check_security(self) -> "Settings":
        secret = self.jwt_secret.get_secret_value()
        if self.environment == "production" and len(secret) < 32:
            raise ValueError("JWT_SECRET debe tener al menos 32 caracteres en producción.")
        if self.email_backend == "smtp" and not (self.smtp_host and self.smtp_from):
            raise ValueError("EMAIL_BACKEND=smtp requiere SMTP_HOST y SMTP_FROM.")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def api_docs_enabled(self) -> bool:
        return (not self.is_production) if self.docs_enabled is None else self.docs_enabled

    def effective_jwt_secret(self) -> str:
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < 32:
            if self.is_production:  # pragma: no cover - bloqueado por el validador
                raise RuntimeError("JWT_SECRET inválido")
            # Solo desarrollo/pruebas: secreto efímero (las sesiones no sobreviven a un reinicio).
            return _ephemeral_secret()
        return secret


@lru_cache
def _ephemeral_secret() -> str:
    import secrets

    return secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # los valores obligatorios provienen del entorno / .env


def to_libpq_url(sqlalchemy_url: str) -> str:
    """Convierte 'postgresql+psycopg://...' en una URL libpq utilizable por psycopg/psql."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)
