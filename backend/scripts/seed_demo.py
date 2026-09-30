"""Datos de DEMOSTRACIÓN / capacitación (nunca en producción).

Crea usuarios de ejemplo, ~40 trabajadores ficticios y una jornada simulada (cola con
atenciones en todos los estados). Opera a través de la propia API, por lo que todo queda
auditado exactamente como en el uso real.

Uso:
    python -m scripts.seed_demo                 # base configurada en DATABASE_URL
    python -m scripts.seed_demo --test-db       # base de pruebas
    python -m scripts.seed_demo --date 2026-09-29

Luego, para ver la jornada "en curso", inicie el backend con el reloj desplazado:
    set DEV_CLOCK_START=2026-09-29T10:30:00-05:00
"""

import argparse
import datetime as dt
import random
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

import app.modules.registry  # noqa: F401
from app.core.clock import INSTITUTION_TZ, FixedClock
from app.core.config import API_PREFIX, get_settings
from app.core.ratelimit import limiter
from app.core.security import hash_password
from app.main import create_app
from app.modules.sites.models import Site
from app.modules.users.models import AppUser, Role
from app.modules.workers.models import Department, Insurer, Worker, WorkerCoverage
from app.shared.text import normalize_key

DEMO_PASSWORD = "Demo-Topico-2026"
USERS = [
    ("admin.demo", "Administración del Sistema (demo)", "ADMIN", ("ALZ", "BAR")),
    ("supervisor.demo", "Rosa Villanueva Paredes", "SUPERVISOR", ("ALZ", "BAR")),
    ("encargada.alz", "Carmen Quispe Huamán", "OPERATOR", ("ALZ",)),
    ("encargada.bar", "Lucía Ramos Mendoza", "OPERATOR", ("BAR",)),
    ("auditor.demo", "Jorge Salazar Ríos", "AUDITOR", ("ALZ", "BAR")),
]
FIRST = [
    "JUAN CARLOS",
    "MARÍA ELENA",
    "LUIS ALBERTO",
    "ROSA MARÍA",
    "JOSÉ ANTONIO",
    "ANA LUCÍA",
    "CARLOS ENRIQUE",
    "GLADYS",
    "MIGUEL ÁNGEL",
    "PATRICIA",
    "JORGE LUIS",
    "CARMEN ROSA",
    "VÍCTOR HUGO",
    "SUSANA",
    "RICARDO",
    "LILIANA",
    "FERNANDO",
    "YOLANDA",
    "PEDRO PABLO",
    "MILAGROS",
]
SURNAMES = [
    "QUISPE",
    "FLORES",
    "SÁNCHEZ",
    "RODRÍGUEZ",
    "GARCÍA",
    "HUAMÁN",
    "MENDOZA",
    "RAMÍREZ",
    "TORRES",
    "CHÁVEZ",
    "VARGAS",
    "CASTILLO",
    "ROJAS",
    "GUTIÉRREZ",
    "PAREDES",
    "ESPINOZA",
    "SALAZAR",
    "CÓRDOVA",
    "VILLANUEVA",
    "LEÓN",
]
DEPARTMENTS = [
    "1° JUZGADO CIVIL DE LIMA",
    "3° JUZGADO DE FAMILIA",
    "SALA LABORAL PERMANENTE",
    "MESA DE PARTES ÚNICA",
    "GERENCIA DE ADMINISTRACIÓN DISTRITAL",
    "OFICINA DE IMAGEN INSTITUCIONAL",
    "2° SALA PENAL DE APELACIONES",
    "CENTRO DE DISTRIBUCIÓN GENERAL",
    "UNIDAD DE PLANEAMIENTO Y DESARROLLO",
    "ARCHIVO CENTRAL",
]


