from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogTemplate,
)
from geoworkbench.forms.models import FormAxisKind, FormDocument, FormTrack, ParameterBinding
from geoworkbench.printing.header_fields import header_field_defaults
from geoworkbench.printing.masterlog_presets import builtin_header_preset
from geoworkbench.tablet.models import TrackKind, XScale


FORM_MASTERLOG_BRIDGE_VERSION = 1
DEFAULT_PRINTABLE_WIDTH_MM = 260.0
_MIN_COLUMN_WIDTH_MM = 10.0


class FormMasterlogBridgeError(ValueError):
    """Raised when a screen form cannot be represented as a printable Masterlog."""


@dataclass(frozen=True, slots=True)
class FormMasterlogBridgeReport:
    template: MasterlogTemplate
    column_count: int
    curve_count: int
    skipped_track_ids: tuple[str, ...]


def build_masterlog_from_form(
    form: FormDocument,
    *,
    template_id: str,
    name: str | None = None,
    existing_template: MasterlogTemplate | None = None,
    printable_width_mm: float = DEFAULT_PRINTABLE_WIDTH_MM,
    header_preset_id: str = "geological_geochemical",
) -> FormMasterlogBridgeReport:
    """Create or synchronize a printable Masterlog from one depth screen form.

    The screen form remains the source of truth for column order, captions, bindings,
    scales, grids and curve styles.  Existing report header elements, page settings,
    editable header fields and image references are preserved during synchronization.
    """

    if form.axis_kind is not FormAxisKind.DEPTH:
        raise FormMasterlogBridgeError(
            "Печатный Masterlog можно связать только с глубинной формой"
        )
    if not isinstance(template_id, str) or not template_id.strip():
        raise FormMasterlogBridgeError("ID печатного шаблона не может быть пустым")
    if (
        isinstance(printable_width_mm, bool)
        or not isinstance(printable_width_mm, (int, float))
        or not isfinite(printable_width_mm)
        or not 80.0 <= float(printable_width_mm) <= 2000.0
    ):
        raise FormMasterlogBridgeError("Ширина печатной области должна быть от 80 до 2000 мм")

    tracks = list(_visible_tracks(form))
    if not tracks:
        raise FormMasterlogBridgeError("Форма не содержит видимых дорожек")

    widths = _scaled_widths(tracks, float(printable_width_mm))
    columns: list[MasterlogColumnTemplate] = []
    skipped: list[str] = []
    curve_count = 0
    for (column, track), width_mm in zip(tracks, widths, strict=True):
        converted = _column_from_track(form, column, track, width_mm)
        if converted is None:
            skipped.append(track.track_id)
            continue
        columns.append(converted)
        curve_count += len(converted.curve_mnemonics)

    if not columns:
        raise FormMasterlogBridgeError("Ни одну дорожку формы нельзя вывести в Masterlog")

    if existing_template is None:
        header = builtin_header_preset(header_preset_id)
        template = MasterlogTemplate(
            template_id=template_id.strip(),
            name=(name or form.name).strip(),
            page_format="roll",
            depth_scale=500,
            header_height_mm=header.height_mm,
            header_elements=list(deepcopy(header.elements)),
            columns=columns,
            properties={
                "header_fields": header_field_defaults(),
                "header_preset_origin": header.preset_id,
            },
            version=1,
        )
    else:
        template = deepcopy(existing_template)
        template.template_id = template_id.strip()
        template.name = (name or existing_template.name or form.name).strip()
        template.columns = columns
        template.version += 1

    template.properties.update(
        {
            "linked_form_id": form.form_id,
            "linked_form_name": form.name,
            "linked_form_style_id": form.style_id,
            "form_masterlog_bridge_version": FORM_MASTERLOG_BRIDGE_VERSION,
            "screen_form_is_source_of_truth": True,
            "printable_width_mm": float(printable_width_mm),
        }
    )
    return FormMasterlogBridgeReport(template, len(columns), curve_count, tuple(skipped))


def _visible_tracks(form: FormDocument) -> Iterable[tuple[object, FormTrack]]:
    for column in form.columns:
        if not column.visible:
            continue
        for track in column.tracks:
            if track.visible:
                yield column, track


