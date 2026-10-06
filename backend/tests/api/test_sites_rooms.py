"""Sedes nuevas y consultorios administrables."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .conftest import Actor, api, register, site_id

WEEK = [{"weekday": d, "block": "AM", "start_time": "08:00", "end_time": "13:00"} for d in range(1, 6)]


def test_new_site_with_rooms_and_call_routing(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    admin = make_user("ADMIN", sites=("ALZ",))
    body = {
        "code": "sjl",
        "name": "Sede San Juan de Lurigancho",
        "short_name": "San Juan de Lurigancho",
        "ticket_prefix": "s",
        "daily_capacity": 15,
        "blocks": WEEK,
    }
    assert client.post(api("/sites"), json=body, headers=make_user("SUPERVISOR").headers).status_code == 403
    created = client.post(api("/sites"), json=body, headers=admin.headers)
    assert created.status_code == 201, created.text
    site = created.json()
    assert (site["code"], site["ticket_prefix"]) == ("SJL", "S")
    duplicate = client.post(api("/sites"), json={**body, "ticket_prefix": "T"}, headers=admin.headers)
    assert duplicate.json()["code"] == "SITE_CODE_TAKEN"

    # Quien la creó (y los administradores) acceden a ella; aparece en la lista completa
    assert site["id"] in [s["id"] for s in client.get(api("/sites"), headers=admin.headers).json()]
    assert "SJL" in [s["code"] for s in client.get(api("/sites/all"), headers=admin.headers).json()]

    # La sede opera desde ya con su configuración y horario iniciales
    sid = site_id(db, "SJL")
    operator = make_user("OPERATOR", sites=("SJL",))
    availability = client.get(api(f"/sites/{sid}/availability"), headers=operator.headers).json()
    assert (availability["capacity"], availability["can_register"]) == (15, True)
    first = register(client, operator, sid, make_worker()).json()
    assert first["ticket_code"] == "S-001"

    # Sin consultorios: el llamado no exige elegir
    rooms_url = api(f"/sites/{sid}/rooms")
    called = client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers).json()
    assert called["room_id"] is None
    client.post(api(f"/appointments/{first['public_id']}/start"), json={}, headers=operator.headers)
    client.post(api(f"/appointments/{first['public_id']}/finish"), json={}, headers=operator.headers)

    # Un consultorio: se asigna solo
    supervisor = make_user("SUPERVISOR", sites=("SJL",))
    one = client.post(
        rooms_url, json={"name": "Consultorio 1", "location_note": "Primer piso"}, headers=supervisor.headers
    )
    assert one.status_code == 201, one.text
    assert (
        client.post(rooms_url, json={"name": "consultorio 1"}, headers=supervisor.headers).json()["code"]
        == "ROOM_DUPLICATE"
    )
    register(client, operator, sid, make_worker())
    auto = client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers).json()
    assert auto["room_name"] == "Consultorio 1"

    # Dos consultorios: hay que indicar a cuál se llama
    two = client.post(rooms_url, json={"name": "Consultorio 2", "sort_order": 2}, headers=supervisor.headers).json()
    register(client, operator, sid, make_worker())
    missing = client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers)
    assert missing.json()["code"] == "ROOM_REQUIRED"
    routed = client.post(api(f"/sites/{sid}/queue/call-next"), json={"room_id": two["id"]}, headers=operator.headers)
    assert routed.json()["room_name"] == "Consultorio 2"

    board = client.get(api("/public/display/sjl")).json()
    assert board["calling"][0]["room"] == "Consultorio 2"

    # Consultorio desactivado: no se puede usar
    client.patch(f"{rooms_url}/{two['id']}", json={"is_active": False}, headers=supervisor.headers)
    register(client, operator, sid, make_worker())
    invalid = client.post(api(f"/sites/{sid}/queue/call-next"), json={"room_id": two["id"]}, headers=operator.headers)
    assert invalid.json()["code"] == "ROOM_INVALID"
    active = client.get(rooms_url, params={"active_only": True}, headers=operator.headers).json()
    assert [r["name"] for r in active] == ["Consultorio 1"]


def test_inactive_site_can_be_reactivated_by_site_manager(
    client: TestClient, make_user: Callable[..., Actor], db: Session
) -> None:
    admin = make_user("ADMIN", sites=("ALZ",))
    body = {"code": "INACT", "name": "Sede temporal", "short_name": "Temporal", "ticket_prefix": "X", "blocks": WEEK}
    sid = client.post(api("/sites"), json=body, headers=admin.headers).json()["id"]
    assert (
        client.patch(api(f"/sites/{sid}"), json={"is_active": False}, headers=admin.headers).json()["is_active"]
        is False
    )
    assert sid not in [s["id"] for s in client.get(api("/sites"), headers=admin.headers).json()]
    assert (
        client.patch(api(f"/sites/{sid}"), json={"is_active": True}, headers=admin.headers).json()["is_active"] is True
    )
