from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from geoworkbench.services.time_display import (
    format_datetime_axis_tick,
    format_elapsed_time,
)
from geoworkbench.tablet.grid_geometry import (
    DEFAULT_DEPTH_GRID_MAJOR_STEP,
    adaptive_aligned_step,
    aligned_engineering_grid_lines,
)


class VerticalRulerKind(StrEnum):
    DEPTH = "depth"
    RELATIVE_TIME = "relative_time"
    DATETIME = "datetime"


class VerticalRulerMode(StrEnum):
    AUTOMATIC = "automatic"
    LABELS_AND_TICKS = "labels_and_ticks"
    TICKS_ONLY = "ticks_only"
    OFF = "off"


@dataclass(frozen=True, slots=True)
class VerticalRulerTick:
    value: float
    major: bool
    label: str


@dataclass(frozen=True, slots=True)
class VerticalRulerLayout:
    """One authoritative vertical scale shared by every tablet column.

    The visible range, engineering step and labels are calculated once for the
    whole tablet/page. Individual tracks may hide labels when too narrow, but
    they must never calculate different tick values or a different depth step.
    """

    minimum: float
    maximum: float
    kind: VerticalRulerKind
    unit: str
    major_step: float
    minor_step: float
    ticks: tuple[VerticalRulerTick, ...]
    minimum_label_spacing_px: float


@dataclass(frozen=True, slots=True)
class VerticalRulerPresentation:
    show_axis: bool
    show_labels: bool
    axis_width: int
    tick_length: int


_GRAPHICAL_TRACK_KINDS = frozenset({"curve", "gas", "dexp", "calcimetry"})


def supports_inner_vertical_ruler(track_kind: str) -> bool:
    return str(track_kind).strip().casefold() in _GRAPHICAL_TRACK_KINDS


def _format_value(
    value: float,
    *,
    spacing: float,
    kind: VerticalRulerKind,
    unit: str,
) -> str:
    if not isfinite(value):
        return ""
    if kind is VerticalRulerKind.DATETIME:
        return format_datetime_axis_tick(float(value), float(spacing))
    if kind is VerticalRulerKind.RELATIVE_TIME:
        rendered = format_elapsed_time(float(value), unit)
        return "" if rendered == "—" else rendered

    absolute_spacing = abs(float(spacing))
    decimals = 0
    if 0.0 < absolute_spacing < 1.0:
        rendered_spacing = f"{absolute_spacing:.6f}".rstrip("0")
        decimals = min(6, len(rendered_spacing.partition(".")[2]))
    return f"{float(value):.{decimals}f}" if decimals else f"{float(value):g}"


def build_vertical_ruler_layout(
    minimum: float,
    maximum: float,
    *,
    pixel_height: float,
    kind: VerticalRulerKind,
    unit: str = "",
    print_mode: bool = False,
) -> VerticalRulerLayout:
    """Build the single shared ruler contract for a viewport or print page."""

    lower, upper = sorted((float(minimum), float(maximum)))
    if not isfinite(lower) or not isfinite(upper) or lower == upper:
        raise ValueError("Границы общей вертикальной шкалы должны быть конечными и различными")

    height = max(1.0, float(pixel_height))
    minimum_label_spacing = 42.0 if print_mode else 52.0
    max_intervals = max(2, int(height // minimum_label_spacing))
    base_step = DEFAULT_DEPTH_GRID_MAJOR_STEP if kind is VerticalRulerKind.DEPTH else 1.0
    major_step = adaptive_aligned_step(
        lower,
        upper,
        base_step,
        max_intervals=max_intervals,
    )
    if not isfinite(major_step) or major_step <= 0.0:
        raise ValueError("Не удалось определить общий шаг вертикальной шкалы")
    minor_step = major_step / 5.0

    ticks = tuple(
        VerticalRulerTick(
            value=line.value,
            major=line.major,
            label=(
                _format_value(
                    line.value,
                    spacing=major_step,
                    kind=kind,
                    unit=unit,
                )
                if line.major
                else ""
            ),
        )
        for line in aligned_engineering_grid_lines(
            lower,
            upper,
            major_step,
            5,
        )
    )
    return VerticalRulerLayout(
        minimum=lower,
        maximum=upper,
        kind=kind,
        unit=unit,
        major_step=major_step,
        minor_step=minor_step,
        ticks=ticks,
        minimum_label_spacing_px=minimum_label_spacing,
    )


def vertical_ruler_presentation(
    layout: VerticalRulerLayout,
    *,
    track_kind: str,
    track_width: int,
    mode: VerticalRulerMode = VerticalRulerMode.AUTOMATIC,
    force_labels: bool = False,
) -> VerticalRulerPresentation:
    """Resolve only track-local visibility; tick values remain shared."""

    normalized_kind = str(track_kind).strip().casefold()
    show_axis = normalized_kind == "depth" or supports_inner_vertical_ruler(normalized_kind)
    if mode is VerticalRulerMode.OFF:
        show_axis = False
    if not show_axis:
        return VerticalRulerPresentation(False, False, 0, 0)

    width = max(1, int(track_width))
    if force_labels or mode is VerticalRulerMode.LABELS_AND_TICKS:
        show_labels = True
    elif mode is VerticalRulerMode.TICKS_ONLY:
        show_labels = False
    else:
        threshold = 92 if layout.kind is VerticalRulerKind.DATETIME else 76
        show_labels = width >= threshold

    preferred_width = (
        58
        if layout.kind is VerticalRulerKind.DATETIME
        else 48
        if layout.kind is VerticalRulerKind.RELATIVE_TIME
        else 38
    )
    axis_width = min(max(10, width - 24), preferred_width) if show_labels else 10
    return VerticalRulerPresentation(
        show_axis=True,
        show_labels=show_labels,
        axis_width=axis_width,
        tick_length=-6 if show_labels else -5,
    )
