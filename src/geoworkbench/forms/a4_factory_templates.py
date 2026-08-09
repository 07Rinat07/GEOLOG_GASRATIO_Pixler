from __future__ import annotations

from copy import deepcopy
from typing import Literal

from geoworkbench.forms.complex_gas import complex_gas_form
from geoworkbench.forms.models import FormAxisKind, FormDocument, ParameterBinding
from geoworkbench.forms.templates import (
    _axis_column,
    _binding,
    _curve_column,
    _factory,
    _gas_component_bindings,
    _special_column,
    _with_a4_print_headers,
)
from geoworkbench.tablet.models import CurveStyle, TrackKind, XScale

TemplateLanguage = Literal["ru", "kk", "en"]

A4_FACTORY_TEMPLATE_IDS: tuple[str, ...] = (
    "factory-masterlog-a4-portrait",
    "factory-masterlog-a4-landscape",
    "factory-technology-a4-portrait",
    "factory-technology-a4-landscape",
    "factory-daily-a4-portrait",
    "factory-daily-a4-landscape",
    "factory-complex-gas-a4-portrait",
    "factory-complex-gas-a4-landscape",
)

_TEXT = {
    "portrait": {"ru": "A4 книжная", "kk": "A4 кітаптық", "en": "A4 portrait"},
    "landscape": {"ru": "A4 альбомная", "kk": "A4 альбомдық", "en": "A4 landscape"},
    "masterlog": {"ru": "MASTERLOG", "kk": "MASTERLOG", "en": "MASTERLOG"},
    "technology": {"ru": "Технология", "kk": "Технология", "en": "Drilling technology"},
    "daily": {
        "ru": "Суточная технологическая форма",
        "kk": "Тәуліктік технологиялық пішін",
        "en": "Daily drilling form",
    },
    "complex_gas": {
        "ru": "Интегрированный газовый каротаж C1–C5",
        "kk": "C1–C5 интеграцияланған газ каротажы",
        "en": "Integrated C1–C5 gas log",
    },
    "stratigraphy": {"ru": "Стратиграфия", "kk": "Стратиграфия", "en": "Stratigraphy"},
    "lithology": {"ru": "Литология", "kk": "Литология", "en": "Lithology"},
    "cuttings": {"ru": "Шламограмма", "kk": "Шламограмма", "en": "Cuttings log"},
    "calcimetry": {"ru": "Кальциметрия", "kk": "Кальциметрия", "en": "Calcimetry"},
    "lba": {"ru": "ЛБА", "kk": "ЛБА", "en": "LBA"},
    "drilling": {"ru": "Бурение", "kk": "Бұрғылау", "en": "Drilling"},
    "gas": {
        "ru": "Абсолютные газы C1–C5",
        "kk": "C1–C5 абсолюттік газдары",
        "en": "Absolute gas C1–C5",
    },
    "normalized": {"ru": "Нормализованный газ", "kk": "Нормаланған газ", "en": "Normalized gas"},
    "relative": {
        "ru": "Относительные коэффициенты",
        "kk": "Салыстырмалы коэффициенттер",
        "en": "Relative gas ratios",
    },
    "pixler": {"ru": "Коэффициенты Pixler", "kk": "Pixler коэффициенттері", "en": "Pixler ratios"},
    "interpretation": {"ru": "Интерпретация", "kk": "Интерпретация", "en": "Interpretation"},
    "mechanics": {"ru": "Механика бурения", "kk": "Бұрғылау механикасы", "en": "Drilling mechanics"},
    "hydraulics": {
        "ru": "Гидравлика и раствор",
        "kk": "Гидравлика және ерітінді",
        "en": "Hydraulics and mud",
    },
    "pumps": {"ru": "Насосы и расходы", "kk": "Сорғылар және шығындар", "en": "Pumps and flow"},
    "pits": {"ru": "Объёмы ёмкостей", "kk": "Ыдыстар көлемі", "en": "Pit volumes"},
    "daily_ops": {"ru": "Суточные операции", "kk": "Тәуліктік операциялар", "en": "Daily operations"},
    "mud_gas": {"ru": "Раствор и газ", "kk": "Ерітінді және газ", "en": "Mud and gas"},
    "comments": {
        "ru": "События и комментарии",
        "kk": "Оқиғалар мен түсініктемелер",
        "en": "Events and comments",
    },
}


