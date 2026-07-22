from __future__ import annotations

from dataclasses import dataclass


PHASE_RANGES: dict[str, tuple[float, float, int]] = {
    "header": (0.00, 0.06, 1),
    "schema": (0.06, 0.14, 2),
    "records": (0.14, 0.72, 3),
    "analysis": (0.72, 0.86, 4),
    "preview": (0.86, 0.94, 5),
    "create": (0.94, 1.00, 6),
}


@dataclass(frozen=True, slots=True)
class ParadoxProgressState:
    phase: str
    phase_number: int
    current: int
    total: int
    phase_ratio: float
    overall_ratio: float


def paradox_progress_state(phase: str, current: int, total: int) -> ParadoxProgressState:
    """Map phase-local progress to a monotonic overall import scale."""

    start, stop, number = PHASE_RANGES.get(phase, (0.0, 1.0, 1))
    safe_total = max(0, int(total))
    safe_current = max(0, int(current))
    ratio = 0.0 if safe_total <= 0 else min(1.0, safe_current / safe_total)
    return ParadoxProgressState(
        phase=phase,
        phase_number=number,
        current=safe_current,
        total=safe_total,
        phase_ratio=ratio,
        overall_ratio=start + (stop - start) * ratio,
    )