def _scaled_widths(
    tracks: list[tuple[object, FormTrack]], printable_width_mm: float
) -> tuple[float, ...]:
    weights = [max(80.0, float(getattr(column, "width", 260))) for column, _ in tracks]
    total = sum(weights)
    raw = [printable_width_mm * value / total for value in weights]
    if all(value >= _MIN_COLUMN_WIDTH_MM for value in raw):
        return tuple(raw)

    fixed = [value < _MIN_COLUMN_WIDTH_MM for value in raw]
    fixed_total = sum(_MIN_COLUMN_WIDTH_MM for value in raw if value < _MIN_COLUMN_WIDTH_MM)
    flexible_weight = sum(weight for weight, is_fixed in zip(weights, fixed, strict=True) if not is_fixed)
    remaining = max(0.0, printable_width_mm - fixed_total)
    result: list[float] = []
    for weight, is_fixed in zip(weights, fixed, strict=True):
        if is_fixed or flexible_weight <= 0.0:
            result.append(_MIN_COLUMN_WIDTH_MM)
        else:
            result.append(max(_MIN_COLUMN_WIDTH_MM, remaining * weight / flexible_weight))
    return tuple(result)


def _column_from_track(
    form: FormDocument,
    form_column: object,
    track: FormTrack,
    width_mm: float,
) -> MasterlogColumnTemplate | None:
    column_type = _masterlog_column_type(track.kind)
    if column_type is None:
        return None

    visible_bindings = [binding for binding in track.bindings if binding.visible]
    mnemonics = [_binding_mnemonic(binding) for binding in visible_bindings]
    styles = {
        mnemonic: MasterlogCurveStyle(
            color=binding.style.color,
            width=binding.style.width,
            line_style=binding.style.line_style.value,
            x_min=binding.x_min,
            x_max=binding.x_max,
        )
        for binding, mnemonic in zip(visible_bindings, mnemonics, strict=True)
    }
    x_scale = _common_scale(visible_bindings)
    x_min, x_max = _common_range(visible_bindings)
    first = visible_bindings[0] if visible_bindings else None
    properties = {
        "linked_form_id": form.form_id,
        "linked_form_column_id": str(getattr(form_column, "column_id", "")),
        "linked_form_track_id": track.track_id,
        "group_title": str(getattr(form_column, "group_title", "")),
        "display_names": {
            mnemonic: binding.display_name
            for binding, mnemonic in zip(visible_bindings, mnemonics, strict=True)
        },
        "display_units": {
            mnemonic: binding.unit
            for binding, mnemonic in zip(visible_bindings, mnemonics, strict=True)
            if binding.unit
        },
        "canonical_parameters": {
            mnemonic: binding.canonical_parameter_id
            for binding, mnemonic in zip(visible_bindings, mnemonics, strict=True)
        },
        "x_axis_label": track.x_axis_label,
        "title_orientation": track.title_orientation,
        "title_position": track.title_position,
        "show_interval_labels": track.show_interval_labels,
    }
    if track.kind is TrackKind.TEXT:
        properties["text_source"] = "cuttings_description"

    return MasterlogColumnTemplate(
        column_id=track.track_id,
        title=track.title or str(getattr(form_column, "title", "")),
        column_type=column_type,
        width_mm=float(width_mm),
        curve_mnemonics=mnemonics if column_type == "curves" else [],
        properties=properties,
        x_scale=x_scale.value,
        x_min=x_min,
        x_max=x_max,
        show_legend=True,
        line_color=first.style.color if first is not None else "#2563eb",
        line_width=first.style.width if first is not None else 1.5,
        line_style=first.style.line_style.value if first is not None else "solid",
        curve_styles=styles if column_type == "curves" else {},
        grid_x=track.grid_x,
        grid_y=track.grid_y,
        grid_major_divisions=5,
        grid_minor_divisions=5,
        grid_alpha=track.grid_alpha,
    )


def _masterlog_column_type(kind: TrackKind) -> str | None:
    return {
        TrackKind.DEPTH: "depth",
        TrackKind.CURVE: "curves",
        TrackKind.GAS: "curves",
        TrackKind.DEXP: "curves",
        TrackKind.STRATIGRAPHY: "stratigraphy",
        TrackKind.LITHOLOGY: "lithology",
        TrackKind.CUTTINGS: "cuttings",
        TrackKind.CALCIMETRY: "calcimetry",
        TrackKind.LBA: "lba",
        TrackKind.INTERPRETATION: "analysis_interpretation",
        TrackKind.TEXT: "cuttings_description",
    }.get(kind)


def _binding_mnemonic(binding: ParameterBinding) -> str:
    return (binding.source_mnemonic or binding.canonical_parameter_id).strip()


def _common_scale(bindings: list[ParameterBinding]) -> XScale:
    if not bindings:
        return XScale.LINEAR
    first = bindings[0].x_scale
    return first if all(binding.x_scale is first for binding in bindings) else XScale.LINEAR


def _common_range(bindings: list[ParameterBinding]) -> tuple[float | None, float | None]:
    if not bindings:
        return None, None
    first = (bindings[0].x_min, bindings[0].x_max)
    if first[0] is None or first[1] is None:
        return None, None
    if all((binding.x_min, binding.x_max) == first for binding in bindings):
        return first
    return None, None
