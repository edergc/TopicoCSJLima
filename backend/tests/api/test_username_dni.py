"""El usuario de ingreso es el DNI: exactamente 8 dígitos 0-9 (admite ceros a la izquierda y a la derecha)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from .conftest import Actor, api


@pytest.mark.parametrize(
    "username", ["maria.lopez", "admin", "1234567", "123456789", "4567890A", "4567-890", "١٢٣٤٥٦٧٨"]
)
def test_new_user_must_be_eight_digit_dni(client: TestClient, make_user: Callable[..., Actor], username: str) -> None:
    admin = make_user("ADMIN")
    body = {"username": username, "full_name": "Persona de Prueba", "role_codes": ["OPERATOR"]}
    response = client.post(api("/admin/users"), json=body, headers=admin.headers)
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION_ERROR"), response.text


@pytest.mark.parametrize("username", ["00012345", "12345000"])
def test_dni_with_leading_or_trailing_zeros_is_accepted(
    client: TestClient, make_user: Callable[..., Actor], username: str
) -> None:
    admin = make_user("ADMIN")
    body = {"username": username, "full_name": "Persona de Prueba", "role_codes": ["OPERATOR"]}
    response = client.post(api("/admin/users"), json=body, headers=admin.headers)
    assert response.status_code == 201, response.text
    assert response.json()["username"] == username
