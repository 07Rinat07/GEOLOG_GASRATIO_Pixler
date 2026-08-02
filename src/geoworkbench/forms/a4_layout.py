from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.forms.models import FormDocument, FormPageOrientation
from geoworkbench.printing.form_width_advisor import audit_form_width
from geoworkbench.tablet.models import (
    COMPACT_TRACK_KINDS,
    compact_track_title_orientation,
    compact_track_title_position,
    minimum_width_for_track_kinds,
)


class A4FitError(ValueError):
    """Raised when a form cannot be fitted without violating column minima."""


@dataclass(frozen=True, slots=True)
class A4FitResult:
    orientation: FormPageOrientation
    capacity_px: int
    previous_width_px: int
    fitted_width_px: int
    changed_columns: int

    @property
    def changed(self) -> bool:
        return self.changed_columns > 0

    @property
    def scale_percent(self) -> float:
        if self.previous_width_px <= 0:
            return 100.0
        return min(100.0, self.fitted_width_px / self.previous_width_px * 100.0)


def _orientation(value: FormPageOrientation | str) -> FormPageOrientation:
    raw = getattr(value, "value", value)
    return FormPageOrientation(str(raw))


def a4_capacity_px(orientation: FormPageOrientation | str) -> int:
    normalized = _orientation(orientation)
    audit = audit_form_width(())
    return (
        audit.portrait_capacity_px
        if normalized is FormPageOrientation.PORTRAIT
        else audit.landscape_capacity_px
    )


def form_fits_a4(
    form: FormDocument,
    orientation: FormPageOrientation | str | None = None,
) -> bool:
    target = _orientation(orientation or form.preferred_page_orientation)
    audit = audit_form_width(
        column.width if column.visible else 0 for column in form.columns
    )
    capacity = (
        audit.portrait_capacity_px
        if target is FormPageOrientation.PORTRAIT
        else audit.landscape_capacity_px
    )
    return audit.total_width_px <= capacity


def fit_form_to_a4(
    form: FormDocument,
    orientation: FormPageOrientation | str | None = None,
) -> A4FitResult:
    """Fit visible columns into one A4 width while preserving useful minima.

    Geology/reference columns are compressed to their safe minimum first. The
    remaining width is distributed among graph and text columns, so depth,
    stratigraphy, lithology, cuttings, calcimetry and LBA do not consume space
    required for readable parameter curves. Hidden columns remain unchanged.
    """

    target = _orientation(orientation or form.preferred_page_orientation)
    form.preferred_page_orientation = target
    visible = [column for column in form.columns if column.visible]
    spacing = 2
    previous_width = sum(column.width for column in visible) + spacing * max(
        0, len(visible) - 1
    )
    capacity = a4_capacity_px(target)
    if not visible or previous_width <= capacity:
        _apply_compact_caption_defaults(form)
        form.validate()
        return A4FitResult(target, capacity, previous_width, previous_width, 0)

    kinds_by_column = [tuple(track.kind for track in column.tracks) for column in visible]
    compact = [
        bool(kinds) and all(kind in COMPACT_TRACK_KINDS for kind in kinds)
        for kinds in kinds_by_column
    ]
    minima = [minimum_width_for_track_kinds(kinds) for kinds in kinds_by_column]
    width_budget = capacity - spacing * max(0, len(visible) - 1)
    minimum_total = sum(minima)
    if minimum_total > width_budget:
        raise A4FitError(
            "Колонки не помещаются в выбранный A4 даже при минимальной ширине. "
            "Скройте второстепенные колонки или выберите альбомную ориентацию."
        )

    extras = [
        max(0, column.width - minimum)
        for column, minimum in zip(visible, minima, strict=True)
    ]
    # Compact geology columns stay at minimum whenever at least one ordinary
    # graph/text column can receive the available width.
    weights = [0 if is_compact else extra for is_compact, extra in zip(compact, extras, strict=True)]
    if sum(weights) <= 0:
        weights = extras
    extra_budget = width_budget - minimum_total
    weight_total = sum(weights)
    if weight_total <= 0:
        allocated = minima[:]
    else:
        allocated = [
            minimum + int(extra_budget * weight / weight_total)
            for minimum, weight in zip(minima, weights, strict=True)
        ]
        remainder = width_budget - sum(allocated)
        order = sorted(
            (index for index, weight in enumerate(weights) if weight > 0),
            key=lambda index: (weights[index], visible[index].width),
            reverse=True,
        )
        for offset in range(remainder):
            allocated[order[offset % len(order)]] += 1

    changed = 0
    for column, width in zip(visible, allocated, strict=True):
        if column.width != width:
            column.width = width
            changed += 1
    _apply_compact_caption_defaults(form)
    form.validate()
    fitted_width = sum(column.width for column in visible) + spacing * max(
        0, len(visible) - 1
    )
    return A4FitResult(target, capacity, previous_width, fitted_width, changed)


def _apply_compact_caption_defaults(form: FormDocument) -> None:
    for column in form.columns:
        kinds = [track.kind for track in column.tracks]
        if not kinds or column.width > 72:
            continue
        if not all(kind in COMPACT_TRACK_KINDS for kind in kinds):
            continue
        orientation = compact_track_title_orientation(kinds[0])
        position = compact_track_title_position(kinds[0])
        column.title_orientation = orientation
        column.title_position = position
        for track in column.tracks:
            track.title_orientation = compact_track_title_orientation(track.kind)
            track.title_position = compact_track_title_position(track.kind)
