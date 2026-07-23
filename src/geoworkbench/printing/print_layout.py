from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import ceil, isfinite

REFERENCE_PRINT_DPI = 96
MAX_ROLL_LENGTH_MM = 5000.0


class PrintScaleMode(StrEnum):
    """How the horizontal print geometry is mapped to the selected medium."""

    FIT = "fit"
    ACTUAL_SIZE = "actual_size"


@dataclass(frozen=True, slots=True)
class PrintMediaDimensions:
    width_mm: float
    height_mm: float
    content_width_mm: float
    content_height_mm: float
    is_roll: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("media width", self.width_mm),
            ("media height", self.height_mm),
            ("content width", self.content_width_mm),
            ("content height", self.content_height_mm),
        ):
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        if self.content_width_mm > self.width_mm or self.content_height_mm > self.height_mm:
            raise ValueError("print margins exceed the selected medium")


@dataclass(frozen=True, slots=True)
class PrintContinuationSlice:
    """One horizontal continuation of the same vertical report interval."""

    source_left_px: float
    source_right_px: float
    index: int
    total: int
    scale_px_to_mm: float

    def __post_init__(self) -> None:
        if not isfinite(self.source_left_px) or not isfinite(self.source_right_px):
            raise ValueError("continuation boundaries must be finite")
        if self.source_left_px < 0 or self.source_right_px <= self.source_left_px:
            raise ValueError("continuation boundaries are invalid")
        if self.index < 1 or self.total < 1 or self.index > self.total:
            raise ValueError("continuation index is invalid")
        if not isfinite(self.scale_px_to_mm) or self.scale_px_to_mm <= 0:
            raise ValueError("continuation scale must be positive")

    @property
    def source_width_px(self) -> float:
        return self.source_right_px - self.source_left_px

    @property
    def rendered_width_mm(self) -> float:
        return self.source_width_px * self.scale_px_to_mm


_STANDARD_MEDIA_MM: dict[str, tuple[float, float]] = {
    "a0": (841.0, 1189.0),
    "a1": (594.0, 841.0),
    "a2": (420.0, 594.0),
    "a3": (297.0, 420.0),
    "a4": (210.0, 297.0),
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
}


def standard_media_size_mm(page_format: str) -> tuple[float, float] | None:
    size = _STANDARD_MEDIA_MM.get(str(page_format).casefold())
    return tuple(size) if size is not None else None


def resolve_media_dimensions(
    *,
    page_format: str,
    orientation: str,
    custom_width_mm: float,
    custom_height_mm: float,
    margins_mm: tuple[float, float, float, float],
    content_width_px: int,
    content_height_px: int,
    scale_mode: PrintScaleMode,
    reference_dpi: int = REFERENCE_PRINT_DPI,
) -> PrintMediaDimensions:
    """Resolve physical paper and printable dimensions without Qt.

    Roll length is content-derived.  A roll segment is capped at 5000 mm because
    that is the maximum custom length supported by the application contract; a
    longer document is represented by deterministic continuation pages.
    """

    if content_width_px <= 0 or content_height_px <= 0:
        raise ValueError("print content dimensions must be positive")
    if reference_dpi <= 0:
        raise ValueError("reference DPI must be positive")
    left, top, right, bottom = _validated_margins(margins_mm)
    format_value = str(page_format).casefold()
    is_roll = format_value == "roll"

    if format_value in {"custom", "roll"}:
        width = _positive_dimension(custom_width_mm, "custom width")
        height = _positive_dimension(custom_height_mm, "custom height")
    else:
        size = standard_media_size_mm(format_value)
        if size is None:
            raise ValueError(f"unsupported print medium: {page_format}")
        width, height = size

    if not is_roll and str(orientation).casefold() == "landscape":
        width, height = height, width

    if is_roll:
        available_width = width - left - right
        if available_width <= 0:
            raise ValueError("print margins exceed roll width")
        natural_width = content_width_px / reference_dpi * 25.4
        natural_height = content_height_px / reference_dpi * 25.4
        horizontal_scale = (
            available_width / natural_width if scale_mode is PrintScaleMode.FIT else 1.0
        )
        required_height = top + bottom + natural_height * horizontal_scale
        height = min(MAX_ROLL_LENGTH_MM, max(25.0, required_height))

    content_width = width - left - right
    content_height = height - top - bottom
    return PrintMediaDimensions(width, height, content_width, content_height, is_roll)


def build_horizontal_continuations(
    *,
    source_width_px: float,
    available_width_mm: float,
    scale_mode: PrintScaleMode,
    overlap_mm: float = 0.0,
    reference_dpi: int = REFERENCE_PRINT_DPI,
) -> tuple[PrintContinuationSlice, ...]:
    """Build stable horizontal pages for Fit or physical 100% output.

    ``actual_size`` maps one logical source pixel to 1/96 inch.  If the source
    is wider than the printable medium, continuation pages are emitted with a
    small configurable overlap.  ``fit`` always produces one horizontal page.
    """

    if not isfinite(source_width_px) or source_width_px <= 0:
        raise ValueError("source width must be positive")
    if not isfinite(available_width_mm) or available_width_mm <= 0:
        raise ValueError("available print width must be positive")
    if not isfinite(overlap_mm) or overlap_mm < 0:
        raise ValueError("continuation overlap cannot be negative")
    if reference_dpi <= 0:
        raise ValueError("reference DPI must be positive")

    if scale_mode is PrintScaleMode.FIT:
        return (
            PrintContinuationSlice(
                0.0,
                float(source_width_px),
                1,
                1,
                available_width_mm / float(source_width_px),
            ),
        )

    px_to_mm = 25.4 / reference_dpi
    capacity_px = available_width_mm / px_to_mm
    overlap_px = overlap_mm / px_to_mm
    if overlap_px >= capacity_px:
        raise ValueError("continuation overlap must be smaller than printable width")
    if source_width_px <= capacity_px:
        return (
            PrintContinuationSlice(0.0, float(source_width_px), 1, 1, px_to_mm),
        )

    step_px = capacity_px - overlap_px
    total = max(1, int(ceil((source_width_px - overlap_px) / step_px)))
    raw: list[tuple[float, float]] = []
    left = 0.0
    for _ in range(total):
        right = min(float(source_width_px), left + capacity_px)
        raw.append((left, right))
        if right >= source_width_px:
            break
        left += step_px
    count = len(raw)
    return tuple(
        PrintContinuationSlice(left, right, index + 1, count, px_to_mm)
        for index, (left, right) in enumerate(raw)
    )


def _positive_dimension(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    normalized = float(value)
    if not isfinite(normalized) or not 25.0 <= normalized <= MAX_ROLL_LENGTH_MM:
        raise ValueError(f"{name} must be between 25 and {MAX_ROLL_LENGTH_MM:g} mm")
    return normalized


def _validated_margins(
    margins_mm: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if len(margins_mm) != 4:
        raise ValueError("four print margins are required")
    values: list[float] = []
    for value in margins_mm:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("print margins must be numeric")
        normalized = float(value)
        if not isfinite(normalized) or not 0.0 <= normalized <= 100.0:
            raise ValueError("print margins must be between 0 and 100 mm")
        values.append(normalized)
    return tuple(values)  # type: ignore[return-value]