def _language(language: str) -> TemplateLanguage:
    return language if language in {"ru", "kk", "en"} else "ru"  # type: ignore[return-value]


def _t(key: str, language: TemplateLanguage) -> str:
    return _TEXT[key][language]


def _name(base: str, language: TemplateLanguage, orientation: str) -> str:
    return f"{_t(base, language)} — {_t(orientation, language)}"


def _finalize(form: FormDocument, profile: str, orientation: str) -> FormDocument:
    _with_a4_print_headers(form, profile)
    form.print_header_template_id = form.print_header_template_ids[orientation]
    form.validate()
    return form


def _instance_binding(
    binding_id: str,
    canonical_id: str,
    display_name: str,
    unit: str,
    color: str,
) -> ParameterBinding:
    return ParameterBinding(
        binding_id=binding_id,
        canonical_parameter_id=canonical_id,
        display_name=display_name,
        unit=unit,
        style=CurveStyle(color=color),
        x_scale=XScale.LINEAR,
    )


def _absolute_gas(language: TemplateLanguage) -> list[ParameterBinding]:
    return [
        _binding("TOTAL_GAS", "Total Gas", "%", "#dc2626", width=2.0),
        *_gas_component_bindings(language),
    ]


def _normalized_gas() -> list[ParameterBinding]:
    return [
        _binding("TG_NORM", "TG NORM", "norm", "#7c3aed", width=2.0),
        _binding("C1_NORM", "C1 NORM", "norm", "#2563eb"),
        _binding("C2_NORM", "C2 NORM", "norm", "#16a34a"),
        _binding("C3_NORM", "C3 NORM", "norm", "#9333ea"),
        _binding("IC4_NORM", "iC4 NORM", "norm", "#ea580c"),
        _binding("NC4_NORM", "nC4 NORM", "norm", "#ca8a04"),
        _binding("IC5_NORM", "iC5 NORM", "norm", "#0891b2"),
        _binding("NC5_NORM", "nC5 NORM", "norm", "#475569"),
    ]


def _axis(axis: FormAxisKind, language: TemplateLanguage, width: int):
    return _axis_column(axis, language, width=width)


def _masterlog(language: TemplateLanguage, orientation: str) -> FormDocument:
    landscape = orientation == "landscape"
    columns = [
        _axis(FormAxisKind.DEPTH, language, 55 if landscape else 48),
        _special_column(
            f"column-a4-{orientation}-stratigraphy",
            _t("stratigraphy", language),
            TrackKind.STRATIGRAPHY,
            55 if landscape else 48,
        ),
        _special_column(
            f"column-a4-{orientation}-lithology",
            _t("lithology", language),
            TrackKind.LITHOLOGY,
            70 if landscape else 60,
        ),
        _special_column(
            f"column-a4-{orientation}-cuttings",
            _t("cuttings", language),
            TrackKind.CUTTINGS,
            80 if landscape else 60,
        ),
        _special_column(
            f"column-a4-{orientation}-calcimetry",
            _t("calcimetry", language),
            TrackKind.CALCIMETRY,
            60 if landscape else 50,
            [
                _binding("CACO3", "CaCO3", "%", "#06b6d4", x_min=0, x_max=100),
                _binding("CAMG_CO3_2", "CaMg(CO3)2", "%", "#8b5cf6", x_min=0, x_max=100),
            ],
        ),
        _special_column(
            f"column-a4-{orientation}-lba",
            _t("lba", language),
            TrackKind.LBA,
            60 if landscape else 48,
        ),
        _curve_column(
            f"column-a4-{orientation}-drilling",
            _t("drilling", language),
            [
                _binding("ROP", "ROP", "m/h", "#dc2626"),
                _binding("WOB", "WOB", "t", "#2563eb"),
                _binding("RPM", "RPM", "rpm", "#16a34a"),
                _binding("SPP", "SPP", "atm", "#9333ea"),
            ],
            240 if landscape else 180,
        ),
        _curve_column(
            f"column-a4-{orientation}-gas",
            _t("gas", language),
            _absolute_gas(language),
            260 if landscape else 200,
        ),
    ]
    if landscape:
        columns.append(
            _special_column(
                "column-a4-landscape-interpretation",
                _t("interpretation", language),
                TrackKind.INTERPRETATION,
                140,
            )
        )
    return _finalize(
        _factory(
            f"factory-masterlog-a4-{orientation}",
            _name("masterlog", language, orientation),
            FormAxisKind.DEPTH,
            columns,
            language,
        ),
        "masterlog",
        orientation,
    )


