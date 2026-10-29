"""El DNI ingresado a mano debe ser exactamente 8 dígitos 0-9 (sin letras, sin completar ceros)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.shared.text import is_valid_dni, normalize_document

from .conftest import Actor, api, register, site_id

INVALID = ["1234567", "123456789", "4120438A", "ABCDEFGH", "4120-438", "١٢٣٤٥٦٧٨"]


@pytest.mark.parametrize("dni", INVALID)
def test_register_rejects_invalid_dni(client: TestClient, operator: Actor, db: Session, dni: str) -> None:
    response = register(client, operator, site_id(db), dni)
    assert response.status_code in (400, 422), response.text
    assert response.json()["code"] in ("INVALID_DOCUMENT", "VALIDATION_ERROR")


@pytest.mark.parametrize("dni", ["1234567", "4120438A", "123456789"])
def test_lookup_and_public_status_reject_invalid_dni(client: TestClient, operator: Actor, dni: str) -> None:
    lookup = client.get(api("/workers/eligibility"), params={"document_number": dni}, headers=operator.headers)
    assert lookup.status_code in (400, 422)
    public = client.get(api("/public/ticket-status"), params={"document_number": dni, "ticket_code": "A-001"})
    assert public.status_code in (404, 422)


def test_worker_creation_requires_eight_digits(client: TestClient, make_user: Callable[..., Actor]) -> None:
    admin = make_user("ADMIN")
    body = {"first_names": "ANA", "paternal_surname": "ROJAS", "coverage_valid_from": "2026-01-01"}
    for dni in ("1234567", "1234567A"):
        response = client.post(api("/workers"), json={**body, "document_number": dni}, headers=admin.headers)
        assert response.json()["code"] in ("INVALID_DOCUMENT", "VALIDATION_ERROR"), response.text


def test_excel_import_still_restores_lost_leading_zeros() -> None:
    # Excel convierte 01234567 en el número 1234567: la importación (y solo ella) completa el cero.
    assert normalize_document(1234567.0) == "01234567"
    assert is_valid_dni(normalize_document("1234567"))
    assert not is_valid_dni("١٢٣٤٥٦٧٨")
