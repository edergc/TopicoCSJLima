"""Autenticación: login, bloqueo, sesiones rotativas, cambio de contraseña, rate limiting."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.ratelimit import limiter
from app.modules.audit.models import AuditEvent
from app.modules.users.models import RefreshToken

from .conftest import PASSWORD, Actor, api

XHR = {"X-Requested-With": "XMLHttpRequest"}


def login(client: TestClient, username: str, password: str = PASSWORD) -> object:
    return client.post(api("/auth/login"), json={"username": username, "password": password})


def test_login_returns_token_profile_and_httponly_cookie(client: TestClient, make_user: Callable[..., Actor]) -> None:
    actor = make_user("OPERATOR", login=False)
    response = login(client, actor.username)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["user"]["roles"] == ["OPERATOR"]
    assert "appointment:create" in body["user"]["permissions"]
    assert [s["code"] for s in body["user"]["sites"]] == ["ALZ"]
    cookie = response.headers["set-cookie"]
    assert "topico_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "samesite=strict" in cookie.lower()
    assert "Path=/api/v1/auth" in cookie


def test_wrong_password_is_generic_and_audited(
    client: TestClient, make_user: Callable[..., Actor], db: Session
) -> None:
    actor = make_user("OPERATOR", login=False)
    response = login(client, actor.username, "incorrecta-123")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
    unknown = login(client, "no.existe", "incorrecta-123")
    assert unknown.json()["code"] == "INVALID_CREDENTIALS"  # no revela si el usuario existe
    events = db.scalars(select(AuditEvent).where(AuditEvent.username == actor.username, AuditEvent.action == "LOGIN"))
    assert [(e.result, e.reason) for e in events] == [("FAILURE", "BAD_PASSWORD")]


def test_account_locks_after_max_failed_attempts(
    client: TestClient, make_user: Callable[..., Actor], clock: FixedClock
) -> None:
    actor = make_user("OPERATOR", login=False)
    codes = [login(client, actor.username, "mala-clave-1").json()["code"] for _ in range(5)]
    assert codes[:4] == ["INVALID_CREDENTIALS"] * 4
    assert codes[4] == "ACCOUNT_LOCKED"
    # Aun con la contraseña correcta, sigue bloqueada...
    assert login(client, actor.username).json()["code"] == "ACCOUNT_LOCKED"
    # ...hasta que pasa el tiempo de bloqueo.
    clock.advance(minutes=16)
    assert login(client, actor.username).status_code == 200


def test_requests_without_valid_token_are_rejected(
    client: TestClient, make_user: Callable[..., Actor], clock: FixedClock
) -> None:
    assert client.get(api("/auth/me")).json()["code"] == "UNAUTHORIZED"
    assert client.get(api("/auth/me"), headers={"Authorization": "Bearer basura"}).json()["code"] == "TOKEN_INVALID"
    actor = make_user("OPERATOR")
    assert client.get(api("/auth/me"), headers=actor.headers).status_code == 200
    clock.advance(minutes=16)
    response = client.get(api("/auth/me"), headers=actor.headers)
    assert (response.status_code, response.json()["code"]) == (401, "TOKEN_EXPIRED")


def test_refresh_rotates_and_detects_reuse(
    client: TestClient, make_user: Callable[..., Actor], clock: FixedClock, db: Session
) -> None:
    actor = make_user("OPERATOR", login=False)
    login(client, actor.username)
    first_cookie = client.cookies.get("topico_refresh")

    assert client.post(api("/auth/refresh")).json()["code"] == "CSRF_CHECK_FAILED"  # sin cabecera XHR
    refreshed = client.post(api("/auth/refresh"), headers=XHR)
    assert refreshed.status_code == 200
    assert client.cookies.get("topico_refresh") != first_cookie

    # Reutilizar el token viejo (fuera del margen de gracia) revoca TODA la sesión.
    clock.advance(minutes=2)
    client.cookies.set("topico_refresh", first_cookie, path="/api/v1/auth")
    assert client.post(api("/auth/refresh"), headers=XHR).json()["code"] == "SESSION_EXPIRED"
    tokens = db.scalars(
        select(RefreshToken).join(RefreshToken.user).where(RefreshToken.revoked_reason == "REUSE_DETECTED")
    )
    assert any(t.user.username == actor.username for t in tokens)


def test_logout_revokes_refresh_token(client: TestClient, make_user: Callable[..., Actor]) -> None:
    actor = make_user("OPERATOR", login=False)
    login(client, actor.username)
    assert client.post(api("/auth/logout"), headers=XHR).status_code == 204
    assert client.post(api("/auth/refresh"), headers=XHR).json()["code"] == "SESSION_EXPIRED"


def test_password_change_required_blocks_operation(client: TestClient, make_user: Callable[..., Actor]) -> None:
    actor = make_user("OPERATOR", must_change=True)
    blocked = client.get(api("/sites"), headers=actor.headers)
    assert (blocked.status_code, blocked.json()["code"]) == (403, "PASSWORD_CHANGE_REQUIRED")
    assert client.get(api("/auth/me"), headers=actor.headers).json()["must_change_password"] is True

    weak = client.post(
        api("/auth/change-password"),
        headers=actor.headers,
        json={"current_password": PASSWORD, "new_password": "corta"},
    )
    assert weak.json()["code"] == "PASSWORD_POLICY"
    changed = client.post(
        api("/auth/change-password"),
        headers=actor.headers,
        json={"current_password": PASSWORD, "new_password": "NuevaClave-2026x"},
    )
    assert changed.status_code == 200
    headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert client.get(api("/sites"), headers=headers).status_code == 200


def test_login_is_rate_limited(client: TestClient) -> None:
    limiter.enabled = True
    try:
        limiter.reset()
        codes = [login(client, "rate.limit", "x").status_code for _ in range(11)]
    finally:
        limiter.enabled = False
    assert codes[-1] == 429
    assert set(codes[:10]) == {401}
