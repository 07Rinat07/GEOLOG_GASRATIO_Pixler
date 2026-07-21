from __future__ import annotations

from pathlib import Path


def available_las_output_path(path: str | Path) -> Path:
    """Return a non-existing .las path by adding a numeric suffix when needed."""

    candidate = Path(path)
    if candidate.suffix.casefold() != ".las":
        candidate = candidate.with_suffix(".las")
    if not candidate.exists():
        return candidate
    number = 2
    while True:
        alternative = candidate.with_name(f"{candidate.stem}_{number}{candidate.suffix}")
        if not alternative.exists():
            return alternative
        number += 1
