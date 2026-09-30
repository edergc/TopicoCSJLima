"""Importación de Excel: validación en staging, previsualización, confirmación y trazabilidad."""

import io
import itertools
from collections.abc import Callable

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.workers.models import Worker

from .conftest import Actor, api

_seq = itertools.count(1)


def make_xlsx(rows: list[list[object]], header: list[str] | None = None, title_rows: int = 1) -> bytes:
    wb = Workbook()
    ws = wb.active
    for _ in range(title_rows):  # filas de título antes del encabezado (común en reportes institucionales)
        ws.append(["RELACIÓN DE TRABAJADORES CON EPS RÍMAC"])
    ws.append(
        header or ["N° DNI", "APELLIDO PATERNO", "APELLIDO MATERNO", "NOMBRES", "SEXO", "CORREO", "DEPENDENCIA", "EDAD"]
    )
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, admin: Actor, content: bytes, name: str = "trabajadores.xlsx") -> object:
    return client.post(
        api("/imports"),
        files={"file": (name, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin.headers,
    )


def unique_dnis(n: int) -> list[str]:
    base = 60_000_000 + next(_seq) * 100
    return [f"{base + i:08d}" for i in range(n)]


def test_full_import_flow(
    client: TestClient, make_user: Callable[..., Actor], make_worker: Callable[..., str], db: Session
) -> None:
    admin = make_user("ADMIN", sites=("ALZ", "BAR"))
    existing = make_worker(covered=False)  # existe, sin cobertura vigente → UPDATE
    d1, d2 = unique_dnis(2)
    lost_zero = "07" + d1[2:]  # DNI con cero inicial; Excel lo guarda como número de 7 dígitos
    content = make_xlsx(
        [
            [int(lost_zero), "PÉREZ", "QUISPE", "Juan Carlos", "M", "jperez@pj.gob.pe", "1° Juzgado Civil", 40],
            [d2, "LÓPEZ", None, "María", "F", "correo-malo", "Sala Laboral", None],
            [existing, "ROJAS", "VEGA", "ANA MARIA", "F", "trabajador@pj.gob.pe", "Sala Laboral", None],
            [d2, "LÓPEZ", None, "María", "F", None, None, None],  # duplicado en archivo
            ["12AB", "X", "Y", "Z", None, None, None, None],  # DNI inválido
            [None, None, None, None, None, None, None, None],  # fila vacía: se ignora
        ]
    )
    response = upload(client, admin, content)
    assert response.status_code == 201, response.text
    batch = response.json()
    assert batch["status"] == "VALIDATED"
    counts = {k: batch[k] for k in ("total_rows", "new_count", "update_count", "error_count", "duplicate_count")}
    assert counts == {"total_rows": 5, "new_count": 2, "update_count": 1, "error_count": 1, "duplicate_count": 1}
    assert "EDAD" not in batch["column_mapping"]["ignored"]

    rows = client.get(api(f"/imports/{batch['public_id']}/rows"), headers=admin.headers).json()["items"]
    first = rows[0]
    assert first["normalized"]["document_number"] == lost_zero
    assert any("ceros iniciales" in w for w in first["warnings"])
    assert any("Correo inválido" in w for w in rows[1]["warnings"])
    assert rows[2]["changes"]["coverage"] == ["SIN COBERTURA", "VIGENTE"]
    assert rows[4]["outcome"] == "ERROR"

    # Nada se incorporó todavía (staging)
    assert db.scalar(select(Worker).where(Worker.document_number == lost_zero)) is None

    csv_report = client.get(api(f"/imports/{batch['public_id']}/errors.csv"), headers=admin.headers)
    assert "DNI inválido" in csv_report.text

    confirmed = client.post(api(f"/imports/{batch['public_id']}/confirm"), json={}, headers=admin.headers)
    assert confirmed.json()["status"] == "CONFIRMED"
    worker = db.scalar(select(Worker).where(Worker.document_number == lost_zero))
    assert worker is not None
    assert (worker.paternal_surname, worker.first_names, worker.department.name) == (
        "PÉREZ",
        "JUAN CARLOS",
        "1° JUZGADO CIVIL",
    )
    assert worker.source_import_id is not None

    # Ya habilitados para registrar atención
    for dni in (lost_zero, existing):
        lookup = client.get(
            api("/workers/eligibility"), params={"document_number": dni}, headers=make_user("OPERATOR").headers
        )
        assert lookup.json()["eligible"] is True

    # El mismo archivo no puede importarse dos veces
    again = upload(client, admin, content)
    assert (again.status_code, again.json()["code"]) == (409, "IMPORT_ALREADY_CONFIRMED")


def test_invalid_files_are_rejected(client: TestClient, make_user: Callable[..., Actor]) -> None:
    admin = make_user("ADMIN")
    assert upload(client, admin, b"no es excel", "datos.xlsx").json()["code"] == "IMPORT_FILE_INVALID"
    assert upload(client, admin, b"a,b", "datos.csv").json()["code"] == "IMPORT_FILE_INVALID"
    no_dni = make_xlsx([["X", "Y"]], header=["NOMBRES", "APELLIDO PATERNO"])
    assert upload(client, admin, no_dni).json()["code"] == "IMPORT_COLUMNS_MISSING"
    only_header = make_xlsx([])
    assert upload(client, admin, only_header).json()["code"] == "IMPORT_EMPTY"


def test_combined_name_column_and_discard(client: TestClient, make_user: Callable[..., Actor]) -> None:
    admin = make_user("ADMIN")
    (dni,) = unique_dnis(1)
    content = make_xlsx([[dni, "GARCÍA TORRES, Luis Alberto"]], header=["DNI", "APELLIDOS Y NOMBRES"], title_rows=0)
    batch = upload(client, admin, content).json()
    assert batch["new_count"] == 1
    row = client.get(api(f"/imports/{batch['public_id']}/rows"), headers=admin.headers).json()["items"][0]
    assert (
        row["normalized"]["paternal_surname"],
        row["normalized"]["maternal_surname"],
        row["normalized"]["first_names"],
    ) == ("GARCÍA", "TORRES", "LUIS ALBERTO")
    discarded = client.post(api(f"/imports/{batch['public_id']}/discard"), headers=admin.headers)
    assert discarded.json()["status"] == "DISCARDED"
    confirm = client.post(api(f"/imports/{batch['public_id']}/confirm"), json={}, headers=admin.headers)
    assert confirm.json()["code"] == "IMPORT_INVALID_STATE"


def test_operator_cannot_import(client: TestClient, operator: Actor) -> None:
    assert upload(client, operator, make_xlsx([])).status_code == 403
