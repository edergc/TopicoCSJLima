"""Prioridad explícita y auditable; identidad visual configurable."""

import zlib
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification
from app.modules.sites.models import SystemParameter

from .conftest import Actor, api, register, site_id

WEEK = [{"weekday": d, "block": "AM", "start_time": "08:00", "end_time": "13:00"} for d in range(1, 6)]


def _set_param(db: Session, key: str, value: object) -> None:
    db.execute(update(SystemParameter).where(SystemParameter.key == key).values(value=value))
    db.commit()


@pytest.fixture
def priority_on(db: Session) -> Iterator[None]:
    _set_param(db, "priority.enabled", True)
    _set_param(db, "priority.max_consecutive", 2)
    yield
    _set_param(db, "priority.enabled", False)
    _set_param(db, "priority.max_consecutive", 3)


@pytest.fixture
def site(client: TestClient, make_user: Callable[..., Actor], request: pytest.FixtureRequest) -> str:
    code = "PB" + "".join(chr(65 + int(c)) for c in f"{abs(hash(request.node.name)) % 10**6:06d}")
    admin = make_user("ADMIN", sites=("ALZ",))
    body = {"code": code, "name": f"Sede {code}", "short_name": code, "ticket_prefix": code[-3:], "blocks": WEEK}
    assert client.post(api("/sites"), json=body, headers=admin.headers).status_code == 201
    return code


def _priority_id(client: TestClient, actor: Actor, code: str) -> int:
    reasons = client.get(api("/catalogs/reasons"), params={"type": "PRIORITY"}, headers=actor.headers).json()
    return next(r["id"] for r in reasons if r["code"] == code)


def test_priority_is_disabled_by_default(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session, site: str
) -> None:
    operator = make_user("OPERATOR", sites=(site,))
    sid = site_id(db, site)
    reason = _priority_id(client, operator, "ADULTO_MAYOR")
    refused = register(client, operator, sid, make_worker(), priority_reason_id=reason)
    assert refused.json()["code"] == "PRIORITY_DISABLED"
    assert client.get(api(f"/sites/{sid}/queue"), headers=operator.headers).json()["priority_enabled"] is False


@pytest.mark.usefixtures("priority_on")
def test_priority_order_with_fairness_cap(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session, site: str
) -> None:
    operator = make_user("OPERATOR", sites=(site,))
    sid = site_id(db, site)
    elder = _priority_id(client, operator, "ADULTO_MAYOR")
    pregnant = _priority_id(client, operator, "GESTANTE")

    normal1 = register(client, operator, sid, make_worker()).json()
    normal2 = register(client, operator, sid, make_worker()).json()
    p1 = register(client, operator, sid, make_worker(), priority_reason_id=elder).json()
    p2 = register(client, operator, sid, make_worker(), priority_reason_id=pregnant).json()
    p3 = register(client, operator, sid, make_worker()).json()
    assert p1["priority_label"] == "Adulto mayor (60 años o más)"

    # Se asigna prioridad después del registro (auditado y en la línea de tiempo)
    set_p3 = client.post(
        api(f"/appointments/{p3['public_id']}/priority"), json={"reason_id": elder}, headers=operator.headers
    )
    assert set_p3.json()["priority_code"] == "ADULTO_MAYOR"
    events = client.get(api(f"/appointments/{p3['public_id']}/events"), headers=operator.headers).json()
    assert events[-1]["action"] == "PRIORITY"

    # Orden esperado con tope de 2 prioritarios seguidos: P1, P2, N1, P3, N2
    expected = [p1, p2, normal1, p3, normal2]
    queue = client.get(api(f"/sites/{sid}/queue"), headers=operator.headers).json()
    assert [a["ticket_code"] for a in queue["waiting"]] == [a["ticket_code"] for a in expected]
    called = []
    for _ in expected:
        a = client.post(api(f"/sites/{sid}/queue/call-next"), headers=operator.headers).json()
        called.append(a["ticket_code"])
        client.post(api(f"/appointments/{a['public_id']}/start"), json={}, headers=operator.headers)
        client.post(api(f"/appointments/{a['public_id']}/finish"), json={}, headers=operator.headers)
    assert called == [a["ticket_code"] for a in expected]

    # La pantalla de sala no revela la categoría de prioridad
    board = client.get(api(f"/public/display/{site}")).text
    assert "Adulto mayor" not in board
    assert "Gestante" not in board


