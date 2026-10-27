"""Médicos del tópico: registro por sede, asignación al iniciar la atención y reportes."""

import random
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.sites.models import Doctor

from .conftest import Actor, api, register, site_id
from .test_sites_rooms import WEEK


@pytest.fixture
def bar_doctors(db: Session) -> Iterator[None]:
    """Las pruebas comparten la BD: al terminar se desactivan los médicos creados en la sede BAR."""
    yield
    db.execute(update(Doctor).where(Doctor.site_id == site_id(db, "BAR")).values(is_active=False))
    db.commit()


def _cmp() -> str:
    return str(random.randint(100_000, 999_999))


def _start(client: TestClient, actor: Actor, site: int, dni: str, *, finish: bool = True, **body: object) -> dict:
    """Registra, llama e inicia; si inició, finaliza (la sede atiende de a uno) salvo finish=False."""
    appt = register(client, actor, site, dni).json()
    client.post(api(f"/appointments/{appt['public_id']}/call"), json={}, headers=actor.headers)
    started = client.post(api(f"/appointments/{appt['public_id']}/start"), json=body, headers=actor.headers).json()
    if finish and started.get("status") == "EN_ATENCION":
        client.post(api(f"/appointments/{appt['public_id']}/finish"), json={}, headers=actor.headers)
    return started


@pytest.mark.usefixtures("bar_doctors")
def test_doctor_registry_and_assignment(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    bar = site_id(db, "BAR")
    supervisor = make_user("SUPERVISOR", sites=("BAR",))
    operator = make_user("OPERATOR", sites=("BAR",))
    url = api(f"/sites/{bar}/doctors")

    # Sin médicos registrados la atención se inicia igual (sin médico)
    assert _start(client, operator, bar, make_worker())["doctor_id"] is None

    cmp = _cmp()
    first = client.post(
        url,
        json={"full_name": "Dra. Ana Pérez Soto", "cmp": cmp, "specialty": "Medicina General"},
        headers=supervisor.headers,
    )
    assert first.status_code == 201, first.text
    doctor = first.json()
    duplicate = client.post(url, json={"full_name": "Otro", "cmp": cmp}, headers=supervisor.headers)
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "DOCTOR_DUPLICATE_CMP")
    assert client.post(url, json={"full_name": "X Y Z"}, headers=operator.headers).status_code == 403

    # Un solo médico activo: se asigna automáticamente
    started = _start(client, operator, bar, make_worker())
    assert (started["doctor_id"], started["doctor_name"]) == (doctor["id"], "Dra. Ana Pérez Soto")

    # Con dos médicos activos hay que indicar quién atiende
    second = client.post(url, json={"full_name": "Dr. Luis Rojas"}, headers=supervisor.headers).json()
    assert _start(client, operator, bar, make_worker())["code"] == "DOCTOR_REQUIRED"
    chosen = _start(client, operator, bar, make_worker(), doctor_id=second["id"])
    assert chosen["doctor_name"] == "Dr. Luis Rojas"

    # Un médico desactivado no puede asignarse
    patch = client.patch(f"{url}/{second['id']}", json={"is_active": False}, headers=supervisor.headers)
    assert patch.json()["is_active"] is False
    assert _start(client, operator, bar, make_worker(), doctor_id=second["id"])["code"] == "DOCTOR_INVALID"
    active = client.get(url, params={"active_only": True}, headers=operator.headers).json()
    assert [d["id"] for d in active] == [doctor["id"]]

    # Pantalla de sala y reportes
    _start(client, operator, bar, make_worker(), finish=False)
    board = client.get(api("/public/display/BAR")).json()
    assert any(t["doctor"] == "Dra. Ana Pérez Soto" for t in board["in_service"])
    summary = client.get(api("/reports/summary"), params={"site_id": bar}, headers=supervisor.headers).json()
    assert {"doctor": "Dra. Ana Pérez Soto", "attended": 1} in [
        {k: d[k] for k in ("doctor", "attended")} for d in summary["by_doctor"]
    ]


def test_delete_only_unused_rooms_and_doctors(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    admin = make_user("ADMIN", sites=("ALZ",))
    body = {"code": "DEL", "name": "Sede de prueba", "short_name": "Prueba", "ticket_prefix": "D", "blocks": WEEK}
    assert client.post(api("/sites"), json=body, headers=admin.headers).status_code == 201
    sid = site_id(db, "DEL")
    supervisor = make_user("SUPERVISOR", sites=("DEL",))
    operator = make_user("OPERATOR", sites=("DEL",))
    rooms, doctors = api(f"/sites/{sid}/rooms"), api(f"/sites/{sid}/doctors")
    used_room = client.post(rooms, json={"name": "Consultorio 1"}, headers=supervisor.headers).json()
    used_doc = client.post(
        doctors, json={"full_name": "Dra. Usada Ruiz", "cmp": _cmp()}, headers=supervisor.headers
    ).json()
    _start(client, operator, sid, make_worker())  # con un solo consultorio y médico, se asignan solos

    spare_room = client.post(rooms, json={"name": "Consultorio 2"}, headers=supervisor.headers).json()
    spare_doc = client.post(
        doctors, json={"full_name": "Dr. Nuevo Paz", "cmp": _cmp()}, headers=supervisor.headers
    ).json()
    client.put(
        f"{doctors}/{spare_doc['id']}/schedule",
        json={"blocks": [{"weekday": 1, "start_time": "08:00", "end_time": "12:00"}]},
        headers=supervisor.headers,
    )

    assert client.delete(f"{rooms}/{spare_room['id']}", headers=operator.headers).status_code == 403
    assert client.delete(f"{rooms}/{spare_room['id']}", headers=supervisor.headers).status_code == 204
    assert client.delete(f"{doctors}/{spare_doc['id']}", headers=supervisor.headers).status_code == 204
    assert client.delete(f"{rooms}/{used_room['id']}", headers=supervisor.headers).json()["code"] == "ROOM_IN_USE"
    assert client.delete(f"{doctors}/{used_doc['id']}", headers=supervisor.headers).json()["code"] == "DOCTOR_IN_USE"
    assert [r["name"] for r in client.get(rooms, headers=supervisor.headers).json()] == ["Consultorio 1"]
    assert [d["full_name"] for d in client.get(doctors, headers=supervisor.headers).json()] == ["Dra. Usada Ruiz"]