def _technology(language: TemplateLanguage, orientation: str) -> FormDocument:
    landscape = orientation == "landscape"
    columns = [
        _axis(FormAxisKind.DEPTH, language, 55 if landscape else 48),
        _curve_column(
            f"column-tech-{orientation}-mechanics",
            _t("mechanics", language),
            [
                _binding("ROP", "ROP", "m/h", "#dc2626"),
                _binding("WOB", "WOB", "t", "#2563eb"),
                _binding("RPM", "RPM", "rpm", "#16a34a"),
                _binding("TQ", "Torque", "kN·m", "#9333ea"),
                _binding("HKLD", "Hook load", "t", "#475569"),
            ],
            260 if landscape else 220,
        ),
        _curve_column(
            f"column-tech-{orientation}-hydraulics",
            _t("hydraulics", language),
            [
                _binding("SPP", "SPP", "atm", "#dc2626"),
                _binding("FLOW_IN", "Flow in", "L/s", "#0891b2"),
                _binding("FLOW_OUT", "Flow out", "L/s", "#0f766e"),
                _binding("MW_IN", "Mud density in", "g/cm³", "#7c3aed"),
            ],
            250 if landscape else 220,
        ),
        _curve_column(
            f"column-tech-{orientation}-pumps",
            _t("pumps", language),
            [
                _binding("SPM1", "Pump 1 SPM", "min-1", "#2563eb"),
                _binding("SPM2", "Pump 2 SPM", "min-1", "#9333ea"),
                _instance_binding(
                    f"binding-tech-{orientation}-pump-flow-in",
                    "FLOW_IN",
                    "Flow in",
                    "L/s",
                    "#0891b2",
                ),
                _instance_binding(
                    f"binding-tech-{orientation}-pump-flow-out",
                    "FLOW_OUT",
                    "Flow out",
                    "L/s",
                    "#0f766e",
                ),
            ],
            240 if landscape else 220,
        ),
    ]
    if landscape:
        columns.append(
            _curve_column(
                "column-tech-landscape-pits",
                _t("pits", language),
                [
                    _binding("PIT_VOL", "Total pit volume", "m³", "#111827"),
                    _binding("PIT1", "Pit 1", "m³", "#fb923c"),
                    _binding("PIT2", "Pit 2", "m³", "#facc15"),
                    _binding("PIT3", "Pit 3", "m³", "#84cc16"),
                ],
                220,
            )
        )
    return _finalize(
        _factory(
            f"factory-technology-a4-{orientation}",
            _name("technology", language, orientation),
            FormAxisKind.DEPTH,
            columns,
            language,
        ),
        "technology",
        orientation,
    )


