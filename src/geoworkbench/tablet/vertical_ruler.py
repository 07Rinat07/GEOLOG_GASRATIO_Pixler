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
class VerticalRulerScaleSettings:
    """Tablet/page-wide frequency settings for one authoritative ruler.

    ``major_step=None`` keeps adaptive engineering spacing. A manual value is
    applied once to the whole tablet/page; individual tracks are never allowed
    to calculate a different depth grid.
    """

    major_step: float | None = None
    minor_divisions: int = 5

    def __post_init__(self) -> None:
        if self.major_step is not None and (
            not isfinite(self.major_step) or self.major_step <= 0.0
        ):
            raise ValueError("Шаг основной вертикальной шкалы должен быть положительным")
        if not 1 <= self.minor_divisions <= 20:
            raise ValueError("Число делений между основными отметками должно быть от 1 до 20")


@dataclass(frozen=True, slots=True)
class VerticalRulerTrackSettings:
    """Per-column visibility without creating a second depth scale.

    Frequency multipliers only hide a subset of ticks/labels from the shared
    ruler. Every displayed value therefore still matches the main well-depth
    column and has the same Y coordinate.
    """

    mode: VerticalRulerMode = VerticalRulerMode.AUTOMATIC
    label_every_major: int = 1
    major_tick_every: int = 1
    minor_tick_every: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.mode, VerticalRulerMode):
            raise ValueError("Режим внутренней вертикальной шкалы не поддерживается")
        for name, value in (
            ("label_every_major", self.label_every_major),
            ("major_tick_every", self.major_tick_every),
            ("minor_tick_every", self.minor_tick_every),
        ):
            if not 1 <= value <= 20:
                raise ValueError(f"{name} должен находиться в диапазоне 1–20")


@dataclass(frozen=True, slots=True)
class VerticalRulerTick:
    value: float
    major: bool
    label: str
    major_index: int | None = None
    minor_index: int | None = None


@dataclass(frozen=True, slots=True)
class VerticalRulerLayout:
    """One authoritative vertical scale shared by every tablet column.

    The visible range, engineering step and tick values are calculated once for
    the whole tablet/page. A track may hide labels or some ticks, but must never
    calculate different depth values or a different vertical mapping.
    """

    minimum: float
    maximum: float
    kind: VerticalRulerKind
    unit: str
    major_step: float
    minor_step: float
    minor_divisions: int
    ticks: tuple[VerticalRulerTick, ...]
    minimum_label_spacing_px: float


