"""Correo de registro: ticket digital (HTML con botón) y el ticket en PDF adjunto con QR."""

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification

from .conftest import Actor, register, site_id


def test_registration_email_carries_digital_ticket(
    client: TestClient, app: FastAPI, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    sid = site_id(db, "ALZ")
    operator = make_user("OPERATOR", sites=("ALZ",))
    dni = make_worker()
    original = app.state.settings
    app.state.settings = original.model_copy(update={"public_app_url": "http://topico.local/consulta"})
    try:
        appt = register(client, operator, sid, dni).json()
    finally:
        app.state.settings = original

    mail = db.scalar(
        select(Notification)
        .where(Notification.template_code == "APPT_REGISTERED", Notification.recipient.is_not(None))
        .order_by(Notification.id.desc())
    )
    assert mail is not None
    assert mail.status == "PENDING"
    code = appt["ticket_code"]
    link = f"http://topico.local/consulta#dni={dni}&amp;turno={code}"
    assert mail.body_html is not None
    assert code in mail.body_html
    assert "Ver mi turno en tiempo real" in mail.body_html
    assert link in mail.body_html
    assert mail.body_text is not None
    assert f"http://topico.local/consulta#dni={dni}&turno={code}" in mail.body_text
    assert mail.attachment_name == f"Turno-{code}.pdf"
    assert mail.attachment_type == "application/pdf"
    assert mail.attachment_data is not None
    assert mail.attachment_data.startswith(b"%PDF")
