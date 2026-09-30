"""Reloj de la aplicación.

Única fuente de "ahora" y "hoy". Los instantes se manejan en UTC y la fecha operativa
se calcula en la zona institucional (America/Lima). En pruebas se reemplaza por FixedClock.
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

INSTITUTION_TZ = ZoneInfo("America/Lima")


class Clock:
    tz: ZoneInfo = INSTITUTION_TZ

    def now(self) -> datetime:
        """Instante actual (aware, UTC)."""
        return datetime.now(UTC)

    def local_now(self) -> datetime:
        return self.now().astimezone(self.tz)

    def today(self) -> date:
        """Fecha operativa en America/Lima."""
        return self.local_now().date()

    def combine(self, day: date, at: time) -> datetime:
        """Convierte fecha + hora local de Lima a un instante aware."""
        return datetime.combine(day, at, tzinfo=self.tz)


class FixedClock(Clock):
    """Reloj controlable para pruebas."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FixedClock requiere un datetime con zona horaria")
        self._instant = instant

    def now(self) -> datetime:
        return self._instant.astimezone(UTC)

    def set(self, instant: datetime) -> None:
        self._instant = instant

    def advance(self, **delta: float) -> None:
        from datetime import timedelta

        self._instant = self._instant + timedelta(**delta)
