from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
import re

from geoworkbench.catalogs.sensors import SensorCatalog, SensorMatch, active_sensor_catalog
from geoworkbench.domain.models import CurveData, Dataset, IndexRole
from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.tablet.models import CurveStyle, TrackKind, XScale

_DYNAMIC_FACTORY_IDS = {"factory-depth-basic", "factory-time-basic"}
_CATEGORY_ORDER = ("drilling", "mud", "gas", "petrophysics", "dexp", "other")
_FALLBACK_COLORS = (
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#ca8a04",
    "#475569",
)

_CATEGORY_TITLES: dict[str, dict[str, str]] = {
    "drilling": {"ru": "Бурение", "kk": "Бұрғылау", "en": "Drilling"},
    "mud": {"ru": "Буровой раствор", "kk": "Бұрғылау ерітіндісі", "en": "Drilling fluid"},
    "gas": {"ru": "Газовые данные", "kk": "Газ деректері", "en": "Gas data"},
    "petrophysics": {"ru": "ГИС и петрофизика", "kk": "ГИС және петрофизика", "en": "Petrophysics"},
    "dexp": {"ru": "D-exponent", "kk": "D-exponent", "en": "D-exponent"},
    "other": {"ru": "Прочие кривые LAS", "kk": "Басқа LAS қисықтары", "en": "Other LAS curves"},
}

_MATERIALIZED_DESCRIPTION: dict[str, str] = {
    "ru": "Рабочая форма автоматически заполнена кривыми текущего LAS-файла. Создайте пользовательскую копию, чтобы изменить названия, состав, шкалы и оформление.",
    "kk": "Жұмыс пішіні ағымдағы LAS файлының қисықтарымен автоматты түрде толтырылды. Атауларды, құрамды, шкалаларды және безендіруді өзгерту үшін пайдаланушы көшірмесін жасаңыз.",
    "en": "The working form was populated automatically from the current LAS file. Create a user copy to edit names, contents, scales, and styling.",
}

_NO_COMPATIBLE_AXIS: dict[str, str] = {
    "ru": "В текущем наборе данных нет подходящей оси для этой формы.",
    "kk": "Ағымдағы деректер жинағында бұл пішінге сәйкес ось жоқ.",
    "en": "The current dataset has no compatible axis for this form.",
}


@dataclass(frozen=True, slots=True)
class MaterializedFormInfo:
    form: FormDocument
    generated_binding_count: int
    compatible_axis: bool


def materialized_factory_templates(
    dataset: Dataset | None,
    language: str = "ru",
    *,
    catalog: SensorCatalog | None = None,
    max_bindings_per_column: int = 4,
) -> dict[str, FormDocument]:
    """Return factory templates adapted to the currently opened dataset.

    Factory IDs remain stable. Only the two generic LAS forms are materialized;
    specialised Gas Ratio/Pixler forms retain their canonical bindings.
    """

    from geoworkbench.forms.templates import factory_templates

    templates = factory_templates(language)
    return {
        form_id: materialize_form_for_dataset(
            form,
            dataset,
            language,
            catalog=catalog,
            max_bindings_per_column=max_bindings_per_column,
        ).form
        for form_id, form in templates.items()
    }


def materialize_form_for_dataset(
    form: FormDocument,
    dataset: Dataset | None,
    language: str = "ru",
    *,
    catalog: SensorCatalog | None = None,
    max_bindings_per_column: int = 4,
) -> MaterializedFormInfo:
    """Create a dataset-specific copy of a generic factory form.

    Empty generic forms are not useful to a geologist: the user expects a base
    template to show the opened LAS curves immediately. This function replaces
    the empty curve column with readable, editable bindings grouped into compact
    columns. The source form and dataset are never modified.
    """

    result = deepcopy(form)
    if result.form_id not in _DYNAMIC_FACTORY_IDS or dataset is None:
        return MaterializedFormInfo(result, 0, _has_compatible_axis(result, dataset))
    existing_bindings = [
        binding
        for column in result.columns
        if column.column_id.startswith("column-auto-")
        for track in column.tracks
        for binding in track.bindings
    ]
    if existing_bindings and all(
        binding.source_mnemonic and dataset.curve_by_mnemonic(binding.source_mnemonic) is not None
        for binding in existing_bindings
    ):
        return MaterializedFormInfo(
            result, len(existing_bindings), _has_compatible_axis(result, dataset)
        )
    if max_bindings_per_column < 1:
        raise ValueError("max_bindings_per_column должен быть не меньше 1")

    compatible = _has_compatible_axis(result, dataset)
    if not compatible:
        result.description = _localized(_NO_COMPATIBLE_AXIS, language)
        return MaterializedFormInfo(result, 0, False)

    catalog = catalog or active_sensor_catalog()
    grouped: dict[str, list[ParameterBinding]] = defaultdict(list)
    for position, curve in enumerate(dataset.curves.values()):
        match = catalog.match(
            curve.metadata.original_mnemonic,
            description=curve.metadata.description or "",
            unit=curve.metadata.unit or "",
        )
        category = match.definition.category if match is not None else "other"
        if category not in _CATEGORY_TITLES:
            category = "other"
        grouped[category].append(_binding_from_curve(curve, position, language, match=match))

    axis_columns = [
        column
        for column in result.columns
        if any(track.kind is TrackKind.DEPTH for track in column.tracks)
    ]
    generated_columns: list[FormColumn] = []
    for category in _CATEGORY_ORDER:
        bindings = grouped.get(category, [])
        if not bindings:
            continue
        chunks = [
            bindings[index : index + max_bindings_per_column]
            for index in range(0, len(bindings), max_bindings_per_column)
        ]
        base_title = _localized(_CATEGORY_TITLES[category], language)
        for chunk_index, chunk in enumerate(chunks, start=1):
            title = base_title if len(chunks) == 1 else f"{base_title} {chunk_index}"
            suffix = f"{category}-{chunk_index}"
            generated_columns.append(
                FormColumn(
                    column_id=f"column-auto-{suffix}",
                    title=title,
                    width=max(260, min(420, 180 + len(chunk) * 45)),
                    tracks=[
                        FormTrack(
                            track_id=f"track-auto-{suffix}",
                            title=title,
                            kind=TrackKind.CURVE,
                            bindings=chunk,
                        )
                    ],
                )
            )

    result.columns = [*axis_columns, *generated_columns]
    result.description = _localized(_MATERIALIZED_DESCRIPTION, language)
    result.validate()
    return MaterializedFormInfo(
        result,
        sum(len(track.bindings) for column in generated_columns for track in column.tracks),
        True,
    )


