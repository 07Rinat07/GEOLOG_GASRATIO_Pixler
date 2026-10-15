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


@dataclass(frozen=True, slots=True)
class PreviewOverlay:
    """Immutable collection of marks, with one bounded editing operation at a time."""

    marks: tuple[PreviewMark, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.marks, tuple) or len(self.marks) > 10000:
            raise ValueError("Invalid overlay collection")
        if not all(isinstance(mark, PreviewMark) for mark in self.marks):
            raise ValueError("Overlay contains invalid marks")

    def add(self, mark: PreviewMark) -> "PreviewOverlay":
        if not isinstance(mark, PreviewMark):
            raise ValueError("Invalid overlay mark")
        return PreviewOverlay(self.marks + (mark,))

    def replace(self, index: int, mark: PreviewMark) -> "PreviewOverlay":
        self._validate_index(index)
        if not isinstance(mark, PreviewMark):
            raise ValueError("Invalid overlay mark")
        return PreviewOverlay(self.marks[:index] + (mark,) + self.marks[index + 1:])

    def remove(self, index: int) -> "PreviewOverlay":
        self._validate_index(index)
        return PreviewOverlay(self.marks[:index] + self.marks[index + 1:])

    def _validate_index(self, index: int) -> None:
        if type(index) is not int or not 0 <= index < len(self.marks):
            raise IndexError("Invalid overlay mark index")


@dataclass(frozen=True, slots=True)
class PreviewEditHistory:
    """Bounded immutable undo/redo snapshots for one report preview session."""

    current: PreviewOverlay = PreviewOverlay()
    undo_stack: tuple[PreviewOverlay, ...] = ()
    redo_stack: tuple[PreviewOverlay, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.current, PreviewOverlay):
            raise ValueError("Invalid current overlay")
        if len(self.undo_stack) > 100 or len(self.redo_stack) > 100:
            raise ValueError("Preview edit history exceeds limit")
        if not all(isinstance(item, PreviewOverlay) for item in (*self.undo_stack, *self.redo_stack)):
            raise ValueError("Invalid preview history snapshot")

    def apply(self, next_overlay: PreviewOverlay) -> "PreviewEditHistory":
        if not isinstance(next_overlay, PreviewOverlay):
            raise ValueError("Invalid preview overlay")
        if next_overlay == self.current:
            return self
        return PreviewEditHistory(
            next_overlay, (self.undo_stack + (self.current,))[-100:], (),
        )

    def undo(self) -> "PreviewEditHistory":
        if not self.undo_stack:
            return self
        return PreviewEditHistory(
            self.undo_stack[-1], self.undo_stack[:-1],
            (self.redo_stack + (self.current,))[-100:],
        )

    def redo(self) -> "PreviewEditHistory":
        if not self.redo_stack:
            return self
        return PreviewEditHistory(
            self.redo_stack[-1], (self.undo_stack + (self.current,))[-100:],
            self.redo_stack[:-1],
        )