@dataclass(frozen=True, slots=True)
class VerticalRulerPresentation:
    show_axis: bool
    show_labels: bool
    axis_width: int
    tick_length: int
    label_every_major: int = 1
    major_tick_every: int = 1
    minor_tick_every: int = 1


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
    settings: VerticalRulerScaleSettings | None = None,
) -> VerticalRulerLayout:
    """Build the single shared ruler contract for a viewport or print page."""

    lower, upper = sorted((float(minimum), float(maximum)))
    if not isfinite(lower) or not isfinite(upper) or lower == upper:
        raise ValueError("Границы общей вертикальной шкалы должны быть конечными и различными")

    resolved = settings or VerticalRulerScaleSettings()
    height = max(1.0, float(pixel_height))
    minimum_label_spacing = 42.0 if print_mode else 52.0
    max_intervals = max(2, int(height // minimum_label_spacing))
    base_step = DEFAULT_DEPTH_GRID_MAJOR_STEP if kind is VerticalRulerKind.DEPTH else 1.0
    major_step = (
        float(resolved.major_step)
        if resolved.major_step is not None
        else adaptive_aligned_step(
            lower,
            upper,
            base_step,
            max_intervals=max_intervals,
        )
    )
    if not isfinite(major_step) or major_step <= 0.0:
        raise ValueError("Не удалось определить общий шаг вертикальной шкалы")
    minor_step = major_step / resolved.minor_divisions

    raw_lines = aligned_engineering_grid_lines(
        lower,
        upper,
        major_step,
        resolved.minor_divisions,
    )
    major_counter = 0
    minor_counter = 0
    ticks: list[VerticalRulerTick] = []
    for line in raw_lines:
        if line.major:
            ticks.append(
                VerticalRulerTick(
                    value=line.value,
                    major=True,
                    label=_format_value(
                        line.value,
                        spacing=major_step,
                        kind=kind,
                        unit=unit,
                    ),
                    major_index=major_counter,
                )
            )
            major_counter += 1
        else:
            ticks.append(
                VerticalRulerTick(
                    value=line.value,
                    major=False,
                    label="",
                    minor_index=minor_counter,
                )
            )
            minor_counter += 1

    return VerticalRulerLayout(
        minimum=lower,
        maximum=upper,
        kind=kind,
        unit=unit,
        major_step=major_step,
        minor_step=minor_step,
        minor_divisions=resolved.minor_divisions,
        ticks=tuple(ticks),
        minimum_label_spacing_px=minimum_label_spacing,
    )


def visible_vertical_ruler_ticks(
    layout: VerticalRulerLayout,
    settings: VerticalRulerTrackSettings,
) -> tuple[VerticalRulerTick, ...]:
    """Return a per-track subset of the shared tick sequence."""

    if settings.mode is VerticalRulerMode.OFF:
        return ()

    visible: list[VerticalRulerTick] = []
    for tick in layout.ticks:
        if tick.major:
            index = tick.major_index or 0
            if index % settings.major_tick_every != 0:
                continue
            label = tick.label
            if settings.mode is VerticalRulerMode.TICKS_ONLY:
                label = ""
            elif index % settings.label_every_major != 0:
                label = ""
            visible.append(
                VerticalRulerTick(
                    value=tick.value,
                    major=True,
                    label=label,
                    major_index=tick.major_index,
                )
            )
            continue

        index = tick.minor_index or 0
        if index % settings.minor_tick_every == 0:
            visible.append(tick)
    return tuple(visible)


def vertical_ruler_presentation(
    layout: VerticalRulerLayout,
    *,
    track_kind: str,
    track_width: int,
    settings: VerticalRulerTrackSettings | None = None,
    force_labels: bool = False,
) -> VerticalRulerPresentation:
    """Resolve track-local visibility while retaining the shared tick contract."""

    resolved = settings or VerticalRulerTrackSettings()
    normalized_kind = str(track_kind).strip().casefold()
    show_axis = normalized_kind == "depth" or supports_inner_vertical_ruler(normalized_kind)
    if resolved.mode is VerticalRulerMode.OFF:
        show_axis = False
    if not show_axis:
        return VerticalRulerPresentation(False, False, 0, 0)

    width = max(1, int(track_width))
    if force_labels or resolved.mode is VerticalRulerMode.LABELS_AND_TICKS:
        show_labels = True
    elif resolved.mode is VerticalRulerMode.TICKS_ONLY:
        show_labels = False
    else:
        threshold = (
            144
            if layout.kind is VerticalRulerKind.DATETIME
            else 112
            if layout.kind is VerticalRulerKind.RELATIVE_TIME
            else 92
        )
        show_labels = width >= threshold

    preferred_width = (
        86
        if layout.kind is VerticalRulerKind.DATETIME
        else 66
        if layout.kind is VerticalRulerKind.RELATIVE_TIME
        else 44
    )
    axis_width = min(max(10, width - 24), preferred_width) if show_labels else 10
    return VerticalRulerPresentation(
        show_axis=True,
        show_labels=show_labels,
        axis_width=axis_width,
        tick_length=-6 if show_labels else -5,
        label_every_major=resolved.label_every_major,
        major_tick_every=resolved.major_tick_every,
        minor_tick_every=resolved.minor_tick_every,
    )
