"""Fixtures de pruebas de la API: app contra la BD de pruebas, reloj controlable y fábricas."""

import datetime as dt
import itertools
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import INSTITUTION_TZ, FixedClock
from app.core.config import API_PREFIX, Settings
from app.core.ratelimit import limiter
from app.core.security import hash_password
from app.main import create_app
from app.modules.sites.models import Site
from app.modules.users.models import AppUser, Role
from app.modules.workers.models import Insurer, Worker, WorkerCoverage

PASSWORD = "Clave-Segura-2026"
_days = itertools.count()
_dni = itertools.count(70_000_000)
_BASE = dt.date(2040, 1, 2)  # lunes


def next_weekday() -> dt.date:
    """Fecha hábil única por prueba (cada prueba opera su propio día → aislamiento)."""
    while True:
        day = _BASE + dt.timedelta(days=next(_days))
        if day.isoweekday() <= 5:
            return day


@pytest.fixture(scope="session")
def app(test_settings: Settings) -> FastAPI:
    limiter.enabled = False
    return create_app(test_settings, clock=FixedClock(dt.datetime(2040, 1, 2, 9, 0, tzinfo=INSTITUTION_TZ)))


@pytest.fixture
def clock(app: FastAPI) -> FixedClock:
    """Reloj fijado a las 09:00 (Lima) de una fecha hábil única."""
    fixed = FixedClock(dt.datetime.combine(next_weekday(), dt.time(9, 0), tzinfo=INSTITUTION_TZ))
    app.state.clock = fixed
    return fixed


@pytest.fixture
def client(app: FastAPI, clock: FixedClock) -> TestClient:
    return TestClient(app, base_url="http://testserver", raise_server_exceptions=False)


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    with app.state.session_factory() as session:
        yield session


@dataclass
class Actor:
    username: str
    password: str
    public_id: uuid.UUID
    headers: dict[str, str]


@pytest.fixture
def make_user(app: FastAPI, client: TestClient) -> Callable[..., Actor]:
    def factory(*roles: str, sites: tuple[str, ...] = ("ALZ",), login: bool = True, must_change: bool = False) -> Actor:
        username = f"u.{uuid.uuid4().hex[:10]}"
        with app.state.session_factory() as s:
            user = AppUser(
                username=username,
                full_name=f"Usuario {username}",
                password_hash=hash_password(PASSWORD),
                auth_provider="LOCAL",
                must_change_password=must_change,
                is_active=True,
                failed_login_attempts=0,
            )
            user.roles = list(s.scalars(select(Role).where(Role.code.in_(roles))))
            user.sites = list(s.scalars(select(Site).where(Site.code.in_(sites))))
            s.add(user)
            s.commit()
            public_id = user.public_id
        headers: dict[str, str] = {}
        if login:
            response = client.post(f"{API_PREFIX}/auth/login", json={"username": username, "password": PASSWORD})
            assert response.status_code == 200, response.text
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        return Actor(username, PASSWORD, public_id, headers)

    return factory


@pytest.fixture
def operator(make_user: Callable[..., Actor]) -> Actor:
    return make_user("OPERATOR", sites=("ALZ",))


@pytest.fixture
def make_worker(app: FastAPI) -> Callable[..., str]:
    def factory(*, covered: bool = True, active: bool = True, email: str | None = "trabajador@pj.gob.pe") -> str:
        dni = f"{next(_dni):08d}"
        with app.state.session_factory() as s:
            worker = Worker(
                document_type="DNI",
                document_number=dni,
                first_names="ANA MARIA",
                paternal_surname="ROJAS",
                maternal_surname="VEGA",
                institutional_email=email,
                is_active=active,
                deactivated_at=None if active else dt.datetime.now(dt.UTC),
            )
            s.add(worker)
            s.flush()
            if covered:
                rimac = s.scalar(select(Insurer).where(Insurer.code == "RIMAC"))
                assert rimac is not None
                s.add(WorkerCoverage(worker_id=worker.id, insurer_id=rimac.id, valid_from=dt.date(2020, 1, 1)))
            s.commit()
        return dni

    return factory


def site_id(db: Session, code: str = "ALZ") -> int:
    value = db.scalar(select(Site.id).where(Site.code == code))
    assert value is not None
    return value


def api(path: str) -> str:
    return f"{API_PREFIX}{path}"


def register(client: TestClient, actor: Actor, site: int, dni: str, **extra: Any) -> Any:
    return client.post(
        api("/appointments"),
        json={"site_id": site, "document_number": dni, "channel": "PHONE", **extra},
        headers=actor.headers,
    )


def reason_id(client: TestClient, actor: Actor, type_: str, code: str | None = None) -> int:
    reasons = client.get(api("/catalogs/reasons"), params={"type": type_}, headers=actor.headers).json()
    return next(r["id"] for r in reasons if code is None or r["code"] == code)
