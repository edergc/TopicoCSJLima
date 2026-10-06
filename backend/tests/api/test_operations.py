"""Paquete operativo: horario/ausencias de médicos, pausa, cierre del día, panel, calificación y mensajes."""

import datetime as dt
import re
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.modules.notifications.models import Notification
from app.modules.ratings.models import ServiceRating
from app.modules.users.models import AppUser

from .conftest import Actor, api, register, site_id

WEEK = [{"weekday": d, "block": "AM", "start_time": "08:00", "end_time": "13:00"} for d in range(1, 6)]


@pytest.fixture
def site(client: TestClient, make_user: Callable[..., Actor], request: pytest.FixtureRequest) -> str:
    """Sede propia por prueba (código único) para no interferir con ALZ/BAR."""
    code = "OP" + "".join(chr(65 + int(c)) for c in f"{abs(hash(request.node.name)) % 10**6:06d}")
    admin = make_user("ADMIN", sites=("ALZ",))
    body = {"code": code, "name": f"Sede {code}", "short_name": code, "ticket_prefix": code[-3:], "blocks": WEEK}
    response = client.post(api("/sites"), json=body, headers=admin.headers)
    assert response.status_code == 201, response.text
    return code


def test_doctor_schedule_absence_and_capacity(
    client: TestClient,
    make_user: Callable[..., Actor],
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
    site: str,
) -> None:
    sid = site_id(db, site)
    supervisor = make_user("SUPERVISOR", sites=(site,))
    operator = make_user("OPERATOR", sites=(site,))
    url = api(f"/sites/{sid}/doctors")
    weekday = clock.today().isoweekday()
    a = client.post(url, json={"full_name": "Dra. Mañana"}, headers=supervisor.headers).json()
    b = client.post(url, json={"full_name": "Dr. Media Mañana"}, headers=supervisor.headers).json()

    # Horarios: A 08–10 (2 h) y B 10–12 (2 h) → 240 min / 15 = 16 cupos (la sede configura 20)
    sched_a = client.put(
        f"{url}/{a['id']}/schedule",
        json={"blocks": [{"weekday": weekday, "start_time": "08:00", "end_time": "10:00"}]},
        headers=supervisor.headers,
    )
    assert sched_a.status_code == 200, sched_a.text
    assert sched_a.json()["on_duty_now"] is True  # el reloj de prueba marca las 09:00
    overlap = client.put(
        f"{url}/{b['id']}/schedule",
        json={
            "blocks": [
                {"weekday": weekday, "start_time": "10:00", "end_time": "12:00"},
                {"weekday": weekday, "start_time": "11:00", "end_time": "12:30"},
            ]
        },
        headers=supervisor.headers,
    )
    assert overlap.json()["code"] == "SCHEDULE_OVERLAP_DOCTOR"
    client.put(
        f"{url}/{b['id']}/schedule",
        json={"blocks": [{"weekday": weekday, "start_time": "10:00", "end_time": "12:00"}]},
        headers=supervisor.headers,
    )
    availability = api(f"/sites/{sid}/availability")
    assert client.get(availability, headers=operator.headers).json()["capacity"] == 16

    # Ausencia de B hoy → 8 cupos; B no puede asignarse
    today = clock.today().isoformat()
    absent = client.post(
        f"{url}/{b['id']}/absences",
        json={"date_from": today, "date_to": today, "reason": "Capacitación"},
        headers=supervisor.headers,
    ).json()
    assert (absent["present_today"], absent["absence_reason"]) == (False, "Capacitación")
    assert client.get(availability, headers=operator.headers).json()["capacity"] == 8

    # La sede abre el día con 8 cupos; al iniciar se asigna sola la médica de turno (A)
    appt = register(client, operator, sid, make_worker()).json()
    assert client.get(availability, headers=operator.headers).json()["capacity"] == 8
    client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers)
    wrong = client.post(
        api(f"/appointments/{appt['public_id']}/start"), json={"doctor_id": b["id"]}, headers=operator.headers
    )
    assert wrong.json()["code"] == "DOCTOR_INVALID"
    started = client.post(api(f"/appointments/{appt['public_id']}/start"), json={}, headers=operator.headers).json()
    assert started["doctor_name"] == "Dra. Mañana"

    # Al quitar la ausencia, el día abierto recupera la capacidad calculada
    removed = client.delete(
        f"{url}/{b['id']}/absences/{absent['upcoming_absences'][0]['id']}", headers=supervisor.headers
    )
    assert removed.json()["present_today"] is True
    assert client.get(availability, headers=operator.headers).json()["capacity"] == 16


