"""Autorización por permisos y por sede (casos críticos 5 y 6)."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent

from .conftest import Actor, api, register, site_id


def test_caso_5_operator_cannot_register_in_other_site(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    response = register(client, operator, site_id(db, "BAR"), make_worker())
    assert (response.status_code, response.json()["code"]) == (403, "SITE_FORBIDDEN")
    denied = db.scalars(
        select(AuditEvent).where(AuditEvent.username == operator.username, AuditEvent.result == "DENIED")
    ).all()
    assert [(e.action, e.reason) for e in denied] == [("ACCESS_DENIED", "SITE_FORBIDDEN")]


def test_caso_5_operator_cannot_modify_appointment_of_other_site(
    client: TestClient, make_user: Callable[..., Actor], operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    barreto = make_user("OPERATOR", sites=("BAR",))
    created = register(client, barreto, site_id(db, "BAR"), make_worker())
    assert created.status_code == 201, created.text
    appointment = created.json()["public_id"]

    for action in ("call", "cancel", "void"):
        response = client.post(api(f"/appointments/{appointment}/{action}"), json={}, headers=operator.headers)
        assert (response.status_code, response.json()["code"]) == (403, "SITE_FORBIDDEN"), action
    assert client.get(api(f"/appointments/{appointment}"), headers=operator.headers).status_code == 403
    assert client.get(api(f"/sites/{site_id(db, 'BAR')}/queue"), headers=operator.headers).status_code == 403


def test_caso_6_operator_cannot_change_configuration(client: TestClient, operator: Actor, db: Session) -> None:
    alz = site_id(db, "ALZ")
    attempts = [
        client.post(
            api(f"/sites/{alz}/settings"),
            headers=operator.headers,
            json={
                "valid_from": "2099-01-01",
                "daily_capacity": 99,
                "slot_minutes": 15,
                "tolerance_minutes": 10,
                "change_reason": "intento",
            },
        ),
        client.put(api("/admin/parameters/booking.advance_days_max"), headers=operator.headers, json={"value": 5}),
        client.get(api("/admin/users"), headers=operator.headers),
        client.get(api("/audit-events"), headers=operator.headers),
        client.patch(
            api(f"/sites/{alz}/service-days/2099-01-05/capacity"),
            headers=operator.headers,
            json={"capacity": 50, "reason": "intento"},
        ),
    ]
    assert [(r.status_code, r.json()["code"]) for r in attempts] == [(403, "FORBIDDEN")] * len(attempts)


def test_auditor_is_read_only(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    auditor = make_user("AUDITOR", sites=("ALZ",))
    assert client.get(api("/audit-events"), headers=auditor.headers).status_code == 200
    response = register(client, auditor, site_id(db), make_worker())
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


def test_admin_does_not_operate_the_queue(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    admin = make_user("ADMIN", sites=("ALZ", "BAR"))
    assert register(client, admin, site_id(db), make_worker()).status_code == 403
    assert client.get(api("/admin/users"), headers=admin.headers).status_code == 200


def test_error_responses_do_not_leak_internals(client: TestClient, operator: Actor) -> None:
    response = client.get(api("/appointments/no-es-un-uuid"), headers=operator.headers)
    body = response.json()
    assert response.status_code == 422
    assert body["success"] is False
    assert body["code"] == "VALIDATION_ERROR"
    assert body["request_id"]
    assert "Traceback" not in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
