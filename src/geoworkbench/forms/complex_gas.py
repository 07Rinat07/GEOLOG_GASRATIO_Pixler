from __future__ import annotations

from typing import Literal

from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTemplateOrigin,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.tablet.models import (
    CurveStyle,
    TrackKind,
    XScale,
    compact_track_title_orientation,
    compact_track_title_position,
)


TemplateLanguage = Literal["ru", "kk", "en"]


_TEXT: dict[str, dict[TemplateLanguage, str]] = {
    "form_name": {
        "ru": "Комплексная газовая форма",
        "kk": "Кешенді газдық пішін",
        "en": "Integrated gas analysis",
    },
    "description": {
        "ru": (
            "Абсолютные, относительные и нормализованные компоненты C1–C5, "
            "суммарный газ, коэффициенты Haworth, изомерные отношения и Pixler. "
            "Каждая графическая колонка снабжена собственной синхронной шкалой глубины."
        ),
        "kk": (
            "C1–C5 абсолюттік, салыстырмалы және нормаланған компоненттері, жалпы газ, "
            "Haworth коэффициенттері, изомерлік қатынастар және Pixler. Әр графикалық "
            "бағанда синхрондалған жеке тереңдік шкаласы бар."
        ),
        "en": (
            "Absolute, relative and normalized C1–C5 components, total gas, Haworth "
            "indices, isomer ratios and Pixler ratios. Every graph column has its own "
            "synchronized internal depth scale."
        ),
    },
    "gas_group": {"ru": "Газовые данные", "kk": "Газ деректері", "en": "Gas data"},
    "depth": {"ru": "Глубина", "kk": "Тереңдік", "en": "Depth"},
    "absolute": {
        "ru": "Абсолютные компоненты",
        "kk": "Абсолюттік компоненттер",
        "en": "Absolute components",
    },
    "absolute_sum": {
        "ru": "Сумма абсолютных газов",
        "kk": "Абсолюттік газдар қосындысы",
        "en": "Absolute gas sum",
    },
    "normalized_total": {
        "ru": "Нормализованный суммарный газ",
        "kk": "Нормаланған жалпы газ",
        "en": "Normalized total gas",
    },
    "normalized_components": {
        "ru": "Нормализованные компоненты",
        "kk": "Нормаланған компоненттер",
        "en": "Normalized components",
    },
    "relative": {
        "ru": "Относительный газ",
        "kk": "Салыстырмалы газ",
        "en": "Relative gas",
    },
    "ratios": {
        "ru": "Wetness, Balance, Character и изомеры",
        "kk": "Wetness, Balance, Character және изомерлер",
        "en": "Wetness, Balance, Character and isomers",
    },
    "pixler": {
        "ru": "Коэффициенты Pixler",
        "kk": "Pixler коэффициенттері",
        "en": "Pixler ratios",
    },
    "total": {"ru": "Суммарный газ", "kk": "Жалпы газ", "en": "Total gas"},
    "methane": {"ru": "Метан C1", "kk": "Метан C1", "en": "Methane C1"},
    "ethane": {"ru": "Этан C2", "kk": "Этан C2", "en": "Ethane C2"},
    "propane": {"ru": "Пропан C3", "kk": "Пропан C3", "en": "Propane C3"},
    "isobutane": {
        "ru": "Изобутан iC4",
        "kk": "Изобутан iC4",
        "en": "Isobutane iC4",
    },
    "nbutane": {"ru": "Н-бутан nC4", "kk": "Н-бутан nC4", "en": "N-butane nC4"},
    "isopentane": {
        "ru": "Изопентан iC5",
        "kk": "Изопентан iC5",
        "en": "Isopentane iC5",
    },
    "npentane": {"ru": "Н-пентан nC5", "kk": "Н-пентан nC5", "en": "N-pentane nC5"},
    "wetness": {"ru": "Wetness", "kk": "Wetness", "en": "Wetness"},
    "balance": {"ru": "Balance", "kk": "Balance", "en": "Balance"},
    "character": {"ru": "Character", "kk": "Character", "en": "Character"},
}