def test_pause_shifts_estimates_and_call_resumes(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session, site: str
) -> None:
    sid = site_id(db, site)
    operator = make_user("OPERATOR", sites=(site,))
    for _ in range(2):
        register(client, operator, sid, make_worker())
    paused = client.post(
        api(f"/sites/{sid}/pause"), json={"reason": "Refrigerio", "minutes": 60}, headers=operator.headers
    )
    assert paused.status_code == 201, paused.text
    resume_at = paused.json()["resume_at"]
    again = client.post(api(f"/sites/{sid}/pause"), json={"reason": "Otra", "minutes": 10}, headers=operator.headers)
    assert again.json()["code"] == "SITE_ALREADY_PAUSED"

    board = client.get(api(f"/sites/{sid}/queue"), headers=operator.headers).json()
    assert board["pause"]["reason"] == "Refrigerio"
    assert all(a["estimated_at"] >= resume_at for a in board["waiting"])  # ISO UTC comparables
    display = client.get(api(f"/public/display/{site}")).json()
    assert (display["pause_reason"], display["pause_resume_at"]) == ("Refrigerio", resume_at)

    # Llamar termina la pausa automáticamente
    client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers)
    assert client.get(api(f"/sites/{sid}/queue"), headers=operator.headers).json()["pause"] is None
    assert client.post(api(f"/sites/{sid}/resume"), headers=operator.headers).json()["code"] == "SITE_NOT_PAUSED"


def test_close_day_marks_pending_and_sends_summary(
    client: TestClient,
    app: FastAPI,
    make_user: Callable[..., Actor],
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
    site: str,
) -> None:
    sid = site_id(db, site)
    operator = make_user("OPERATOR", sites=(site,))
    supervisor = make_user("SUPERVISOR", sites=(site,))
    db.execute(update(AppUser).where(AppUser.username == supervisor.username).values(email="supervision@pj.gob.pe"))
    db.commit()
    attended, called, waiting = (register(client, operator, sid, make_worker()).json() for _ in range(3))
    client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers)
    client.post(api(f"/appointments/{attended['public_id']}/start"), json={}, headers=operator.headers)

    close_url = api(f"/sites/{sid}/service-days/{clock.today().isoformat()}/close")
    assert client.post(close_url, headers=operator.headers).status_code == 403  # requiere service_day:close
    assert client.post(close_url, headers=supervisor.headers).json()["code"] == "DAY_HAS_IN_SERVICE"
    client.post(api(f"/appointments/{attended['public_id']}/finish"), json={}, headers=operator.headers)
    client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers)  # "called" queda llamado

    result = client.post(close_url, headers=supervisor.headers)
    assert result.status_code == 200, result.text
    assert result.json() | {"service_date": None} == {
        "service_date": None,
        "marked_no_show": 2,
        "attended": 1,
        "no_show": 2,
        "cancelled": 0,
        "summary_sent_to": 1,
    }
    for appt in (called, waiting):
        body = client.get(api(f"/appointments/{appt['public_id']}"), headers=supervisor.headers).json()
        assert (body["status"], body["close_reason"]["code"]) == ("NO_PRESENTADO", "CIERRE_JORNADA")
    assert register(client, operator, sid, make_worker()).json()["code"] == "SERVICE_DAY_CLOSED"
    assert client.post(close_url, headers=supervisor.headers).json()["code"] == "SERVICE_DAY_CLOSED"

    summary = db.scalar(select(Notification).where(Notification.recipient == "supervision@pj.gob.pe"))
    assert summary is not None
    assert (summary.template_code, summary.attachment_type) == ("DAY_SUMMARY", "application/pdf")
    assert summary.attachment_data is not None
    assert summary.attachment_data.startswith(b"%PDF")

    live = client.get(api("/dashboard/live"), headers=supervisor.headers).json()
    mine = next(s for s in live["sites"] if s["site_code"] == site)
    assert (mine["day_status"], mine["counts"]["attended"]) == ("CLOSED", 1)