@pytest.mark.usefixtures("priority_on")
def test_priority_can_be_removed_and_rejects_invalid(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session, site: str
) -> None:
    operator = make_user("OPERATOR", sites=(site,))
    sid = site_id(db, site)
    elder = _priority_id(client, operator, "ADULTO_MAYOR")
    appt = register(client, operator, sid, make_worker(), priority_reason_id=elder).json()
    removed = client.post(
        api(f"/appointments/{appt['public_id']}/priority"), json={"reason_id": None}, headers=operator.headers
    )
    assert removed.json()["priority_code"] is None
    cancel_reason = client.get(api("/catalogs/reasons"), params={"type": "CANCEL"}, headers=operator.headers).json()[0][
        "id"
    ]
    wrong = client.post(
        api(f"/appointments/{appt['public_id']}/priority"), json={"reason_id": cancel_reason}, headers=operator.headers
    )
    assert wrong.json()["code"] == "PRIORITY_INVALID"


def _png(color: tuple[int, int, int] = (122, 30, 44)) -> bytes:
    """PNG mínimo de 1×1 (sin dependencias)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return len(data).to_bytes(4, "big") + kind + data + zlib.crc32(kind + data).to_bytes(4, "big")

    raw = b"\x00" + bytes(color)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_branding_logo_color_pdf_and_email(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    admin = make_user("ADMIN")
    try:
        assert client.get(api("/public/branding/logo")).status_code == 404
        svg = client.put(
            api("/admin/branding/logo"),
            files={"file": ("x.svg", b"<svg onload='alert(1)'/>", "image/svg+xml")},
            headers=admin.headers,
        )
        assert svg.json()["code"] == "LOGO_INVALID"  # solo PNG/JPEG, validado por contenido
        operator = make_user("OPERATOR")
        assert (
            client.put(
                api("/admin/branding/logo"), files={"file": ("l.png", _png(), "image/png")}, headers=operator.headers
            ).status_code
            == 403
        )
        uploaded = client.put(
            api("/admin/branding/logo"), files={"file": ("l.png", _png(), "image/png")}, headers=admin.headers
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["logo_updated_at"]
        logo = client.get(api("/public/branding/logo"))
        assert (logo.status_code, logo.headers["content-type"]) == (200, "image/png")

        _set_param(db, "branding.primary_color", "#123456")
        assert client.get(api("/public/branding")).json()["primary_color"] == "#123456"
        _set_param(db, "branding.primary_color", "rojo")  # inválido → color por defecto
        assert client.get(api("/public/branding")).json()["primary_color"] == "#7a1e2c"

        # PDF con logo y correo con versión HTML de la marca
        supervisor = make_user("SUPERVISOR")
        pdf = client.get(api("/reports/export"), params={"format": "pdf"}, headers=supervisor.headers)
        assert pdf.content.startswith(b"%PDF")
        register(client, operator, site_id(db), make_worker())
        mail = db.scalar(
            select(Notification).where(Notification.template_code == "APPT_REGISTERED").order_by(Notification.id.desc())
        )
        assert mail is not None
        assert mail.body_html is not None
        assert "Corte Superior de Justicia de Lima" in mail.body_html
    finally:
        client.delete(api("/admin/branding/logo"), headers=admin.headers)
        _set_param(db, "branding.primary_color", "#7a1e2c")
    assert client.get(api("/public/branding")).json()["logo_updated_at"] is None
