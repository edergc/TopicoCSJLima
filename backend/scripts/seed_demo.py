"""Datos de DEMOSTRACIÓN / capacitación (nunca en producción).

Crea usuarios de ejemplo, ~40 trabajadores ficticios y una jornada simulada (cola con
atenciones en todos los estados). Opera a través de la propia API, por lo que todo queda
auditado exactamente como en el uso real.

Uso:
    python -m scripts.seed_demo                 # base configurada en DATABASE_URL
    python -m scripts.seed_demo --test-db       # base de pruebas
    python -m scripts.seed_demo --date 2026-09-29
    python -m scripts.seed_demo --history-days 10            # + 10 días hábiles anteriores completos
    python -m scripts.seed_demo --now --allow-production     # instalación aún SIN datos reales

--allow-production solo se acepta si ningún usuario real registró atenciones (sistema en
preparación). Allí los trabajadores ficticios no tienen correo (podrían coincidir con personas
reales); solo el trabajador de prueba indicado con --test-email recibe notificaciones.

Luego, para ver la jornada "en curso", inicie el backend con el reloj desplazado:
    set DEV_CLOCK_START=2026-09-29T10:30:00-05:00
"""

import argparse
import datetime as dt
import random
import sys

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

import app.modules.registry  # noqa: F401
from app.core.clock import INSTITUTION_TZ, FixedClock
from app.core.config import API_PREFIX, get_settings
from app.core.ratelimit import limiter
from app.core.security import hash_password
from app.main import create_app
from app.modules.appointments.models import Appointment
from app.modules.sites.models import Site
from app.modules.users.models import AppUser, Role
from app.modules.workers.models import Department, Insurer, Worker, WorkerCoverage
from app.shared.text import normalize_key

