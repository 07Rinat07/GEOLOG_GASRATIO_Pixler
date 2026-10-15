"""Validated, non-destructive page-space marks for editable report previews.

Marks are overlays on the generated report, never edits to source well data.
Coordinates are normalized to the printable page rectangle (0..1).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math


class PreviewMarkKind(StrEnum):
    TEXT = "text"
    COMMENT = "comment"
    SYMBOL = "symbol"
    FREEHAND = "freehand"


_MAX_TEXT = 4000
_MAX_POINTS = 4096


def _fraction(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Page coordinates must be finite numbers")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError("Page coordinates must lie within [0, 1]")
    return number


@dataclass(frozen=True, slots=True)
class PreviewMark:
    kind: PreviewMarkKind
    page: int
    x: float
    y: float
    text: str = ""
    points: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PreviewMarkKind):
            raise ValueError("Unsupported preview mark kind")
        if type(self.page) is not int or self.page < 0:
            raise ValueError("Page index must be a non-negative integer")
        object.__setattr__(self, "x", _fraction(self.x))
        object.__setattr__(self, "y", _fraction(self.y))
        if not isinstance(self.text, str) or len(self.text) > _MAX_TEXT:
            raise ValueError("Invalid preview mark text")
        if not isinstance(self.points, tuple) or len(self.points) > _MAX_POINTS:
            raise ValueError("Invalid preview stroke")
        normalized = []
        for point in self.points:
            if not isinstance(point, tuple) or len(point) != 2:
                raise ValueError("Invalid preview stroke point")
            normalized.append((_fraction(point[0]), _fraction(point[1])))
        object.__setattr__(self, "points", tuple(normalized))
        if self.kind is PreviewMarkKind.FREEHAND:
            if self.text or len(normalized) < 2:
                raise ValueError("Freehand marks require at least two points and no text")
        elif normalized:
            raise ValueError("Only freehand marks can contain stroke points")
        elif not self.text.strip():
            raise ValueError("Text, comments and symbols must not be empty")
