"""Comandos administrativos de línea de comandos.

python -m app.cli create-admin --username admin --full-name "Nombre Apellido"
python -m app.cli verify-audit
python -m app.cli send-test-email --to usuario@pj.gob.pe
"""

import argparse
import getpass
import sys

from sqlalchemy import select, text

import app.modules.registry  # noqa: F401
from app.core.config import get_settings
from app.core.db import build_engine, build_session_factory
from app.core.security import hash_password
from app.modules.audit import service as audit
from app.modules.auth.service import validate_password_policy
from app.modules.sites.models import Site
from app.modules.users.models import AppUser, Role


def create_admin(username: str, full_name: str, email: str | None) -> int:
    settings = get_settings()
    factory = build_session_factory(build_engine(settings.database_url, settings))
    with factory() as db:
        username = username.strip().lower()
        if db.scalar(select(AppUser.id).where(AppUser.username == username)):
            print(f"El usuario '{username}' ya existe.", file=sys.stderr)
            return 1
        password = getpass.getpass("Contraseña: ")
        if password != getpass.getpass("Repita la contraseña: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1
        try:
            validate_password_policy(db, password, username)
        except Exception as exc:
            print(f"Contraseña inválida: {getattr(exc, 'details', None) or exc}", file=sys.stderr)
            return 1
        user = AppUser(
            username=username,
            full_name=full_name,
            email=email,
            auth_provider="LOCAL",
            password_hash=hash_password(password),
            must_change_password=False,
            is_active=True,
            failed_login_attempts=0,
        )
        user.roles = list(db.scalars(select(Role).where(Role.code == "ADMIN")))
        user.sites = list(db.scalars(select(Site)))
        db.add(user)
        db.flush()
        audit.record(
            db,
            action="USER_CREATE",
            username="cli",
            resource_type="user",
            resource_id=user.public_id,
            after={"username": username, "roles": ["ADMIN"], "origin": "CLI"},
        )
        db.commit()
        print(f"Administrador '{username}' creado con acceso a todas las sedes.")
        return 0


def verify_audit() -> int:
    settings = get_settings()
    engine = build_engine(settings.database_url, settings)
    with engine.connect() as conn:
        problems = conn.execute(text("SELECT chain_seq, problem FROM topico.verify_audit_chain()")).all()
        total = conn.execute(text("SELECT count(*) FROM topico.audit_event")).scalar()
    if problems:
        print(f"¡ALERTA! Se detectaron {len(problems)} problemas en la cadena de auditoría:")
        for seq, problem in problems[:50]:
            print(f"  evento #{seq}: {problem}")
        return 2
    print(f"Auditoría íntegra ({total} eventos verificados).")
    return 0


def send_test_email(to: str) -> int:
    from app.modules.notifications.channels import OutgoingMessage, build_channel

    channel = build_channel(get_settings())
    if channel is None:
        print("EMAIL_BACKEND=disabled: no hay canal configurado.", file=sys.stderr)
        return 1
    channel.send(OutgoingMessage(0, to, "Prueba de correo — Tópico CSJ Lima", "Correo de prueba del sistema."))
    print(f"Correo de prueba enviado a {to}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="Crear el primer administrador")
    p.add_argument("--username", required=True)
    p.add_argument("--full-name", required=True)
    p.add_argument("--email")
    sub.add_parser("verify-audit", help="Verificar la integridad de la auditoría")
    p = sub.add_parser("send-test-email", help="Probar la configuración de correo")
    p.add_argument("--to", required=True)
    args = parser.parse_args()
    if args.command == "create-admin":
        return create_admin(args.username, args.full_name, args.email)
    if args.command == "verify-audit":
        return verify_audit()
    return send_test_email(args.to)


if __name__ == "__main__":
    sys.exit(main())