def seed_reference(session_factory: object, rng: random.Random) -> list[str]:
    with session_factory() as s:  # type: ignore[operator]
        for username, full_name, role, sites in USERS:
            if s.scalar(select(AppUser.id).where(AppUser.username == username)):
                continue
            user = AppUser(
                username=username,
                full_name=full_name,
                password_hash=hash_password(DEMO_PASSWORD),
                auth_provider="LOCAL",
                must_change_password=False,
                is_active=True,
                failed_login_attempts=0,
            )
            user.roles = list(s.scalars(select(Role).where(Role.code == role)))
            user.sites = list(s.scalars(select(Site).where(Site.code.in_(sites))))
            s.add(user)
        for name in DEPARTMENTS:
            s.execute(
                insert(Department).values(name=name, normalized_name=normalize_key(name)).on_conflict_do_nothing()
            )
        s.flush()
        departments = list(s.scalars(select(Department).where(Department.name.in_(DEPARTMENTS))))
        rimac = s.scalar(select(Insurer).where(Insurer.code == "RIMAC"))
        assert rimac is not None
        dnis = []
        for i in range(40):
            dni = f"{41_200_000 + i * 137:08d}"
            dnis.append(dni)
            if s.scalar(select(Worker.id).where(Worker.document_number == dni)):
                continue
            first, paternal, maternal = rng.choice(FIRST), rng.choice(SURNAMES), rng.choice(SURNAMES)
            email = None if i % 9 == 4 else f"{first.split()[0].lower()}.{normalize_key(paternal).lower()}{i}@pj.gob.pe"
            worker = Worker(
                document_type="DNI",
                document_number=dni,
                first_names=first,
                paternal_surname=paternal,
                maternal_surname=maternal,
                sex=rng.choice("FM"),
                institutional_email=email,
                phone=f"9{rng.randint(10_000_000, 99_999_999)}",
                department_id=rng.choice(departments).id,
                birth_date=dt.date(rng.randint(1965, 2000), rng.randint(1, 12), rng.randint(1, 28)),
            )
            s.add(worker)
            s.flush()
            if i not in (7, 23, 38):  # tres trabajadores sin cobertura vigente (para demostrar el rechazo)
                s.add(WorkerCoverage(worker_id=worker.id, insurer_id=rimac.id, valid_from=dt.date(2025, 1, 1)))
        s.commit()
    return dnis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-db", action="store_true")
    parser.add_argument("--date", type=dt.date.fromisoformat, default=None)
    args = parser.parse_args()

    settings = get_settings()
    if settings.is_production:
        print("seed_demo no puede ejecutarse en producción.", file=sys.stderr)
        return 1
    if args.test_db:
        settings = settings.model_copy(update={"database_url": settings.test_database_url})
    settings = settings.model_copy(
        update={"notifications_worker_enabled": False, "log_dir": None, "email_backend": "disabled"}
    )

    day = args.date or dt.datetime.now(INSTITUTION_TZ).date()
    clock = FixedClock(dt.datetime.combine(day, dt.time(8, 5), tzinfo=INSTITUTION_TZ))
    app = create_app(settings, clock=clock)
    limiter.enabled = False
    rng = random.Random(2026)  # noqa: S311 - datos ficticios reproducibles, no criptografía
    dnis = seed_reference(app.state.session_factory, rng)
    covered = [d for i, d in enumerate(dnis) if i not in (7, 23, 38)]

    client = TestClient(app)

    tokens: dict[str, tuple[dt.datetime, dict[str, str]]] = {}

    def login(username: str) -> dict[str, str]:
        """Inicia sesión solo si no hay token o está por vencer (el reloj simulado avanza)."""
        cached = tokens.get(username)
        if cached and clock.now() - cached[0] < dt.timedelta(minutes=12):
            return cached[1]
        r = client.post(f"{API_PREFIX}/auth/login", json={"username": username, "password": DEMO_PASSWORD})
        r.raise_for_status()
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        tokens[username] = (clock.now(), headers)
        return headers

    sites = {s["code"]: s["id"] for s in client.get(f"{API_PREFIX}/sites", headers=login("admin.demo")).json()}
    queue = client.get(f"{API_PREFIX}/sites/{sites['ALZ']}/queue", headers=login("encargada.alz")).json()
    if queue["counts"]["total"] > 0:
        print(f"La jornada del {day} ya tiene datos; no se generan atenciones nuevas.")
        return 0

    def reasons(username: str, type_: str) -> list[dict[str, object]]:
        return client.get(f"{API_PREFIX}/catalogs/reasons", params={"type": type_}, headers=login(username)).json()

    def act(username: str, appt: dict[str, object], action: str, **body: object) -> dict[str, object]:
        r = client.post(f"{API_PREFIX}/appointments/{appt['public_id']}/{action}", json=body, headers=login(username))
        r.raise_for_status()
        return r.json()

    registered = []
    for i, dni in enumerate(covered[:14]):
        clock.advance(minutes=rng.randint(2, 6))
        r = client.post(
            f"{API_PREFIX}/appointments",
            headers=login("encargada.alz"),
            json={"site_id": sites["ALZ"], "document_number": dni, "channel": "PHONE" if i % 3 else "WALK_IN"},
        )
        r.raise_for_status()
        registered.append(r.json())

    # Primeras atenciones del día: llamar → iniciar → finalizar
    for appt in registered[:4]:
        act("encargada.alz", appt, "call")
        clock.advance(minutes=3)
        act("encargada.alz", appt, "start")
        clock.advance(minutes=rng.randint(9, 14))
        act("encargada.alz", appt, "finish")
    cancel_reason = next(r for r in reasons("encargada.alz", "CANCEL") if r["code"] == "ATENCION_EXTERNA")
    act(
        "encargada.alz",
        registered[4],
        "cancel",
        reason_id=cancel_reason["id"],
        note="Se atenderá en la clínica por la tarde",
    )
    act("encargada.alz", registered[5], "call")
    clock.advance(minutes=11)
    act("encargada.alz", registered[5], "no-show")
    act("encargada.alz", registered[6], "call")
    clock.advance(minutes=2)
    act("encargada.alz", registered[6], "start")
    clock.advance(minutes=4)
    act("encargada.alz", registered[7], "call")

    for dni in covered[20:26]:
        client.post(
            f"{API_PREFIX}/appointments",
            headers=login("encargada.bar"),
            json={"site_id": sites["BAR"], "document_number": dni, "channel": "PHONE"},
        ).raise_for_status()

    print(f"Jornada de demostración generada para el {day:%d/%m/%Y} (hasta las {clock.local_now():%H:%M}).")
    print(f"Usuarios (contraseña: {DEMO_PASSWORD}): " + ", ".join(u[0] for u in USERS))
    print(f"DNI habilitado de ejemplo: {covered[30]} · DNI sin cobertura: {dnis[7]}")
    print(f"Para ver la jornada en curso: DEV_CLOCK_START={day.isoformat()}T{clock.local_now():%H:%M}:00-05:00")
    return 0


if __name__ == "__main__":
    sys.exit(main())