def _binding_from_curve(
    curve: CurveData,
    position: int,
    language: str,
    *,
    match: SensorMatch | None,
) -> ParameterBinding:
    metadata = curve.metadata
    canonical = (
        match.definition.canonical_mnemonic
        if match is not None
        else metadata.canonical_mnemonic or metadata.original_mnemonic
    )
    display_name = _curve_display_name(curve, language, match=match)
    color = (
        match.definition.color
        if match is not None
        else _FALLBACK_COLORS[position % len(_FALLBACK_COLORS)]
    )
    minimum = match.definition.default_min if match is not None else None
    maximum = match.definition.default_max if match is not None else None
    minimum, maximum = _safe_default_range(minimum, maximum)
    # Dataset-driven working forms always begin with a linear engineering
    # scale.  Logarithmic display remains available as an explicit saved setting.
    scale = XScale.LINEAR
    stable_part = _safe_id(metadata.curve_id or metadata.original_mnemonic)
    return ParameterBinding(
        binding_id=f"binding-auto-{position}-{stable_part}",
        canonical_parameter_id=_safe_id(canonical),
        display_name=display_name,
        source_mnemonic=metadata.original_mnemonic,
        unit=metadata.unit or (match.definition.unit if match is not None else ""),
        style=CurveStyle(color=color, width=1.5),
        x_scale=scale,
        x_min=minimum,
        x_max=maximum,
    )


def _safe_default_range(
    minimum: float | None, maximum: float | None
) -> tuple[float | None, float | None]:
    """Return a valid manual X range or request autoscale.

    Legacy sensor catalogs may contain placeholder ranges such as ``0 .. 0``.
    Such values are metadata, not a usable plotting interval.  A single broken
    catalog entry must never prevent the form manager from opening, therefore
    invalid, incomplete and non-finite ranges are converted to autoscale.
    """

    if minimum is None or maximum is None:
        return None, None
    if not isfinite(minimum) or not isfinite(maximum):
        return None, None
    if minimum >= maximum:
        return None, None
    return float(minimum), float(maximum)


def _curve_display_name(
    curve: CurveData,
    language: str,
    *,
    match: SensorMatch | None,
) -> str:
    metadata = curve.metadata
    description = (metadata.description or "").strip()
    if description and description.casefold() not in {
        metadata.original_mnemonic.casefold(),
        (metadata.canonical_mnemonic or "").casefold(),
    }:
        return description[:120]
    if match is not None and language == "ru":
        return (match.definition.name_ru or match.definition.short_name_ru)[:120]
    return (metadata.canonical_mnemonic or metadata.original_mnemonic)[:120]


def _has_compatible_axis(form: FormDocument, dataset: Dataset | None) -> bool:
    if dataset is None:
        return False
    wanted = IndexRole.DEPTH if form.axis_kind is FormAxisKind.DEPTH else IndexRole.TIME
    return any(index.role is wanted for index in dataset.indexes.values())


def _localized(values: dict[str, str], language: str) -> str:
    return values.get(language, values["ru"])


def _safe_id(value: str) -> str:
    normalized = re.sub(r"[^\w.:-]+", "_", value.strip(), flags=re.UNICODE)
    return normalized[:120] or "curve"
