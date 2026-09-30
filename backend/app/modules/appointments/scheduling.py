"""Cálculo de la hora estimada de atención (referencial, RN-16).

Modelo: hay `lanes` puntos de atención (médicos). Cada atención dura `slot` minutos.
Quienes están EN_ATENCION ocupan su punto hasta started_at + slot; luego se atiende a los
LLAMADOS y a los EN_ESPERA, en orden. Los horarios caen siempre dentro de los bloques de
atención (saltando el intervalo entre mañana y tarde). Si no hay bloque disponible, None.
"""

import heapq
from collections.abc import Sequence
from datetime import datetime, timedelta


def _fit_into_blocks(t: datetime, blocks: Sequence[tuple[datetime, datetime]]) -> datetime | None:
    """Primer instante >= t dentro de un bloque (una atención puede iniciar mientras el bloque siga abierto)."""
    for start, end in blocks:
        candidate = max(t, start)
        if candidate < end:
            return candidate
    return None


def estimate_start_times(
    *,
    now: datetime,
    blocks: Sequence[tuple[datetime, datetime]],
    slot_minutes: int,
    lanes: int,
    in_service_started: Sequence[datetime],
    pending_count: int,
) -> list[datetime | None]:
    """Hora estimada de inicio para cada una de las `pending_count` personas en espera (en orden)."""
    slot = timedelta(minutes=slot_minutes)
    ordered_blocks = sorted(blocks)
    free_at = [max(now, started + slot) for started in sorted(in_service_started)[:lanes]]
    free_at += [now] * (max(lanes, 1) - len(free_at))
    heapq.heapify(free_at)

    estimates: list[datetime | None] = []
    for _ in range(pending_count):
        lane_free = heapq.heappop(free_at)
        start = _fit_into_blocks(lane_free, ordered_blocks)
        if start is None:
            estimates.append(None)
            heapq.heappush(free_at, lane_free)
            continue
        estimates.append(start)
        heapq.heappush(free_at, start + slot)
    return estimates
