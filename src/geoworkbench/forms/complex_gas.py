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
)


TemplateLanguage = Literal["ru", "kk", "en"]


# The catalog is exposed to the shared runtime-localization index as ordinary
# string-keyed mappings; TemplateLanguage still constrains every lookup entry point.
_TEXT: dict[str, dict[str, str]] = {
    "form_name": {
        "ru": "Интегрированный газовый каротаж C1–C5",
        "kk": "C1–C5 интеграцияланған газ каротажы",
        "en": "Integrated C1–C5 gas log",
    },
    "description": {
        "ru": (
            "Скорость проходки, суммарный газ, абсолютные, относительные и "
            "нормализованные компоненты C1–C5, индексы Haworth, изомерные "
            "отношения и Pixler. "
            "Каждая графическая колонка снабжена собственной синхронной шкалой глубины."
        ),
        "kk": (
            "Бұрғылау жылдамдығы, жалпы газ, C1–C5 абсолюттік, салыстырмалы және "
            "нормаланған компоненттері, Haworth индекстері, изомерлік қатынастар "
            "және Pixler. Әр графикалық "
            "бағанда синхрондалған жеке тереңдік шкаласы бар."
        ),
        "en": (
            "ROP, total gas, absolute, relative and normalized C1–C5 components, "
            "Haworth indices, isomer ratios and Pixler ratios. Every graph column "
            "has its own synchronized internal depth scale."
        ),
    },
    "gas_group": {"ru": "Газовые данные", "kk": "Газ деректері", "en": "Gas data"},
    "depth": {"ru": "Глубина", "kk": "Тереңдік", "en": "Depth"},
    "rop": {
        "ru": "ROP / скорость проходки",
        "kk": "ROP / бұрғылау жылдамдығы",
        "en": "ROP / drill rate",
    },
    "absolute": {
        "ru": "Компоненты C1–C5",
        "kk": "C1–C5 компоненттері",
        "en": "C1–C5 components",
    },
    "absolute_sum": {
        "ru": "Суммарный газ",
        "kk": "Жалпы газ",
        "en": "Total gas",
    },
    "normalized_total": {
        "ru": "Нормализованный суммарный газ",
        "kk": "Нормаланған жалпы газ",
        "en": "Normalized total gas",
    },
    "normalized_components": {
        "ru": "C1–C5, нормализованные",
        "kk": "C1–C5, нормаланған",
        "en": "Normalized C1–C5",
    },
    "relative": {
        "ru": "C1–C5, относительный состав",
        "kk": "C1–C5, салыстырмалы құрам",
        "en": "Relative C1–C5",
    },
    "ratios": {
        "ru": "Газовые индексы",
        "kk": "Газ индекстері",
        "en": "Gas ratios",
    },
    "pixler": {
        "ru": "Отношения Pixler",
        "kk": "Pixler қатынастары",
        "en": "Pixler ratios",
    },
    "total": {"ru": "Суммарный газ", "kk": "Жалпы газ", "en": "Total gas"},
    "methane": {"ru": "C1 Метан", "kk": "C1 Метан", "en": "C1 Methane"},
    "ethane": {"ru": "C2 Этан", "kk": "C2 Этан", "en": "C2 Ethane"},
    "propane": {"ru": "C3 Пропан", "kk": "C3 Пропан", "en": "C3 Propane"},
    "isobutane": {
        "ru": "iC4 Изобутан",
        "kk": "iC4 Изобутан",
        "en": "iC4 Isobutane",
    },
    "nbutane": {"ru": "nC4 Н-бутан", "kk": "nC4 Н-бутан", "en": "nC4 N-butane"},
    "isopentane": {
        "ru": "iC5 Изопентан",
        "kk": "iC5 Изопентан",
        "en": "iC5 Isopentane",
    },
    "npentane": {"ru": "nC5 Н-пентан", "kk": "nC5 Н-пентан", "en": "nC5 N-pentane"},
    "wetness": {"ru": "Влажность газа", "kk": "Газ ылғалдылығы", "en": "Wetness"},
    "balance": {"ru": "Баланс газа", "kk": "Газ теңгерімі", "en": "Balance"},
    "character": {"ru": "Характер газа", "kk": "Газ сипаты", "en": "Character"},
    "relative_suffix": {"ru": "отн.", "kk": "сал.", "en": "rel."},
    "normalized_suffix": {"ru": "норм.", "kk": "норм.", "en": "norm."},
    "normalized_units": {
        "ru": "норм. ед.",
        "kk": "норм. бірл.",
        "en": "norm. units",
    },
    "of_total": {"ru": "% от суммы", "kk": "жалпыдан %", "en": "% of total"},
    "ratio_unit": {"ru": "отношение", "kk": "қатынас", "en": "ratio"},
    "log_ratio": {
        "ru": "отношение (лог.)",
        "kk": "қатынас (лог.)",
        "en": "ratio (log)",
    },
}


