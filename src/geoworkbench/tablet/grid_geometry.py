from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, isfinite, log10


DEFAULT_GRID_MAJOR_DIVISIONS = 5
DEFAULT_GRID_MINOR_DIVISIONS = 5
DEFAULT_GRID_ALPHA = 0.2
DEFAULT_DEPTH_GRID_MAJOR_STEP = 5.0


@dataclass(frozen=True, slots=True)
class GridLine:
    """One normalized engineering-grid line shared by screen and print."""

    fraction: float
    major: bool


@dataclass(frozen=True, slots=True)
class AlignedGridLine:
    """One engineering-grid coordinate aligned to a physical axis origin."""

    value: float
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


def adaptive_aligned_step(
    minimum: float,
    maximum: float,
    base_step: float = DEFAULT_DEPTH_GRID_MAJOR_STEP,
    *,
    max_intervals: int = 20,
) -> float:
    """Return a zero-aligned step without overcrowding a long visible range.

    Depth logs use a 5 m base grid. A full-well overview may span thousands of
    metres, so the step grows by whole multiples of the base while page-sized
    intervals keep the requested 5 m spacing.
    """

    span = abs(float(maximum) - float(minimum))
    normalized_base = float(base_step)
    interval_limit = max(1, int(max_intervals))
    if not isfinite(span) or not isfinite(normalized_base) or normalized_base <= 0.0:
        return normalized_base
    if span <= 0.0:
        return normalized_base
    required = span / interval_limit
    if required <= normalized_base:
        return normalized_base

    # Use the conventional 1-2-5 engineering series instead of arbitrary
    # multiples of the base step.  Apart from producing familiar labels, this
    # keeps adjacent zoom levels stable (5, 10, 20, 50, 100, ...).
    magnitude = 10.0 ** floor(log10(required))
    normalized = required / magnitude
    tolerance = 1e-12
    if normalized <= 1.0 + tolerance:
        factor = 1.0
    elif normalized <= 2.0 + tolerance:
        factor = 2.0
    elif normalized <= 5.0 + tolerance:
        factor = 5.0
    else:
        factor = 10.0
    return max(normalized_base, factor * magnitude)


def aligned_grid_values(
    minimum: float,
    maximum: float,
    step: float,
    *,
    origin: float = 0.0,
) -> tuple[float, ...]:
    """Return grid coordinates aligned to ``origin`` inside the visible range."""

    lower, upper = sorted((float(minimum), float(maximum)))
    normalized_step = float(step)
    normalized_origin = float(origin)
    if (
        not isfinite(lower)
        or not isfinite(upper)
        or not isfinite(normalized_step)
        or normalized_step <= 0.0
        or not isfinite(normalized_origin)
    ):
        return ()
    tolerance = normalized_step * 1e-9
    first = ceil((lower - normalized_origin - tolerance) / normalized_step)
    last = floor((upper - normalized_origin + tolerance) / normalized_step)
    if last < first:
        return ()
    return tuple(normalized_origin + index * normalized_step for index in range(first, last + 1))


def aligned_engineering_grid_lines(
    minimum: float,
    maximum: float,
    major_step: float,
    minor_divisions: int = DEFAULT_GRID_MINOR_DIVISIONS,
    *,
    origin: float = 0.0,
) -> tuple[AlignedGridLine, ...]:
    """Return zero-aligned major and minor coordinates for a physical axis.

    ``minor_divisions`` is the number of equal intervals inside one major
    interval.  For example, a 5 m major step and five subdivisions produce
    minor lines at every metre while keeping 50, 55, 60, ... as major lines.
    """

    normalized_major = float(major_step)
    normalized_origin = float(origin)
    if not isfinite(normalized_major) or normalized_major <= 0.0 or not isfinite(normalized_origin):
        return ()
    subdivisions = max(1, int(minor_divisions))
    minor_step = normalized_major / subdivisions
    values = aligned_grid_values(
        minimum,
        maximum,
        minor_step,
        origin=normalized_origin,
    )
    tolerance = 1e-8
    return tuple(
        AlignedGridLine(
            value,
            abs(
                (value - normalized_origin) / normalized_major
                - round((value - normalized_origin) / normalized_major)
            )
            <= tolerance,
        )
        for value in values
    )


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
