"""Genera docs/03-diccionario-datos.md a partir del catálogo de PostgreSQL.

El diccionario se obtiene de la base real (comentarios, tipos, restricciones e índices),
así nunca queda desactualizado respecto del esquema.

Uso:
    python -m scripts.generate_data_dictionary            # base principal
    python -m scripts.generate_data_dictionary --test     # base de pruebas
"""

import argparse
from pathlib import Path

import psycopg

from app.core.config import BACKEND_DIR, DB_SCHEMA, get_settings, to_libpq_url

OUTPUT = BACKEND_DIR.parent / "docs" / "03-diccionario-datos.md"

TABLES_SQL = """
SELECT c.relname, obj_description(c.oid, 'pg_class')
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = %s AND c.relkind = 'r' AND c.relname <> 'alembic_version'
 ORDER BY c.relname
"""

COLUMNS_SQL = """
SELECT a.attname,
       format_type(a.atttypid, a.atttypmod),
       NOT a.attnotnull,
       CASE WHEN a.attidentity <> '' THEN 'IDENTITY'
            WHEN a.attgenerated <> '' THEN 'GENERADA'
            ELSE pg_get_expr(d.adbin, d.adrelid) END,
       col_description(a.attrelid, a.attnum)
  FROM pg_attribute a
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
 WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY a.attnum
"""

CONSTRAINTS_SQL = """
SELECT conname, contype, pg_get_constraintdef(oid)
  FROM pg_constraint
 WHERE conrelid = %s::regclass
 ORDER BY CASE contype WHEN 'p' THEN 0 WHEN 'u' THEN 1 WHEN 'f' THEN 2 WHEN 'x' THEN 3 ELSE 4 END, conname
"""

INDEXES_SQL = """
SELECT i.relname, pg_get_indexdef(i.oid)
  FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid
 WHERE x.indrelid = %s::regclass
   AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conindid = i.oid)
 ORDER BY i.relname
"""

TRIGGERS_SQL = """
SELECT t.tgname, p.proname
  FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid
 WHERE t.tgrelid = %s::regclass AND NOT t.tgisinternal
 ORDER BY t.tgname
"""

CONSTRAINT_TYPES = {"p": "PK", "u": "UNIQUE", "f": "FK", "c": "CHECK", "x": "EXCLUDE"}


def _cell(value: object) -> str:
    return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")


def generate(url: str) -> str:
    lines = [
        "# Diccionario de datos — Tópico CSJ Lima",
        "",
        "> Documento **generado automáticamente** desde el catálogo de PostgreSQL con",
        "> `python -m scripts.generate_data_dictionary`. No editar a mano.",
        "",
    ]
    with psycopg.connect(url) as conn:
        tables = conn.execute(TABLES_SQL, (DB_SCHEMA,)).fetchall()
        lines += ["## Tablas", ""]
        lines += [f"- [`{name}`](#{name}) — {_cell(comment)}" for name, comment in tables]
        for name, comment in tables:
            qualified = f"{DB_SCHEMA}.{name}"
            lines += ["", f"## {name}", "", _cell(comment), ""]
            lines += ["| Columna | Tipo | Nulo | Por defecto | Descripción |", "|---|---|---|---|---|"]
            for col, typ, nullable, default, desc in conn.execute(COLUMNS_SQL, (qualified,)):
                lines.append(f"| `{col}` | {typ} | {'sí' if nullable else 'no'} | {_cell(default)} | {_cell(desc)} |")
            constraints = conn.execute(CONSTRAINTS_SQL, (qualified,)).fetchall()
            if constraints:
                lines += ["", "**Restricciones**", "", "| Nombre | Tipo | Definición |", "|---|---|---|"]
                lines += [f"| `{n}` | {CONSTRAINT_TYPES.get(t, t)} | `{_cell(d)}` |" for n, t, d in constraints]
            indexes = conn.execute(INDEXES_SQL, (qualified,)).fetchall()
            if indexes:
                lines += ["", "**Índices adicionales**", ""]
                lines += [f"- `{n}`: `{_cell(d)}`" for n, d in indexes]
            triggers = conn.execute(TRIGGERS_SQL, (qualified,)).fetchall()
            if triggers:
                lines += ["", "**Triggers**", ""]
                lines += [f"- `{n}` → `{fn}()`" for n, fn in triggers]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Usar la base de datos de pruebas")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    settings = get_settings()
    url = settings.test_database_migration_url if args.test else settings.database_migration_url
    if not url:
        raise SystemExit("URL de base de datos no configurada.")
    args.output.write_text(generate(to_libpq_url(url)), encoding="utf-8")
    print(f"Diccionario generado en {args.output}")


if __name__ == "__main__":
    main()
