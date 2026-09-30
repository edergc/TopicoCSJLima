"""Flujo operativo de la encargada y casos críticos, a través de la API."""

import datetime as dt
import threading
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import INSTITUTION_TZ, FixedClock

from .conftest import Actor, api, reason_id, register, site_id

CAPACITY_MESSAGE = "Se ha alcanzado la capacidad máxima de atención para esta sede en la fecha seleccionada."


def set_capacity(client: TestClient, supervisor: Actor, site: int, day: dt.date, capacity: int) -> None:
    response = client.patch(
        api(f"/sites/{site}/service-days/{day.isoformat()}/capacity"),
        json={"capacity": capacity, "reason": "Prueba de capacidad"},
        headers=supervisor.headers,
    )
    assert response.status_code == 200, response.text


def queue(client: TestClient, actor: Actor, site: int) -> dict:
    response = client.get(api(f"/sites/{site}/queue"), headers=actor.headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_full_operational_flow(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session, clock: FixedClock
) -> None:
    alz = site_id(db)
    dni_a, dni_b = make_worker(), make_worker()

    # Buscar DNI → verificar habilitación
    lookup = client.get(api("/workers/eligibility"), params={"document_number": dni_a}, headers=operator.headers)
    assert lookup.json()["eligible"] is True
    assert lookup.json()["worker"]["document_number"] == dni_a

    # Registrar → turno generado, en espera, con posición y hora estimada
    first = register(client, operator, alz, dni_a)
    assert first.status_code == 201, first.text
    a = first.json()
    assert (a["ticket_code"], a["status"], a["position"], a["people_ahead"]) == ("A-001", "EN_ESPERA", 1, 0)
    assert a["estimated_at"] is not None
    b = register(client, operator, alz, dni_b).json()
    assert (b["ticket_code"], b["position"]) == ("A-002", 2)

    # La búsqueda ahora muestra su turno activo
    lookup = client.get(api("/workers/eligibility"), params={"document_number": dni_a}, headers=operator.headers)
    assert lookup.json()["active_appointment"]["ticket_code"] == "A-001"

    # Panel operativo
    board = queue(client, operator, alz)
    assert board["counts"]["waiting"] == 2
    assert board["counts"]["available"] == 18
    assert board["next_ticket_code"] == "A-001"

    # Llamar siguiente → A-001
    called = client.post(api(f"/sites/{alz}/queue/call-next"), headers=operator.headers)
    assert called.status_code == 200, called.text
    assert (called.json()["ticket_code"], called.json()["status"]) == ("A-001", "LLAMADO")
    assert "START" in called.json()["allowed_actions"]

    # Iniciar y finalizar
    clock.advance(minutes=2)
    started = client.post(api(f"/appointments/{a['public_id']}/start"), json={}, headers=operator.headers)
    assert started.json()["status"] == "EN_ATENCION"
    clock.advance(minutes=12)
    finished = client.post(api(f"/appointments/{a['public_id']}/finish"), json={}, headers=operator.headers)
    assert finished.json()["status"] == "ATENDIDO"

    board = queue(client, operator, alz)
    counts = board["counts"]
    assert (counts["attended"], counts["waiting"], counts["available"]) == (1, 1, 18)  # atendido sigue ocupando cupo

    # Trazabilidad: línea de tiempo completa
    events = client.get(api(f"/appointments/{a['public_id']}/events"), headers=operator.headers).json()
    assert [e["action"] for e in events] == ["REGISTER", "CALL", "START", "FINISH"]
    assert all(e["user_name"] for e in events)

    # Notificaciones encoladas (outbox): registro y llamado
    notes = client.get(api(f"/appointments/{a['public_id']}/notifications"), headers=operator.headers).json()
    assert {n["template_code"] for n in notes} == {"APPT_REGISTERED", "APPT_CALLED"}
    assert all(n["recipient_masked"] == "t***@pj.gob.pe" for n in notes)


def test_caso_1_capacity_reached(
    client: TestClient,
    operator: Actor,
    make_user: Callable[..., Actor],
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
) -> None:
    alz = site_id(db)
    set_capacity(client, make_user("SUPERVISOR"), alz, clock.today(), 2)
    assert register(client, operator, alz, make_worker()).status_code == 201
    assert register(client, operator, alz, make_worker()).status_code == 201
    third = register(client, operator, alz, make_worker())
    assert third.status_code == 409
    assert third.json() | {"request_id": None} == {
        "success": False,
        "code": "CAPACITY_REACHED",
        "message": CAPACITY_MESSAGE,
        "details": None,
        "request_id": None,
    }
    availability = client.get(api(f"/sites/{alz}/availability"), headers=operator.headers).json()
    assert (availability["available"], availability["can_register"], availability["blocker_code"]) == (
        0,
        False,
        "CAPACITY_REACHED",
    )


def test_caso_2_cancellation_releases_slot(
    client: TestClient,
    operator: Actor,
    make_user: Callable[..., Actor],
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
) -> None:
    alz = site_id(db)
    set_capacity(client, make_user("SUPERVISOR"), alz, clock.today(), 1)
    first = register(client, operator, alz, make_worker()).json()
    assert register(client, operator, alz, make_worker()).json()["code"] == "CAPACITY_REACHED"

    url = api(f"/appointments/{first['public_id']}/cancel")
    assert client.post(url, json={}, headers=operator.headers).json()["code"] == "REASON_REQUIRED"
    other = reason_id(client, operator, "CANCEL", "OTRO")
    assert client.post(url, json={"reason_id": other}, headers=operator.headers).json()["code"] == "NOTE_REQUIRED"
    wrong_type = reason_id(client, operator, "VOID")
    assert client.post(url, json={"reason_id": wrong_type}, headers=operator.headers).json()["code"] == "REASON_INVALID"

    cancel = client.post(
        url,
        json={
            "reason_id": reason_id(client, operator, "CANCEL", "ATENCION_EXTERNA"),
            "note": "Se atenderá en la clínica",
        },
        headers=operator.headers,
    )
    assert cancel.status_code == 200
    body = cancel.json()
    assert (body["status"], body["close_reason"]["code"]) == ("CANCELADO", "ATENCION_EXTERNA")
    assert body["allowed_actions"] == []

    again = register(client, operator, alz, make_worker())  # el cupo quedó libre
    assert (again.status_code, again.json()["ticket_code"]) == (201, "A-002")  # el número no se reutiliza


def test_caso_3_no_show_after_tolerance(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session, clock: FixedClock
) -> None:
    alz = site_id(db)
    appt = register(client, operator, alz, make_worker()).json()
    client.post(api(f"/sites/{alz}/queue/call-next"), headers=operator.headers)
    url = api(f"/appointments/{appt['public_id']}/no-show")

    early = client.post(url, json={}, headers=operator.headers)
    assert early.json()["code"] == "TOLERANCE_NOT_ELAPSED"
    assert early.json()["details"]["seconds_remaining"] == 600

    clock.advance(minutes=10)
    board = queue(client, operator, alz)
    assert [i["code"] for i in board["incidents"]] == ["TOLERANCE_EXPIRED"]
    done = client.post(url, json={}, headers=operator.headers)  # motivo por defecto
    assert done.status_code == 200
    assert (done.json()["status"], done.json()["close_reason"]["code"]) == ("NO_PRESENTADO", "NO_ACUDIO")
    assert queue(client, operator, alz)["counts"]["available"] == 20


def test_caso_4_concurrent_last_slot_through_api(
    app: FastAPI,
    operator: Actor,
    make_user: Callable[..., Actor],
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
    client: TestClient,
) -> None:
    alz = site_id(db)
    set_capacity(client, make_user("SUPERVISOR"), alz, clock.today(), 1)
    second_operator = make_user("OPERATOR")
    actors, dnis = [operator, second_operator] * 3, [make_worker() for _ in range(6)]
    barrier, results = threading.Barrier(6), [0] * 6

    def attempt(i: int) -> None:
        with TestClient(app, raise_server_exceptions=False) as local:
            barrier.wait()
            results[i] = register(local, actors[i], alz, dnis[i]).status_code

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert sorted(results) == [201, 409, 409, 409, 409, 409]


def test_caso_7_worker_not_eligible(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    alz = site_id(db)
    cases = {
        make_worker(covered=False): "WORKER_NOT_ELIGIBLE",
        make_worker(active=False): "WORKER_INACTIVE",
        "09999999": "WORKER_NOT_FOUND",
        "1234": "VALIDATION_ERROR",
        "12345A78": "INVALID_DOCUMENT",
    }
    for dni, code in cases.items():
        response = register(client, operator, alz, dni)
        assert response.json()["code"] == code, dni
    lookup = client.get(api("/workers/eligibility"), params={"document_number": "09999999"}, headers=operator.headers)
    assert (lookup.json()["found"], lookup.json()["eligible"], lookup.json()["code"]) == (
        False,
        False,
        "WORKER_NOT_FOUND",
    )


def test_dni_with_lost_leading_zero_is_normalized(
    client: TestClient, operator: Actor, make_worker: Callable[..., str]
) -> None:
    dni = make_worker()
    lookup = client.get(api("/workers/eligibility"), params={"document_number": f" {dni} "}, headers=operator.headers)
    assert lookup.json()["document_number"] == dni


def test_one_active_appointment_per_worker_per_day(
    client: TestClient, operator: Actor, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    dni = make_worker()
    assert register(client, operator, site_id(db), dni).status_code == 201
    again = register(client, operator, site_id(db), dni)
    assert (again.status_code, again.json()["code"]) == (409, "WORKER_ALREADY_HAS_APPOINTMENT")
    assert "A-001" in again.json()["message"]
    both = make_user("SUPERVISOR", sites=("ALZ", "BAR"))
    other_site = register(client, both, site_id(db, "BAR"), dni)
    assert other_site.json()["code"] == "WORKER_ALREADY_HAS_APPOINTMENT"


def test_no_show_cannot_reregister_by_default(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session, clock: FixedClock
) -> None:
    alz, dni = site_id(db), make_worker()
    appt = register(client, operator, alz, dni).json()
    client.post(api(f"/appointments/{appt['public_id']}/call"), json={}, headers=operator.headers)
    clock.advance(minutes=11)
    client.post(api(f"/appointments/{appt['public_id']}/no-show"), json={}, headers=operator.headers)
    assert register(client, operator, alz, dni).json()["code"] == "REREGISTER_NOT_ALLOWED"


def test_registration_window_and_closures(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session, clock: FixedClock
) -> None:
    alz = site_id(db)
    clock.set(dt.datetime.combine(clock.today(), dt.time(17, 0), tzinfo=INSTITUTION_TZ))
    operator = make_user("OPERATOR")
    assert register(client, operator, alz, make_worker()).json()["code"] == "REGISTRATION_WINDOW_CLOSED"

    supervisor = make_user("SUPERVISOR")
    tomorrow = clock.today() + dt.timedelta(days=5000)  # fecha aislada de los días de otras pruebas
    closure = client.post(
        api(f"/sites/{alz}/closures"),
        headers=supervisor.headers,
        json={"closure_date": tomorrow.isoformat(), "reason": "Feriado institucional"},
    )
    assert closure.status_code == 201
    clock.set(dt.datetime.combine(tomorrow, dt.time(9, 0), tzinfo=INSTITUTION_TZ))
    operator = make_user("OPERATOR")
    assert register(client, operator, alz, make_worker()).json()["code"] == "SITE_CLOSED_ON_DATE"


def test_optimistic_concurrency_and_invalid_transitions(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    created = register(client, operator, site_id(db), make_worker())
    assert created.status_code == 201, created.text
    appt = created.json()
    url = api(f"/appointments/{appt['public_id']}")
    finish = client.post(f"{url}/finish", json={}, headers=operator.headers)
    assert (finish.status_code, finish.json()["code"]) == (409, "INVALID_TRANSITION")

    called = client.post(f"{url}/call", json={"version": appt["version"]}, headers=operator.headers).json()
    stale = client.post(f"{url}/start", json={"version": appt["version"]}, headers=operator.headers)
    assert (stale.status_code, stale.json()["code"]) == (409, "APPOINTMENT_CHANGED")
    ok = client.post(f"{url}/start", json={"version": called["version"]}, headers=operator.headers)
    assert ok.json()["status"] == "EN_ATENCION"


def test_only_one_in_service_per_site_by_default(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    alz = site_id(db)
    first = register(client, operator, alz, make_worker()).json()
    second = register(client, operator, alz, make_worker()).json()
    for appt in (first, second):
        client.post(api(f"/appointments/{appt['public_id']}/call"), json={}, headers=operator.headers)
    assert (
        client.post(api(f"/appointments/{first['public_id']}/start"), json={}, headers=operator.headers).status_code
        == 200
    )
    blocked = client.post(api(f"/appointments/{second['public_id']}/start"), json={}, headers=operator.headers)
    assert blocked.json()["code"] == "MAX_IN_SERVICE_REACHED"


def test_requeue_keeps_order(client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session) -> None:
    alz = site_id(db)
    a = register(client, operator, alz, make_worker()).json()
    register(client, operator, alz, make_worker())
    client.post(api(f"/sites/{alz}/queue/call-next"), headers=operator.headers)
    back = client.post(api(f"/appointments/{a['public_id']}/requeue"), json={}, headers=operator.headers)
    assert back.json()["status"] == "EN_ESPERA"
    assert queue(client, operator, alz)["next_ticket_code"] == "A-001"  # conserva su lugar
    assert client.post(api(f"/sites/{alz}/queue/call-next"), headers=operator.headers).json()["call_count"] == 2


def test_call_next_on_empty_queue(client: TestClient, operator: Actor, db: Session) -> None:
    response = client.post(api(f"/sites/{site_id(db)}/queue/call-next"), headers=operator.headers)
    assert response.json()["code"] == "QUEUE_EMPTY"


def test_public_ticket_status(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    alz = site_id(db)
    register(client, operator, alz, make_worker())
    dni = make_worker()
    appt = register(client, operator, alz, dni).json()

    ok = client.get(api("/public/ticket-status"), params={"document_number": dni, "ticket_code": appt["ticket_code"]})
    assert ok.status_code == 200
    body = ok.json()
    assert (body["position"], body["people_ahead"], body["worker_name"]) == (2, 1, "A*** R***")
    assert "document_number" not in body  # no expone datos adicionales

    for params in (
        {"document_number": dni, "ticket_code": "A-999"},
        {"document_number": "09999999", "ticket_code": appt["ticket_code"]},
    ):
        wrong = client.get(api("/public/ticket-status"), params=params)
        assert (wrong.status_code, wrong.json()["code"]) == (404, "PUBLIC_TICKET_NOT_FOUND")
