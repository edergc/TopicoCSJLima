"""Pantalla pública de turnos (sala de espera)."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.sites.models import SystemParameter

from .conftest import Actor, api, register, site_id


def test_display_board_shows_calls_and_queue_without_personal_data(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    alz = site_id(db)
    dnis = [make_worker() for _ in range(3)]
    for dni in dnis:
        register(client, operator, alz, dni)
    client.post(api(f"/sites/{alz}/queue/call-next"), headers=operator.headers)

    response = client.get(api("/public/display/alz"))  # sin sesión; el código no distingue mayúsculas
    assert response.status_code == 200, response.text
    board = response.json()
    assert board["site"]["code"] == "ALZ"
    assert [(t["ticket_code"], t["name"], t["call_count"]) for t in board["calling"]] == [("A-001", "Ana R.", 1)]
    assert [t["ticket_code"] for t in board["waiting"]] == ["A-002", "A-003"]
    assert board["waiting_total"] == 2
    assert board["waiting"][0]["estimated_at"]
    # Minimización de datos: nada que identifique más allá del nombre abreviado.
    for dni in dnis:
        assert dni not in response.text
    assert "ROJAS" not in response.text
    assert "VEGA" not in response.text
    assert "@" not in response.text

    sites = client.get(api("/public/display/sites")).json()
    assert {s["code"] for s in sites} >= {"ALZ", "BAR"}


def test_display_can_hide_names_or_be_disabled(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    alz = site_id(db)
    register(client, operator, alz, make_worker())
    try:
        db.execute(update(SystemParameter).where(SystemParameter.key == "display.show_names").values(value=False))
        db.commit()
        board = client.get(api("/public/display/ALZ")).json()
        assert board["show_names"] is False
        assert all(t["name"] is None for t in board["waiting"])

        db.execute(update(SystemParameter).where(SystemParameter.key == "display.enabled").values(value=False))
        db.commit()
        disabled = client.get(api("/public/display/ALZ"))
        assert (disabled.status_code, disabled.json()["code"]) == (404, "DISPLAY_DISABLED")
    finally:
        db.execute(
            update(SystemParameter)
            .where(SystemParameter.key.in_(["display.show_names", "display.enabled"]))
            .values(value=True)
        )
        db.commit()


def test_display_unknown_site(client: TestClient) -> None:
    response = client.get(api("/public/display/XYZ"))
    assert (response.status_code, response.json()["code"]) == (404, "SITE_NOT_FOUND")