def test_anonymous_rating_flow(
    client: TestClient,
    app: FastAPI,
    make_user: Callable[..., Actor],
    make_worker: Callable[..., str],
    db: Session,
    site: str,
) -> None:
    original = app.state.settings
    app.state.settings = original.model_copy(update={"public_app_url": "http://topico.local/consulta"})
    try:
        sid = site_id(db, site)
        operator = make_user("OPERATOR", sites=(site,))
        appt = register(client, operator, sid, make_worker()).json()
        client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers)
        client.post(api(f"/appointments/{appt['public_id']}/start"), json={}, headers=operator.headers)
        client.post(api(f"/appointments/{appt['public_id']}/finish"), json={}, headers=operator.headers)
    finally:
        app.state.settings = original

    mail = db.scalar(
        select(Notification).where(Notification.template_code == "RATING_REQUEST").order_by(Notification.id.desc())
    )
    assert mail is not None
    assert mail.body_text
    match = re.search(r"http://topico\.local/calificar#([\w-]+)", mail.body_text)
    assert match, mail.body_text
    token = match.group(1)
    assert db.scalar(select(ServiceRating.token_hash).where(ServiceRating.site_id == sid)) != token  # solo el hash

    lookup = client.post(api("/public/rating/lookup"), json={"token": token}).json()
    assert (lookup["submitted"], lookup["expired"]) == (False, False)
    sent = client.post(
        api("/public/rating"), json={"token": token, "score": 5, "wait_score": 4, "comment": "Muy amables"}
    )
    assert sent.status_code == 204, sent.text
    twice = client.post(api("/public/rating"), json={"token": token, "score": 1})
    assert twice.json()["code"] == "RATING_ALREADY_SUBMITTED"
    assert client.post(api("/public/rating/lookup"), json={"token": "x" * 32}).json()["code"] == "RATING_NOT_FOUND"

    supervisor = make_user("SUPERVISOR", sites=(site,))
    rating = client.get(api("/reports/summary"), params={"site_id": sid}, headers=supervisor.headers).json()["rating"]
    assert (rating["count"], rating["avg_score"], rating["avg_wait_score"]) == (1, 5.0, 4.0)
    assert rating["comments"][0]["comment"] == "Muy amables"
    assert "worker" not in str(rating)
    assert "dni" not in str(rating).lower()


def test_display_messages_rotate_by_site(
    client: TestClient, make_user: Callable[..., Actor], db: Session, clock: FixedClock, site: str
) -> None:
    sid = site_id(db, site)
    supervisor = make_user("SUPERVISOR", sites=(site,))
    admin = make_user("ADMIN", sites=(site,))
    today = clock.today()
    url = api("/display-messages")
    own = client.post(
        url,
        json={"site_id": sid, "text": "Lávese las manos", "valid_from": today.isoformat()},
        headers=supervisor.headers,
    )
    assert own.status_code == 201, own.text
    glob = {"text": "Campaña de vacunación", "valid_from": today.isoformat(), "sort_order": 1}
    assert client.post(url, json=glob, headers=supervisor.headers).status_code == 403  # todas las sedes: site:manage
    assert client.post(url, json=glob, headers=admin.headers).status_code == 201
    future = {"site_id": sid, "text": "Mensaje futuro", "valid_from": (today + dt.timedelta(days=3)).isoformat()}
    client.post(url, json=future, headers=supervisor.headers)

    board = client.get(api(f"/public/display/{site}")).json()
    assert board["messages"][:2] == ["Lávese las manos", "Campaña de vacunación"]
    assert "Mensaje futuro" not in board["messages"]

    client.patch(f"{url}/{own.json()['id']}", json={"is_active": False}, headers=supervisor.headers)
    assert "Lávese las manos" not in client.get(api(f"/public/display/{site}")).json()["messages"]


@pytest.fixture(autouse=True)
def _deactivate_global_messages(db: Session) -> Iterator[None]:
    """Los mensajes globales afectan a todas las sedes: se desactivan al terminar cada prueba."""
    yield
    from app.modules.sites.models import DisplayMessage

    db.execute(update(DisplayMessage).where(DisplayMessage.site_id.is_(None)).values(is_active=False))
    db.commit()