_COMPONENTS: tuple[tuple[str, str, str], ...] = (
    ("C1", "methane", "#111827"),
    ("C2", "ethane", "#16a34a"),
    ("C3", "propane", "#0891b2"),
    ("IC4", "isobutane", "#2563eb"),
    ("NC4", "nbutane", "#ea580c"),
    ("IC5", "isopentane", "#c026d3"),
    ("NC5", "npentane", "#7e22ce"),
)


def _language(language: str) -> TemplateLanguage:
    return language if language in {"ru", "kk", "en"} else "ru"  # type: ignore[return-value]


def _t(key: str, language: TemplateLanguage) -> str:
    return _TEXT[key][language]


def factory_label_translations() -> tuple[dict[str, str], ...]:
    """Return static and generated captions used by persisted complex-gas forms."""

    generated: list[dict[str, str]] = []
    for code, _label_key, _color in _COMPONENTS:
        display_code = code.replace("IC", "iC").replace("NC", "nC")
        generated.extend(
            (
                {
                    language: f"{display_code} {_TEXT['relative_suffix'][language]}"
                    for language in ("ru", "kk", "en")
                },
                {
                    language: f"{display_code} {_TEXT['normalized_suffix'][language]}"
                    for language in ("ru", "kk", "en")
                },
            )
        )
    generated.append(
        {
            language: f"TG {_TEXT['normalized_suffix'][language]}"
            for language in ("ru", "kk", "en")
        }
    )
    return (*_TEXT.values(), *generated)


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
        header_text_color="#0f172a",
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
        # Factory documents are read-only already.  Keeping the column itself
        # unlocked lets an editable copy enable any hidden repeat depth column,
        # while the locked depth track still protects its axis semantics.
        locked=False,
        title_orientation="horizontal",
        title_position="center",
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
                title_orientation="horizontal",
                title_position="center",
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
    grid_x: bool = True,
    show_x_scale: bool = True,
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
                grid_x=grid_x,
                grid_y=True,
                grid_major_divisions=5,
                grid_minor_divisions=5,
                grid_alpha=0.22,
                grid_print=True,
                show_x_scale=show_x_scale,
                x_axis_label=x_axis_label,
                show_interval_labels=True,
            )
        ],
    )


def _relative_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    return [
        _binding(
            f"{code}_REL",
            f"{code.replace('IC', 'iC').replace('NC', 'nC')} {_t('relative_suffix', language)}",
            "%",
            color,
            x_min=0.0,
            x_max=100.0,
        )
        for code, _label_key, color in _COMPONENTS
    ]


def _normalized_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    bindings: list[ParameterBinding] = []
    for code, label_key, color in _COMPONENTS:
        normalized_code = "C1_NORM_REF" if code == "C1" else f"{code}_NORM"
        bindings.append(
            _binding(
                normalized_code,
                f"{code.replace('IC', 'iC').replace('NC', 'nC')} {_t('normalized_suffix', language)}",
                _t("normalized_units", language),
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
            _t("ratio_unit", language),
            "#b45309",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.1,
            x_max=100.0,
        ),
        _binding(
            "CHARACTER",
            _t("character", language),
            _t("ratio_unit", language),
            "#be123c",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.01,
            x_max=10.0,
        ),
        _binding(
            "IC4_NC4",
            "iC4/nC4",
            _t("ratio_unit", language),
            "#7c3aed",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.01,
            x_max=100.0,
        ),
        _binding(
            "IC5_NC5",
            "iC5/nC5",
            _t("ratio_unit", language),
            "#0369a1",
            x_scale=XScale.LOGARITHMIC,
            x_min=0.01,
            x_max=100.0,
        ),
    ]


def _pixler_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    return [
        _binding(
            code,
            label,
            _t("ratio_unit", language),
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
            "rop",
            _curve_column(
                "column-complex-rop",
                _t("rop", lang),
                [
                    _binding(
                        "ROP",
                        "ROP",
                        "",
                        "#475569",
                        x_min=None,
                        x_max=None,
                        width=1.8,
                    )
                ],
                gas_group,
                width=220,
                x_axis_label="ROP",
            ),
        ),
        (
            "absolute",
            _curve_column(
                "column-complex-absolute",
                _t("absolute", lang),
                _component_bindings(
                    lang,
                    unit="",
                    x_min=None,
                    x_max=None,
                ),
                gas_group,
                width=430,
                x_axis_label="",
                grid_x=False,
                show_x_scale=False,
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
                        "",
                        "#dc2626",
                        x_min=0.0,
                        x_max=100.0,
                        width=2.2,
                    ),
                    _binding(
                        "TG_NORM",
                        f"TG {_t('normalized_suffix', lang)}",
                        _t("normalized_units", lang),
                        "#7c3aed",
                        x_min=None,
                        x_max=None,
                        width=2.0,
                    ),
                ],
                gas_group,
                width=250,
                x_axis_label="TG",
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
                x_axis_label=_t("normalized_units", lang),
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
                x_axis_label=_t("of_total", lang),
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
                x_axis_label=_t("ratio_unit", lang),
            ),
        ),
        (
            "pixler",
            _curve_column(
                "column-complex-pixler",
                _t("pixler", lang),
                _pixler_bindings(lang),
                gas_group,
                width=360,
                x_axis_label=_t("log_ratio", lang),
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
