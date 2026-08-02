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

    Compact geology/reference columns may use their 48 px minimum. Curve and
    text columns keep the larger minimum defined by their track kinds. Remaining
    width is distributed proportionally to each column's current extra width.
    Hidden columns are left untouched.
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

    minima = [
        minimum_width_for_track_kinds(track.kind for track in column.tracks)
        for column in visible
    ]
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
    extra_budget = width_budget - minimum_total
    extra_total = sum(extras)
    if extra_total <= 0:
        allocated = minima[:]
    else:
        allocated = [
            minimum + int(extra_budget * extra / extra_total)
            for minimum, extra in zip(minima, extras, strict=True)
        ]
        remainder = width_budget - sum(allocated)
        order = sorted(
            range(len(visible)),
            key=lambda index: (extras[index], visible[index].width),
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
