from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class GridLine:
    """One normalized engineering-grid line shared by screen and print."""

    fraction: float
    major: bool


def engineering_tick_levels(
    minimum: float,
    maximum: float,
    major_divisions: int,
    minor_divisions: int,
) -> tuple[tuple[float, float], ...]:
    """Return stable major/minor spacing levels for an engineering axis.

    The result is intentionally Qt-independent.  The screen adapter translates
    these levels into ``pyqtgraph.AxisItem`` spacing, while print renderers use
    :func:`normalized_grid_lines` and project the same division contract into a
    physical page rectangle.
    """

    span = abs(float(maximum) - float(minimum))
    if not isfinite(span) or span <= 0.0:
        return ()
    major = max(1, int(major_divisions))
    minor = max(1, int(minor_divisions))
    origin = min(float(minimum), float(maximum))
    major_spacing = span / major
    levels = [(major_spacing, origin)]
    if minor > 1:
        levels.append((major_spacing / minor, origin))
    return tuple(levels)


def normalized_grid_lines(
    major_divisions: int,
    minor_divisions: int,
) -> tuple[GridLine, ...]:
    """Return ordered major/minor positions in the closed interval ``[0, 1]``."""

    major = max(1, int(major_divisions))
    minor = max(1, int(minor_divisions))
    lines: list[GridLine] = []
    for major_index in range(major + 1):
        lines.append(GridLine(major_index / major, True))
        if major_index == major or minor == 1:
            continue
        lines.extend(
            GridLine((major_index + minor_index / minor) / major, False)
            for minor_index in range(1, minor)
        )
    return tuple(lines)


def project_grid_lines(
    length: float,
    major_divisions: int,
    minor_divisions: int,
    *,
    origin: float = 0.0,
) -> tuple[tuple[float, bool], ...]:
    """Project normalized grid lines into pixels, millimetres, or another unit."""

    safe_length = float(length)
    safe_origin = float(origin)
    if not isfinite(safe_length) or safe_length < 0.0:
        raise ValueError("Grid projection length must be a finite non-negative number")
    if not isfinite(safe_origin):
        raise ValueError("Grid projection origin must be finite")
    return tuple(
        (safe_origin + safe_length * line.fraction, line.major)
        for line in normalized_grid_lines(major_divisions, minor_divisions)
    )
