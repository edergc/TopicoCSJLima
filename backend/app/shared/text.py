"""Normalización de textos y documentos de identidad."""

import re
import unicodedata
from typing import cast

# [0-9] y no \d: en Python \d también acepta dígitos de otros alfabetos (árabes, devanagari…).
_DNI_RE = re.compile(r"^[0-9]{8}$")
_SPACES = re.compile(r"\s+")


def normalize_document(raw: object) -> str:
    """Normaliza un DNI: quita espacios/guiones y restaura ceros iniciales perdidos (p. ej., por Excel).

    Devuelve el valor normalizado (puede seguir siendo inválido; validar con is_valid_dni).
    """
    if raw is None:
        return ""
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    text = str(raw).strip().replace(" ", "").replace("-", "").replace(".", "")
    if text.isdigit() and 5 <= len(text) < 8:
        text = text.zfill(8)
    return text.upper()


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_safe[T](value: T) -> T:
    """Texto para CSV/Excel: un apóstrofo inicial evita que Excel lo ejecute como fórmula (OWASP)."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return cast(T, "'" + value)
    return value


def is_valid_dni(value: str) -> bool:
    return bool(_DNI_RE.fullmatch(value))


def strict_dni(raw: object) -> str:
    """DNI ingresado a mano (pantallas, API): exactamente 8 dígitos 0-9, sin completar ceros.

    Solo se toleran espacios al inicio o al final. El relleno de ceros iniciales es exclusivo de la
    importación de Excel (normalize_document), donde Excel los pierde al tratar el DNI como número.
    """
    return "" if raw is None else str(raw).strip()


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_key(text: str) -> str:
    """Clave de comparación: mayúsculas, sin tildes, espacios simples."""
    return _SPACES.sub(" ", strip_accents(text).upper()).strip()


def clean_name(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = _SPACES.sub(" ", str(text)).strip().upper()
    return cleaned or None


def mask_name(first_names: str, paternal_surname: str) -> str:
    """'JUAN CARLOS', 'PEREZ' → 'J*** P***' (consulta pública)."""
    first = first_names.strip()[:1]
    last = paternal_surname.strip()[:1]
    return f"{first}*** {last}***".strip()


def display_name(first_names: str, paternal_surname: str, maternal_surname: str | None) -> str:
    """'PEREZ QUISPE, Juan Carlos' para listas operativas."""
    surnames = " ".join(p for p in (paternal_surname, maternal_surname) if p)
    return f"{surnames}, {first_names.title()}"


def short_name(first_names: str, paternal_surname: str, maternal_surname: str | None) -> str:
    """'Juan P. Q.' (cola en pantalla compartida)."""
    first = first_names.split()[0].title() if first_names else ""
    initials = " ".join(f"{p[0]}." for p in (paternal_surname, maternal_surname) if p)
    return f"{first} {initials}".strip()