_COMPONENTS: tuple[tuple[str, str, str], ...] = (
    ("C1", "methane", "#111827"),
    ("C2", "ethane", "#84cc16"),
    ("C3", "propane", "#22d3ee"),
    ("IC4", "isobutane", "#2563eb"),
    ("NC4", "nbutane", "#fb923c"),
    ("IC5", "isopentane", "#d946ef"),
    ("NC5", "npentane", "#9333ea"),
)


def _language(language: str) -> TemplateLanguage:
    return language if language in {"ru", "kk", "en"} else "ru"  # type: ignore[return-value]


def _t(key: str, language: TemplateLanguage) -> str:
    return _TEXT[key][language]


def _binding(
    code: str,
    name: str,
    unit: str,
    color: str,
    *,
    x_scale: XScale = XScale.LINEAR,
    x_min: float | None = None,
    x_max: float | None = None,
    width: float = 1.6,
) -> ParameterBinding:
    return ParameterBinding(
        binding_id=f"binding-complex-{code.lower().replace('_', '-')}",
        canonical_parameter_id=code,
        display_name=name,
        unit=unit,
        style=CurveStyle(color=color, width=width),
        x_scale=x_scale,
        x_min=x_min,
        x_max=x_max,
        header_text_color=color,
        header_line_color=color,
    )


def _component_bindings(
    language: TemplateLanguage,
    *,
    suffix: str = "",
    unit: str,
    x_min: float | None,
    x_max: float | None,
) -> list[ParameterBinding]:
    return [
        _binding(
            f"{code}{suffix}",
            _t(label_key, language),
            unit,
            color,
            x_min=x_min,
            x_max=x_max,
        )
        for code, label_key, color in _COMPONENTS
    ]


def _internal_depth_column(
    language: TemplateLanguage,
    suffix: str,
    group_title: str,
) -> FormColumn:
    title = _t("depth", language)
    return FormColumn(
        column_id=f"column-complex-depth-{suffix}",
        title=title,
        group_title=group_title,
        width=96,
        locked=True,
        title_orientation=compact_track_title_orientation(TrackKind.DEPTH),
        title_position=compact_track_title_position(TrackKind.DEPTH),
        tracks=[
            FormTrack(
                track_id=f"track-complex-depth-{suffix}",
                title=title,
                kind=TrackKind.DEPTH,
                locked=True,
                grid_x=False,
                grid_y=True,
                grid_major_divisions=10,
                grid_minor_divisions=5,
                grid_alpha=0.28,
                grid_print=True,
                x_axis_label="MD",
                title_orientation=compact_track_title_orientation(TrackKind.DEPTH),
                title_position=compact_track_title_position(TrackKind.DEPTH),
                show_interval_labels=True,
            )
        ],
    )


def _curve_column(
    column_id: str,
    title: str,
    bindings: list[ParameterBinding],
    group_title: str,
    *,
    width: int,
    x_axis_label: str,
) -> FormColumn:
    return FormColumn(
        column_id=column_id,
        title=title,
        group_title=group_title,
        width=width,
        tracks=[
            FormTrack(
                track_id=f"track-{column_id}",
                title=title,
                kind=TrackKind.CURVE,
                bindings=bindings,
                grid_x=True,
                grid_y=True,
                grid_major_divisions=5,
                grid_minor_divisions=5,
                grid_alpha=0.22,
                grid_print=True,
                x_axis_label=x_axis_label,
                show_interval_labels=True,
            )
        ],
    )


def _relative_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    return _component_bindings(
        language,
        suffix="_REL",
        unit="% of ΣC1–C5",
        x_min=0.0,
        x_max=100.0,
    )


def _normalized_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    bindings: list[ParameterBinding] = []
    for code, label_key, color in _COMPONENTS:
        normalized_code = "C1_NORM_REF" if code == "C1" else f"{code}_NORM"
        bindings.append(
            _binding(
                normalized_code,
                f"{_t(label_key, language)} NORM",
                "normalized gas units",
                color,
                x_min=None,
                x_max=None,
            )
        )
    return bindings


def _ratio_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    return [
        _binding(
            "WETNESS",
            _t("wetness", language),
            "%",
            "#0f766e",
            x_min=0.0,
            x_max=100.0,
            width=2.0,
        ),
        _binding(
            "BALANCE",
            _t("balance", language),
            "ratio",
            "#b45309",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.1,
            x_max=100.0,
        ),
        _binding(
            "CHARACTER",
            _t("character", language),
            "ratio",
            "#be123c",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.01,
            x_max=10.0,
        ),
        _binding(
            "IC4_NC4",
            "iC4/nC4",
            "ratio",
            "#7c3aed",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.01,
            x_max=100.0,
        ),
        _binding(
            "IC5_NC5",
            "iC5/nC5",
            "ratio",
            "#0369a1",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.01,
            x_max=100.0,
        ),
    ]