DEMO_PASSWORD = "Demo-Topico-2026"
# Los usuarios ingresan con su DNI (convención institucional). DNI ficticios de demostración.
ADMIN_DEMO, SUPERVISOR_DEMO, OPERATOR_ALZ, OPERATOR_BAR, AUDITOR_DEMO = (
    "40000001",
    "40000002",
    "40000003",
    "40000004",
    "40000005",
)
USERS = [
    (ADMIN_DEMO, "Administración del Sistema (demo)", "ADMIN", ("ALZ", "BAR")),
    (SUPERVISOR_DEMO, "Rosa Villanueva Paredes", "SUPERVISOR", ("ALZ", "BAR")),
    (OPERATOR_ALZ, "Carmen Quispe Huamán", "OPERATOR", ("ALZ",)),
    (OPERATOR_BAR, "Lucía Ramos Mendoza", "OPERATOR", ("BAR",)),
    (AUDITOR_DEMO, "Jorge Salazar Ríos", "AUDITOR", ("ALZ", "BAR")),
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


def seed_reference(session_factory: object, rng: random.Random, *, with_email: bool = True) -> list[str]:
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
            email = (
                None
                if (i % 9 == 4 or not with_email)
                else f"{normalize_key(first.split()[0]).lower()}.{normalize_key(paternal).lower()}{i}@pj.gob.pe"
            )
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
    parser.add_argument("--now", action="store_true", help="La jornada de hoy termina en la hora actual (en curso)")
    parser.add_argument("--history-days", type=int, default=0, help="Días hábiles anteriores con jornadas completas")
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--test-email", default=None, help="Correo del trabajador de prueba (recibe notificaciones)")
    parser.add_argument(
        "--report", default="../DATOS-DE-PRUEBA.xlsx", help="Excel con accesos, trabajadores y atenciones"
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.is_production and not args.allow_production:
        print("seed_demo no puede ejecutarse en producción (use --allow-production si aún no hay datos reales).")
        return 1
    if args.test_db:
        settings = settings.model_copy(update={"database_url": settings.test_database_url})
    settings = settings.model_copy(
        update={"notifications_worker_enabled": False, "log_dir": None, "email_backend": "disabled"}
    )

    real_now = dt.datetime.now(INSTITUTION_TZ)
    day = args.date or real_now.date()
    clock = FixedClock(dt.datetime.combine(day, dt.time(8, 5), tzinfo=INSTITUTION_TZ))
    app = create_app(settings, clock=clock)
    limiter.enabled = False
    if settings.is_production and _has_real_appointments(app.state.session_factory):
        print("Ya existen atenciones registradas por usuarios reales: no se cargan datos de demostración.")
        return 1

    rng = random.Random(2026)  # noqa: S311 - datos ficticios reproducibles, no criptografía
    dnis = seed_reference(app.state.session_factory, rng, with_email=not settings.is_production)
    covered = [d for i, d in enumerate(dnis) if i not in (7, 23, 38)]
    client = TestClient(app)
    tokens: dict[str, tuple[dt.datetime, dict[str, str]]] = {}

    def login(username: str) -> dict[str, str]:
        """Inicia sesión solo si no hay token o está por vencer (el reloj simulado avanza)."""
        cached = tokens.get(username)
        if cached and dt.timedelta(0) <= clock.now() - cached[0] < dt.timedelta(minutes=12):
            return cached[1]
        r = client.post(f"{API_PREFIX}/auth/login", json={"username": username, "password": DEMO_PASSWORD})
        r.raise_for_status()
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        tokens[username] = (clock.now(), headers)
        return headers

    sites = {s["code"]: s["id"] for s in client.get(f"{API_PREFIX}/sites", headers=login(ADMIN_DEMO)).json()}
    operators = {"ALZ": OPERATOR_ALZ, "BAR": OPERATOR_BAR}

    def has_data(site: str, when: dt.date) -> bool:
        r = client.get(
            f"{API_PREFIX}/sites/{sites[site]}/queue", params={"date": when.isoformat()}, headers=login(operators[site])
        )
        return r.status_code == 200 and r.json()["counts"]["total"] > 0

    def reasons(username: str, type_: str) -> list[dict[str, object]]:
        return client.get(f"{API_PREFIX}/catalogs/reasons", params={"type": type_}, headers=login(username)).json()

    def act(username: str, appt: dict[str, object], action: str, **body: object) -> dict[str, object]:
        r = client.post(f"{API_PREFIX}/appointments/{appt['public_id']}/{action}", json=body, headers=login(username))
        r.raise_for_status()
        return r.json()

    def register(site: str, dni: str, channel: str) -> dict[str, object] | None:
        r = client.post(
            f"{API_PREFIX}/appointments",
            headers=login(operators[site]),
            json={"site_id": sites[site], "document_number": dni, "channel": channel},
        )
        return r.json() if r.status_code == 201 else None  # p. ej., capacidad alcanzada

    def start_day(when: dt.date, at: dt.time) -> None:
        clock.set(dt.datetime.combine(when, at, tzinfo=INSTITUTION_TZ))
        tokens.clear()

    # Historial: jornadas completas de días hábiles anteriores (para reportes e historial).
    history: list[dt.date] = []
    cursor = day
    while len(history) < args.history_days:
        cursor -= dt.timedelta(days=1)
        if cursor.isoweekday() <= 5:
            history.append(cursor)
    for when in reversed(history):
        for site in ("ALZ", "BAR"):
            if has_data(site, when):
                continue
            start_day(when, dt.time(8, 5))
            user = operators[site]
            pool = rng.sample(covered, rng.randint(9, 16) if site == "ALZ" else rng.randint(5, 10))
            day_appts = []
            for dni in pool:
                clock.advance(minutes=rng.randint(2, 9))
                appt = register(site, dni, rng.choice(["PHONE", "PHONE", "WALK_IN"]))
                if appt:
                    day_appts.append(appt)
            simple_cancel = [r["id"] for r in reasons(user, "CANCEL") if not r["requires_note"]]
            for appt in day_appts:
                roll = rng.random()
                if roll < 0.08:
                    act(user, appt, "cancel", reason_id=rng.choice(simple_cancel))
                    continue
                act(user, appt, "call")
                if roll < 0.15:
                    clock.advance(minutes=11)
                    act(user, appt, "no-show")
                    continue
                clock.advance(minutes=rng.randint(1, 5))
                act(user, appt, "start")
                clock.advance(minutes=rng.randint(8, 18))
                act(user, appt, "finish")
            print(f"  {when:%d/%m/%Y} {site}: {len(day_appts)} atenciones")

    # Jornada del día, en curso.
    if has_data("ALZ", day):
        print(f"La jornada del {day} ya tiene datos; no se generan atenciones nuevas.")
    else:
        if args.now and day == real_now.date():
            # Se simula la mañana de modo que termine cerca de la hora actual.
            start = (real_now - dt.timedelta(minutes=125)).time().replace(second=0, microsecond=0)
            start_day(day, max(start, dt.time(8, 5)))
        else:
            start_day(day, dt.time(8, 5))
        today_pool = [d for d in covered if d != covered[30]]  # el DNI de ejemplo queda libre para probar
        registered = []
        for i, dni in enumerate(today_pool[:14]):
            clock.advance(minutes=rng.randint(2, 6))
            appt = register("ALZ", dni, "PHONE" if i % 3 else "WALK_IN")
            if appt:
                registered.append(appt)

        # Primeras atenciones del día: llamar → iniciar → finalizar
        for appt in registered[:4]:
            act(OPERATOR_ALZ, appt, "call")
            clock.advance(minutes=3)
            act(OPERATOR_ALZ, appt, "start")
            clock.advance(minutes=rng.randint(9, 14))
            act(OPERATOR_ALZ, appt, "finish")
        cancel_reason = next(r for r in reasons(OPERATOR_ALZ, "CANCEL") if r["code"] == "ATENCION_EXTERNA")
        act(
            OPERATOR_ALZ,
            registered[4],
            "cancel",
            reason_id=cancel_reason["id"],
            note="Se atenderá en la clínica por la tarde",
        )
        act(OPERATOR_ALZ, registered[5], "call")
        clock.advance(minutes=11)
        act(OPERATOR_ALZ, registered[5], "no-show")
        act(OPERATOR_ALZ, registered[6], "call")
        clock.advance(minutes=2)
        act(OPERATOR_ALZ, registered[6], "start")
        clock.advance(minutes=4)
        act(OPERATOR_ALZ, registered[7], "call")

        for dni in today_pool[20:26]:
            register("BAR", dni, "PHONE")

    if args.test_email:
        _set_test_email(app.state.session_factory, covered[30], args.test_email)

    print(f"Jornada de demostración generada para el {day:%d/%m/%Y} (hasta las {clock.local_now():%H:%M}).")
    if args.report:
        from scripts.demo_report import write_report

        base_url = settings.public_app_url.removesuffix("/consulta") if settings.public_app_url else ""
        path = write_report(
            app.state.session_factory,
            args.report,
            users=USERS,
            password=DEMO_PASSWORD,
            base_url=base_url,
            test_dni=covered[30],
            test_email=args.test_email,
            uncovered_dni=dnis[7],
        )
        print(f"Documento con accesos y datos de prueba: {path}")
    print(f"Usuarios (contraseña: {DEMO_PASSWORD}): " + ", ".join(u[0] for u in USERS))
    print(f"DNI habilitado de ejemplo: {covered[30]} · DNI sin cobertura: {dnis[7]}")
    if not args.now:
        print(f"Para ver la jornada en curso: DEV_CLOCK_START={day.isoformat()}T{clock.local_now():%H:%M}:00-05:00")
    return 0


def _has_real_appointments(session_factory: object) -> bool:
    """¿Algún usuario que no sea de demostración registró atenciones? (sistema ya en uso)."""
    demo = [u[0] for u in USERS]
    with session_factory() as s:  # type: ignore[operator]
        real = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .join(AppUser, AppUser.id == Appointment.registered_by)
            .where(AppUser.username.not_in(demo))
        )
    return bool(real)


def _set_test_email(session_factory: object, dni: str, email: str) -> None:
    with session_factory() as s:  # type: ignore[operator]
        worker = s.scalar(select(Worker).where(Worker.document_number == dni))
        assert worker is not None
        worker.institutional_email = email
        s.commit()
    print(f"Trabajador de prueba DNI {dni}: notificaciones a {email}")


if __name__ == "__main__":
    sys.exit(main())
