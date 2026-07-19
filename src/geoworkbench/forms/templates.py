from __future__ import annotations

from copy import deepcopy

from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTemplateOrigin,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.tablet.models import CurveStyle, TrackKind, XScale


def factory_templates() -> dict[str, FormDocument]:
    templates = {
        "factory-depth-basic": _basic_depth(),
        "factory-time-basic": _basic_time(),
        "factory-gas-components": _gas_components(),
        "factory-gas-ratio": _gas_ratio(),
        "factory-pixler": _pixler(),
        "factory-interpretation": _interpretation(),
    }
    return {key: deepcopy(value) for key, value in templates.items()}


def _factory(form_id: str, name: str, axis: FormAxisKind, columns: list[FormColumn]) -> FormDocument:
    return FormDocument(
        form_id=form_id,
        name=name,
        axis_kind=axis,
        columns=columns,
        description="Заводской шаблон GEOLOG Gas Ratio & Pixler",
        origin=FormTemplateOrigin.FACTORY,
        read_only=True,
    )


def _axis_column(axis: FormAxisKind) -> FormColumn:
    title = "Глубина" if axis is FormAxisKind.DEPTH else "Время"
    return FormColumn(
        column_id=f"column-{axis.value}-axis",
        title=title,
        width=120,
        locked=True,
        tracks=[
            FormTrack(
                track_id=f"track-{axis.value}-axis",
                title=title,
                kind=TrackKind.DEPTH,
                locked=True,
                x_axis_label="MD" if axis is FormAxisKind.DEPTH else "TIME",
            )
        ],
    )


def _curve_column(column_id: str, title: str, bindings: list[ParameterBinding], width: int = 260) -> FormColumn:
    return FormColumn(
        column_id=column_id,
        title=title,
        width=width,
        tracks=[FormTrack(track_id=f"track-{column_id}", title=title, kind=TrackKind.CURVE, bindings=bindings)],
    )


def _binding(code: str, name: str, unit: str = "", color: str = "#2563eb", *, log: bool = False) -> ParameterBinding:
    return ParameterBinding(
        binding_id=f"binding-{code.lower().replace('_', '-')}",
        canonical_parameter_id=code,
        display_name=name,
        unit=unit,
        style=CurveStyle(color=color),
        x_scale=XScale.LOGARITHMIC if log else XScale.LINEAR,
    )


def _basic_depth() -> FormDocument:
    return _factory(
        "factory-depth-basic",
        "Базовая глубинная форма",
        FormAxisKind.DEPTH,
        [_axis_column(FormAxisKind.DEPTH), _curve_column("column-curves", "Кривые", [])],
    )


def _basic_time() -> FormDocument:
    return _factory(
        "factory-time-basic",
        "Базовая временная форма",
        FormAxisKind.TIME,
        [_axis_column(FormAxisKind.TIME), _curve_column("column-time-curves", "Кривые", [])],
    )


def _gas_components() -> FormDocument:
    gases = [
        _binding("TOTAL_GAS", "Total Gas", "%", "#dc2626"),
        _binding("C1", "Метан C1", "ppm", "#2563eb"),
        _binding("C2", "Этан C2", "ppm", "#16a34a"),
        _binding("C3", "Пропан C3", "ppm", "#9333ea"),
        _binding("IC4", "Изобутан iC4", "ppm", "#ea580c"),
        _binding("NC4", "Бутан nC4", "ppm", "#ca8a04"),
        _binding("IC5", "Изопентан iC5", "ppm", "#0891b2"),
        _binding("NC5", "Пентан nC5", "ppm", "#475569"),
    ]
    return _factory(
        "factory-gas-components",
        "Газовые компоненты C1–C5",
        FormAxisKind.DEPTH,
        [_axis_column(FormAxisKind.DEPTH), _curve_column("column-gases", "Газ C1–C5", gases, 420)],
    )


def _gas_ratio() -> FormDocument:
    return _factory(
        "factory-gas-ratio",
        "Gas Ratio",
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH),
            _curve_column("column-rop", "ROP", [_binding("ROP", "Механическая скорость", "m/h", "#111827")]),
            _curve_column(
                "column-total-gas",
                "Total Gas",
                [
                    _binding("TOTAL_GAS", "Total Gas", "%", "#dc2626"),
                    _binding("NORMALIZED_TOTAL_GAS", "Нормализованный газ", "%", "#7c3aed"),
                ],
            ),
            _curve_column(
                "column-gas-ratios",
                "Gas Ratio",
                [
                    _binding("WETNESS", "Wetness", "", "#0f766e"),
                    _binding("BALANCE", "Balance", "", "#b45309"),
                    _binding("CHARACTER", "Character", "", "#be123c"),
                ],
                320,
            ),
        ],
    )


def _pixler() -> FormDocument:
    return _factory(
        "factory-pixler",
        "Pixler",
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH),
            _curve_column(
                "column-pixler",
                "Pixler ratios",
                [
                    _binding("PIXLER_C1_C2", "C1/C2", "", "#2563eb", log=True),
                    _binding("PIXLER_C1_C3", "C1/C3", "", "#16a34a", log=True),
                    _binding("PIXLER_C1_C4", "C1/C4", "", "#ea580c", log=True),
                    _binding("PIXLER_C1_C5", "C1/C5", "", "#9333ea", log=True),
                ],
                360,
            ),
        ],
    )


def _interpretation() -> FormDocument:
    return _factory(
        "factory-interpretation",
        "Интерпретация",
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH),
            _curve_column("column-total-gas", "Total Gas", [_binding("TOTAL_GAS", "Total Gas", "%", "#dc2626")]),
            FormColumn(
                column_id="column-interpretation",
                title="Интерпретация",
                width=320,
                tracks=[
                    FormTrack(
                        track_id="track-interpretation",
                        title="Интервалы и комментарии",
                        kind=TrackKind.INTERPRETATION,
                    )
                ],
            ),
        ],
    )