def _pixler_bindings() -> list[ParameterBinding]:
    return [
        _binding(
            code,
            label,
            "ratio",
            color,
            x_scale=XScale.LOGARITHMIC,
            x_min=0.1,
            x_max=1000.0,
            width=1.8,
        )
        for code, label, color in (
            ("PIXLER_C1_C2", "C1/C2", "#2563eb"),
            ("PIXLER_C1_C3", "C1/C3", "#16a34a"),
            ("PIXLER_C1_C4", "C1/(iC4+nC4)", "#ea580c"),
            ("PIXLER_C1_C5", "C1/(iC5+nC5)", "#9333ea"),
        )
    ]


def complex_gas_form(language: str = "ru") -> FormDocument:
    """Return the production-ready depth form for complete C1–C5 gas analysis."""

    lang = _language(language)
    gas_group = _t("gas_group", lang)
    sections: list[tuple[str, FormColumn]] = [
        (
            "absolute",
            _curve_column(
                "column-complex-absolute",
                _t("absolute", lang),
                _component_bindings(
                    lang,
                    unit="% abs",
                    x_min=0.0,
                    x_max=100.0,
                ),
                gas_group,
                width=430,
                x_axis_label="% abs",
            ),
        ),
        (
            "absolute-sum",
            _curve_column(
                "column-complex-absolute-sum",
                _t("absolute_sum", lang),
                [
                    _binding(
                        "TG_CALC",
                        _t("total", lang),
                        "% abs",
                        "#dc2626",
                        x_min=0.0,
                        x_max=100.0,
                        width=2.2,
                    )
                ],
                gas_group,
                width=230,
                x_axis_label="% abs",
            ),
        ),
        (
            "normalized-total",
            _curve_column(
                "column-complex-normalized-total",
                _t("normalized_total", lang),
                [
                    _binding(
                        "TG_NORM",
                        _t("normalized_total", lang),
                        "normalized gas units",
                        "#7c3aed",
                        x_min=None,
                        x_max=None,
                        width=2.2,
                    )
                ],
                gas_group,
                width=250,
                x_axis_label="normalized gas units",
            ),
        ),
        (
            "normalized-components",
            _curve_column(
                "column-complex-normalized-components",
                _t("normalized_components", lang),
                _normalized_bindings(lang),
                gas_group,
                width=440,
                x_axis_label="normalized gas units",
            ),
        ),
        (
            "relative",
            _curve_column(
                "column-complex-relative",
                _t("relative", lang),
                _relative_bindings(lang),
                gas_group,
                width=440,
                x_axis_label="% ΣC1–C5",
            ),
        ),
        (
            "ratios",
            _curve_column(
                "column-complex-ratios",
                _t("ratios", lang),
                _ratio_bindings(lang),
                gas_group,
                width=380,
                x_axis_label="ratio",
            ),
        ),
        (
            "pixler",
            _curve_column(
                "column-complex-pixler",
                _t("pixler", lang),
                _pixler_bindings(),
                gas_group,
                width=360,
                x_axis_label="ratio (log)",
            ),
        ),
    ]

    columns: list[FormColumn] = []
    for suffix, graph_column in sections:
        columns.extend(
            (
                _internal_depth_column(lang, suffix, gas_group),
                graph_column,
            )
        )

    form = FormDocument(
        form_id="factory-complex-gas-analysis",
        name=_t("form_name", lang),
        axis_kind=FormAxisKind.DEPTH,
        columns=columns,
        description=_t("description", lang),
        origin=FormTemplateOrigin.FACTORY,
        read_only=True,
        print_header_template_id="factory-header:a4_gas_interpretation_portrait",
        print_header_template_ids={
            "portrait": "factory-header:a4_gas_interpretation_portrait",
            "landscape": "factory-header:a4_gas_interpretation_landscape",
        },
    )
    form.validate()
    return form


__all__ = ["complex_gas_form"]
