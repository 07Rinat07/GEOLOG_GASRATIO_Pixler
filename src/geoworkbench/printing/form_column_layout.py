from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from geoworkbench.tablet.models import TrackDefinition, TrackKind


_DEFAULT_SPACING_PX = 2


@dataclass(frozen=True, slots=True)
class AdaptiveColumnLayout:
    """Print-only column widths for one tablet page.

    The widths are logical Qt pixels.  The renderer applies one common scale to
    all columns, therefore text, line widths and curve geometry keep identical
    proportions across the printed page.
    """

    widths: tuple[int, ...]
    spacing: int = _DEFAULT_SPACING_PX

    def __post_init__(self) -> None:
        if not self.widths or any(width < 80 for width in self.widths):
            raise ValueError("Печатная ширина каждой колонки должна быть не меньше 80 px")
        if self.spacing < 0:
            raise ValueError("Интервал между колонками не может быть отрицательным")

    @property
    def total_width(self) -> int:
        return sum(self.widths) + self.spacing * max(0, len(self.widths) - 1)


def adaptive_column_layout(
    tracks: Sequence[TrackDefinition],
    *,
    page_aspect_ratio: float,
    content_height: int,
    spacing: int = _DEFAULT_SPACING_PX,
) -> AdaptiveColumnLayout:
    """Fit every visible form column to one portrait/landscape page width.

    The available logical width is derived from the paper aspect ratio and the
    current chart height.  Very wide screen tracks are capped before the extra
    width is distributed, so one track cannot consume most of an A4 page.
    Minimum readable widths are preserved.  When a portrait page contains too
    many columns, the renderer scales the complete balanced layout uniformly;
    it never clips or silently omits a track.
    """

    visible = [track for track in tracks if track.visible]
    if not visible:
        raise ValueError("Нет видимых колонок для печати")
    if (
        isinstance(page_aspect_ratio, bool)
        or not isinstance(page_aspect_ratio, (int, float))
        or not isfinite(page_aspect_ratio)
        or page_aspect_ratio <= 0
    ):
        raise ValueError("Соотношение сторон страницы должно быть положительным")
    if (
        isinstance(content_height, bool)
        or not isinstance(content_height, int)
        or content_height <= 0
    ):
        raise ValueError("Высота печатного содержимого должна быть положительной")
    if spacing < 0:
        raise ValueError("Интервал между колонками не может быть отрицательным")

    minimums = [_minimum_width(track.kind) for track in visible]
    preferred = [
        max(minimum, min(_preferred_cap(track.kind), int(track.width)))
        for track, minimum in zip(visible, minimums, strict=True)
    ]
    gaps = spacing * max(0, len(visible) - 1)
    nominal_width = max(1, round(content_height * float(page_aspect_ratio)))
    target_columns_width = max(sum(minimums), nominal_width - gaps)
    widths = _distribute_width(target_columns_width, minimums, preferred)
    return AdaptiveColumnLayout(tuple(widths), spacing)


def original_column_layout(
    tracks: Sequence[TrackDefinition], *, spacing: int = _DEFAULT_SPACING_PX
) -> AdaptiveColumnLayout:
    visible = [track for track in tracks if track.visible]
    if not visible:
        raise ValueError("Нет видимых колонок для печати")
    return AdaptiveColumnLayout(
        tuple(max(80, min(2000, int(track.width))) for track in visible),
        spacing,
    )


def _minimum_width(kind: TrackKind) -> int:
    if kind is TrackKind.DEPTH:
        return 96
    if kind in {TrackKind.LITHOLOGY, TrackKind.CUTTINGS, TrackKind.CALCIMETRY}:
        return 104
    if kind in {TrackKind.STRATIGRAPHY, TrackKind.INTERPRETATION, TrackKind.TEXT}:
        return 112
    return 120


def _preferred_cap(kind: TrackKind) -> int:
    if kind is TrackKind.DEPTH:
        return 140
    if kind in {TrackKind.LITHOLOGY, TrackKind.CUTTINGS, TrackKind.CALCIMETRY}:
        return 220
    if kind in {TrackKind.STRATIGRAPHY, TrackKind.INTERPRETATION, TrackKind.TEXT}:
        return 280
    return 320


def _distribute_width(target: int, minimums: Sequence[int], preferred: Sequence[int]) -> list[int]:
    widths = list(minimums)
    remaining = target - sum(widths)
    if remaining <= 0:
        return widths

    demands = [
        max(0, wanted - minimum) for minimum, wanted in zip(minimums, preferred, strict=True)
    ]
    demand_total = sum(demands)
    if demand_total:
        granted = min(remaining, demand_total)
        additions = _proportional_integers(granted, demands)
        widths = [width + addition for width, addition in zip(widths, additions, strict=True)]
        remaining -= granted

    if remaining > 0:
        # Once all preferred widths are reached, use the original capped widths
        # as weights.  This fills landscape pages without creating empty bands.
        additions = _proportional_integers(remaining, preferred)
        widths = [width + addition for width, addition in zip(widths, additions, strict=True)]
    return widths


def _proportional_integers(total: int, weights: Sequence[int]) -> list[int]:
    if total <= 0:
        return [0] * len(weights)
    weight_total = sum(max(0, weight) for weight in weights)
    if weight_total <= 0:
        base, remainder = divmod(total, len(weights))
        return [base + (1 if index < remainder else 0) for index in range(len(weights))]

    raw = [total * max(0, weight) / weight_total for weight in weights]
    result = [int(value) for value in raw]
    remainder = total - sum(result)
    order = sorted(
        range(len(raw)),
        key=lambda index: (raw[index] - result[index], weights[index]),
        reverse=True,
    )
    for index in order[:remainder]:
        result[index] += 1
    return result