def _daily(language: TemplateLanguage, orientation: str) -> FormDocument:
    landscape = orientation == "landscape"
    columns = [
        _axis(FormAxisKind.TIME, language, 55 if landscape else 48),
        _curve_column(
            f"column-daily-{orientation}-ops",
            _t("daily_ops", language),
            [
                _binding("HOLE_DEPTH", "Hole depth", "m", "#2563eb"),
                _binding("BIT_DEPTH", "Bit depth", "m", "#111827"),
                _binding("ROP", "ROP", "m/h", "#dc2626"),
                _binding("HKLD", "Hook load", "t", "#0f766e"),
                _binding("RPM", "RPM", "rpm", "#16a34a"),
            ],
            250 if landscape else 220,
        ),
        _curve_column(
            f"column-daily-{orientation}-mud-gas",
            _t("mud_gas", language),
            [
                _binding("TEMP_IN", "Mud temperature in", "°C", "#16a34a"),
                _binding("TEMP_OUT", "Mud temperature out", "°C", "#d946ef"),
                _binding("MW_IN", "Mud density in", "g/cm³", "#2563eb"),
                _binding("TOTAL_GAS", "Total Gas", "%", "#dc2626"),
                _binding("C1", "C1", "%", "#0891b2"),
            ],
            250 if landscape else 220,
        ),
        _curve_column(
            f"column-daily-{orientation}-pits",
            _t("pits", language),
            [
                _binding("PIT_VOL", "Total pit volume", "m³", "#111827"),
                _binding("PIT1", "Pit 1", "m³", "#fb923c"),
                _binding("PIT2", "Pit 2", "m³", "#facc15"),
                _binding("PIT3", "Pit 3", "m³", "#84cc16"),
            ],
            240 if landscape else 220,
        ),
    ]
    if landscape:
        columns.append(
            _special_column(
                "column-daily-landscape-comments",
                _t("comments", language),
                TrackKind.TEXT,
                230,
            )
        )
    return _finalize(
        _factory(
            f"factory-daily-a4-{orientation}",
            _name("daily", language, orientation),
            FormAxisKind.TIME,
            columns,
            language,
        ),
        "operational_control",
        orientation,
    )


def _complex_gas(language: TemplateLanguage, orientation: str) -> FormDocument:
    """Build a complete seven-graph gas form that fits its named A4 orientation."""

    landscape = orientation == "landscape"
    form = complex_gas_form(language)
    form.form_id = f"factory-complex-gas-a4-{orientation}"
    form.name = _name("complex_gas", language, orientation)

    depth_width = 55 if landscape else 48
    graph_widths = (
        (100, 160, 110, 160, 150, 140, 130)
        if landscape
        else (80, 110, 80, 110, 100, 90, 86)
    )
    depth_index = 0
    graph_index = 0
    for column in form.columns:
        if column.tracks and column.tracks[0].kind is TrackKind.DEPTH:
            column.width = depth_width
            column.visible = depth_index == 0
            depth_index += 1
        else:
            column.width = graph_widths[graph_index]
            graph_index += 1

    if depth_index != 7 or graph_index != len(graph_widths):
        raise RuntimeError("Unexpected complex-gas column structure")
    return _finalize(form, "gas_interpretation", orientation)


def a4_factory_templates(language: str = "ru") -> dict[str, FormDocument]:
    lang = _language(language)
    forms = {
        "factory-masterlog-a4-portrait": _masterlog(lang, "portrait"),
        "factory-masterlog-a4-landscape": _masterlog(lang, "landscape"),
        "factory-technology-a4-portrait": _technology(lang, "portrait"),
        "factory-technology-a4-landscape": _technology(lang, "landscape"),
        "factory-daily-a4-portrait": _daily(lang, "portrait"),
        "factory-daily-a4-landscape": _daily(lang, "landscape"),
        "factory-complex-gas-a4-portrait": _complex_gas(lang, "portrait"),
        "factory-complex-gas-a4-landscape": _complex_gas(lang, "landscape"),
    }
    return {form_id: deepcopy(forms[form_id]) for form_id in A4_FACTORY_TEMPLATE_IDS}
