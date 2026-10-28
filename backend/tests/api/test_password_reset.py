"""Recuperación de contraseña por correo: enlace de un solo uso, con vencimiento y sin revelar usuarios."""

import re
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.modules.audit.models import AuditEvent
from app.modules.notifications.models import Notification
from app.modules.users.models import AppUser, PasswordReset, RefreshToken

from .conftest import Actor, api

NEW_PASSWORD = "NuevaClave2026"


@pytest.fixture
def public_url(app: FastAPI) -> Iterator[None]:
    original = app.state.settings
    app.state.settings = original.model_copy(update={"public_app_url": "http://topico.local/consulta"})
    try:
        yield
    finally:
        app.state.settings = original


def with_email(app: FastAPI, actor: Actor, email: str = "usuario@pj.gob.pe") -> None:
    with app.state.session_factory() as s:
        s.execute(update(AppUser).where(AppUser.public_id == actor.public_id).values(email=email))
        s.commit()


def request_link(client: TestClient, username: str) -> int:
    return client.post(api("/auth/password-reset/request"), json={"username": username}).status_code


def last_link(db: Session, email: str = "usuario@pj.gob.pe") -> str:
    mail = db.scalar(
        select(Notification)
        .where(Notification.template_code == "PASSWORD_RESET", Notification.recipient == email)
        .order_by(Notification.id.desc())
    )
    assert mail is not None
    assert mail.body_text
    match = re.search(r"http://topico\.local/recuperar-clave#([\w-]+)", mail.body_text)
    assert match, mail.body_text
    return match.group(1)


def confirm(client: TestClient, token: str, password: str = NEW_PASSWORD) -> object:
    return client.post(api("/auth/password-reset/confirm"), json={"token": token, "new_password": password})


@pytest.mark.usefixtures("public_url")
def test_reset_link_sets_new_password_once_and_closes_sessions(
    client: TestClient, app: FastAPI, make_user: Callable[..., Actor], db: Session, clock: FixedClock
) -> None:
    actor = make_user("OPERATOR", must_change=True)
    with_email(app, actor)
    assert request_link(client, actor.username.upper()) == 204
    token = last_link(db)
    assert db.scalar(select(PasswordReset.token_hash).where(PasswordReset.token_hash == token)) is None  # solo el hash

    weak = confirm(client, token, "corta")
    assert (weak.status_code, weak.json()["code"]) == (422, "PASSWORD_POLICY")
    assert confirm(client, token).status_code == 204

    again = confirm(client, token, "OtraClave2026")
    assert again.json()["code"] == "RESET_LINK_INVALID"
    assert (
        client.post(api("/auth/login"), json={"username": actor.username, "password": actor.password}).status_code
        == 401
    )
    login = client.post(api("/auth/login"), json={"username": actor.username, "password": NEW_PASSWORD})
    assert login.status_code == 200
    assert login.json()["user"]["must_change_password"] is False

    user_id = db.scalar(select(AppUser.id).where(AppUser.public_id == actor.public_id))
    reasons = set(db.scalars(select(RefreshToken.revoked_reason).where(RefreshToken.user_id == user_id)))
    assert "PASSWORD_CHANGED" in reasons  # la sesión anterior quedó cerrada
    actions = list(db.scalars(select(AuditEvent.action).where(AuditEvent.username == actor.username)))
    assert "PASSWORD_RESET_REQUEST" in actions
    assert "PASSWORD_RESET_CONFIRM" in actions


@pytest.mark.usefixtures("public_url")
def test_unknown_users_and_users_without_email_get_the_same_answer(
    client: TestClient, app: FastAPI, make_user: Callable[..., Actor], db: Session
) -> None:
    no_email = make_user("OPERATOR", login=False)
    assert request_link(client, "no.existe") == 204
    assert request_link(client, no_email.username) == 204
    assert (
        db.scalar(
            select(Notification.id).where(
                Notification.template_code == "PASSWORD_RESET", Notification.recipient.is_(None)
            )
        )
        is None
    )
    reasons = {
        e.username: e.reason
        for e in db.scalars(
            select(AuditEvent).where(AuditEvent.action == "PASSWORD_RESET_REQUEST", AuditEvent.result == "FAILURE")
        )
    }
    assert reasons["no.existe"] == "USER_NOT_FOUND"
    assert reasons[no_email.username] == "NO_EMAIL"


@pytest.mark.usefixtures("public_url")
def test_link_expires_and_a_new_request_invalidates_the_previous_one(
    client: TestClient, app: FastAPI, make_user: Callable[..., Actor], db: Session, clock: FixedClock
) -> None:
    actor = make_user("OPERATOR", login=False)
    with_email(app, actor, "vence@pj.gob.pe")
    request_link(client, actor.username)
    first = last_link(db, "vence@pj.gob.pe")

    request_link(client, actor.username)  # pedido repetido enseguida: no se envía otro correo
    assert last_link(db, "vence@pj.gob.pe") == first

    clock.advance(minutes=3)
    request_link(client, actor.username)
    second = last_link(db, "vence@pj.gob.pe")
    assert second != first
    assert confirm(client, first).json()["code"] == "RESET_LINK_INVALID"

    clock.advance(minutes=31)
    assert confirm(client, second).json()["code"] == "RESET_LINK_EXPIRED"


@pytest.mark.usefixtures("public_url")
def test_reset_unlocks_a_locked_account(
    client: TestClient, app: FastAPI, make_user: Callable[..., Actor], db: Session
) -> None:
    actor = make_user("OPERATOR", login=False)
    with_email(app, actor, "bloqueado@pj.gob.pe")
    for _ in range(5):
        client.post(api("/auth/login"), json={"username": actor.username, "password": "mala-clave-1"})
    request_link(client, actor.username)
    assert confirm(client, last_link(db, "bloqueado@pj.gob.pe")).status_code == 204
    login = client.post(api("/auth/login"), json={"username": actor.username, "password": NEW_PASSWORD})
    assert login.status_code == 200
