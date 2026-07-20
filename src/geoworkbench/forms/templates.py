from __future__ import annotations

from copy import deepcopy
from typing import Literal

from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTemplateOrigin,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.tablet.models import CurveLineStyle, CurveStyle, TrackKind, XScale

TemplateLanguage = Literal["ru", "kk", "en"]


_TEXT: dict[str, dict[str, str]] = {
    "factory_description": {
        "ru": "Заводской шаблон GEOLOG Gas Ratio & Pixler",
        "kk": "GEOLOG Gas Ratio & Pixler зауыттық үлгісі",
        "en": "GEOLOG Gas Ratio & Pixler factory template",
    },
    "depth": {"ru": "Глубина", "kk": "Тереңдік", "en": "Depth"},
    "time": {"ru": "Время", "kk": "Уақыт", "en": "Time"},
    "curves": {"ru": "Кривые", "kk": "Қисықтар", "en": "Curves"},
    "basic_depth": {
        "ru": "LAS — рабочая глубинная форма",
        "kk": "LAS — жұмыс тереңдік пішіні",
        "en": "LAS — working depth form",
    },
    "basic_time": {
        "ru": "LAS — рабочая временная форма",
        "kk": "LAS — жұмыс уақыт пішіні",
        "en": "LAS — working time form",
    },
    "gas_components": {
        "ru": "Газовые компоненты C1–C5",
        "kk": "C1–C5 газ компоненттері",
        "en": "C1–C5 gas components",
    },
    "gas_c1_c5": {"ru": "Газ C1–C5", "kk": "C1–C5 газы", "en": "C1–C5 gas"},
    "gas_ratio": {"ru": "Газовые коэффициенты", "kk": "Газ коэффициенттері", "en": "Gas ratios"},
    "pixler": {"ru": "Коэффициенты Pixler", "kk": "Pixler коэффициенттері", "en": "Pixler ratios"},
    "interpretation": {"ru": "Интерпретация", "kk": "Интерпретация", "en": "Interpretation"},
    "intervals_comments": {
        "ru": "Интервалы и комментарии",
        "kk": "Интервалдар мен түсініктемелер",
        "en": "Intervals and comments",
    },
    "rop": {"ru": "Скорость проходки", "kk": "Бұрғылау жылдамдығы", "en": "Rate of penetration"},
    "wob": {"ru": "Нагрузка на долото", "kk": "Қашауға түсетін жүктеме", "en": "Weight on bit"},
    "rpm": {"ru": "Обороты ротора", "kk": "Ротор айналымы", "en": "Rotary speed"},
    "drilling": {"ru": "Бурение", "kk": "Бұрғылау", "en": "Drilling"},
    "mud": {"ru": "Буровой раствор", "kk": "Бұрғылау ерітіндісі", "en": "Drilling fluid"},
    "flow_in": {"ru": "Расход на входе", "kk": "Кірістегі шығын", "en": "Flow in"},
    "flow_out": {"ru": "Расход на выходе", "kk": "Шығыстағы шығын", "en": "Flow out"},
    "spp": {"ru": "Давление на манифольде", "kk": "Манифольд қысымы", "en": "Standpipe pressure"},
    "mud_density": {"ru": "Плотность раствора", "kk": "Ерітінді тығыздығы", "en": "Mud density"},
    "raw_norm_gas": {
        "ru": "Сырой и нормализованный газ",
        "kk": "Бастапқы және нормаланған газ",
        "en": "Raw and normalized gas",
    },
    "total_gas": {"ru": "Суммарный газ", "kk": "Жалпы газ", "en": "Total gas"},
    "normalized_total_gas": {
        "ru": "Нормализованный суммарный газ",
        "kk": "Нормаланған жалпы газ",
        "en": "Normalized total gas",
    },
    "hc_sum_raw": {
        "ru": "Сумма C1–C5",
        "kk": "C1–C5 қосындысы",
        "en": "C1–C5 sum",
    },
    "hc_sum_norm": {
        "ru": "Нормализованная сумма C1–C5",
        "kk": "Нормаланған C1–C5 қосындысы",
        "en": "Normalized C1–C5 sum",
    },
    "methane": {"ru": "Метан C1", "kk": "Метан C1", "en": "Methane C1"},
    "ethane": {"ru": "Этан C2", "kk": "Этан C2", "en": "Ethane C2"},
    "propane": {"ru": "Пропан C3", "kk": "Пропан C3", "en": "Propane C3"},
    "isobutane": {"ru": "Изобутан iC4", "kk": "Изобутан iC4", "en": "Isobutane iC4"},
    "nbutane": {"ru": "Н-бутан nC4", "kk": "Н-бутан nC4", "en": "N-butane nC4"},
    "isopentane": {"ru": "Изопентан iC5", "kk": "Изопентан iC5", "en": "Isopentane iC5"},
    "npentane": {"ru": "Н-пентан nC5", "kk": "Н-пентан nC5", "en": "N-pentane nC5"},
    "wetness": {"ru": "Влажность газа", "kk": "Газ ылғалдылығы", "en": "Wetness"},
    "balance": {"ru": "Баланс газа", "kk": "Газ балансы", "en": "Balance"},
    "character": {"ru": "Характер газа", "kk": "Газ сипаты", "en": "Character"},
    "ic4_nc4": {"ru": "Отношение iC4/nC4", "kk": "iC4/nC4 қатынасы", "en": "iC4/nC4 ratio"},
    "ic5_nc5": {"ru": "Отношение iC5/nC5", "kk": "iC5/nC5 қатынасы", "en": "iC5/nC5 ratio"},
    "lithology": {"ru": "Литология", "kk": "Литология", "en": "Lithology"},
    "gas_ratio_pixler_depth": {
        "ru": "Gas Ratio & Pixler — глубинная интерпретация",
        "kk": "Gas Ratio & Pixler — тереңдік интерпретациясы",
        "en": "Gas Ratio & Pixler — depth interpretation",
    },
    "gas_ratio_pixler_time": {
        "ru": "Gas Ratio & Pixler — временной мониторинг",
        "kk": "Gas Ratio & Pixler — уақыттық мониторинг",
        "en": "Gas Ratio & Pixler — time monitoring",
    },
    "normalized_gas_qc": {
        "ru": "Контроль нормализованного газа",
        "kk": "Нормаланған газды бақылау",
        "en": "Normalized gas QC",
    },
    "c1_c5_detailed": {
        "ru": "Детальный C1–C5",
        "kk": "Егжей-тегжейлі C1–C5",
        "en": "Detailed C1–C5",
    },
    "quality": {"ru": "Контроль качества", "kk": "Сапаны бақылау", "en": "Quality control"},
    "normalization_factor": {
        "ru": "Коэффициент нормализации",
        "kk": "Нормалау коэффициенті",
        "en": "Normalization factor",
    },
    "normalization_valid": {
        "ru": "Допустимость нормализации",
        "kk": "Нормалаудың жарамдылығы",
        "en": "Normalization validity",
    },
}


def _language(language: str) -> TemplateLanguage:
    return language if language in {"ru", "kk", "en"} else "ru"  # type: ignore[return-value]


def _t(key: str, language: TemplateLanguage) -> str:
    return _TEXT[key][language]


def factory_templates(language: str = "ru") -> dict[str, FormDocument]:
    lang = _language(language)
    templates = {
        "factory-depth-basic": _basic_depth(lang),
        "factory-time-basic": _basic_time(lang),
        "factory-gas-components": _gas_components(lang),
        "factory-gas-ratio": _gas_ratio(lang),
        "factory-pixler": _pixler(lang),
        "factory-interpretation": _interpretation(lang),
        "factory-gas-ratio-pixler-depth": _gas_ratio_pixler_depth(lang),
        "factory-gas-ratio-pixler-time": _gas_ratio_pixler_time(lang),
        "factory-normalized-gas-qc": _normalized_gas_qc(lang),
        "factory-c1-c5-detailed": _c1_c5_detailed(lang),
    }
    return {key: deepcopy(value) for key, value in templates.items()}


def _factory(
    form_id: str,
    name: str,
    axis: FormAxisKind,
    columns: list[FormColumn],
    language: TemplateLanguage,
) -> FormDocument:
    return FormDocument(
        form_id=form_id,
        name=name,
        axis_kind=axis,
        columns=columns,
        description=_t("factory_description", language),
        origin=FormTemplateOrigin.FACTORY,
        read_only=True,
    )


def _axis_column(axis: FormAxisKind, language: TemplateLanguage) -> FormColumn:
    title = _t("depth", language) if axis is FormAxisKind.DEPTH else _t("time", language)
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


def _curve_column(
    column_id: str,
    title: str,
    bindings: list[ParameterBinding],
    width: int = 260,
    *,
    x_axis_label: str = "",
) -> FormColumn:
    return FormColumn(
        column_id=column_id,
        title=title,
        width=width,
        tracks=[
            FormTrack(
                track_id=f"track-{column_id}",
                title=title,
                kind=TrackKind.CURVE,
                bindings=bindings,
                x_axis_label=x_axis_label,
            )
        ],
    )


def _special_column(column_id: str, title: str, kind: TrackKind, width: int) -> FormColumn:
    return FormColumn(
        column_id=column_id,
        title=title,
        width=width,
        tracks=[FormTrack(track_id=f"track-{column_id}", title=title, kind=kind)],
    )


def _binding(
    code: str,
    name: str,
    unit: str = "",
    color: str = "#2563eb",
    *,
    log: bool = False,
    width: float = 1.5,
    line_style: CurveLineStyle = CurveLineStyle.SOLID,
    x_min: float | None = None,
    x_max: float | None = None,
) -> ParameterBinding:
    return ParameterBinding(
        binding_id=f"binding-{code.lower().replace('_', '-')}",
        canonical_parameter_id=code,
        display_name=name,
        unit=unit,
        style=CurveStyle(color=color, width=width, line_style=line_style),
        x_scale=XScale.LOGARITHMIC if log else XScale.LINEAR,
        x_min=x_min,
        x_max=x_max,
    )


def _gas_component_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    return [
        _binding("C1", _t("methane", language), "%", "#2563eb"),
        _binding("C2", _t("ethane", language), "%", "#16a34a"),
        _binding("C3", _t("propane", language), "%", "#9333ea"),
        _binding("IC4", _t("isobutane", language), "%", "#ea580c"),
        _binding("NC4", _t("nbutane", language), "%", "#ca8a04"),
        _binding("IC5", _t("isopentane", language), "%", "#0891b2"),
        _binding("NC5", _t("npentane", language), "%", "#475569"),
    ]


def _ratio_bindings(language: TemplateLanguage) -> list[ParameterBinding]:
    return [
        _binding("WETNESS", _t("wetness", language), "", "#0f766e"),
        _binding("BALANCE", _t("balance", language), "", "#b45309"),
        _binding("CHARACTER", _t("character", language), "", "#be123c"),
        _binding("IC4_NC4", _t("ic4_nc4", language), "", "#7c3aed"),
        _binding("IC5_NC5", _t("ic5_nc5", language), "", "#0369a1"),
    ]


def _pixler_bindings() -> list[ParameterBinding]:
    return [
        _binding("PIXLER_C1_C2", "C1/C2", "", "#2563eb", log=True),
        _binding("PIXLER_C1_C3", "C1/C3", "", "#16a34a", log=True),
        _binding("PIXLER_C1_C4", "C1/C4", "", "#ea580c", log=True),
        _binding("PIXLER_C1_C5", "C1/C5", "", "#9333ea", log=True),
    ]


def _basic_depth(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-depth-basic",
        _t("basic_depth", language),
        FormAxisKind.DEPTH,
        [_axis_column(FormAxisKind.DEPTH, language), _curve_column("column-curves", _t("curves", language), [])],
        language,
    )


def _basic_time(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-time-basic",
        _t("basic_time", language),
        FormAxisKind.TIME,
        [_axis_column(FormAxisKind.TIME, language), _curve_column("column-time-curves", _t("curves", language), [])],
        language,
    )


def _gas_components(language: TemplateLanguage) -> FormDocument:
    gases = [
        _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626"),
        *_gas_component_bindings(language),
    ]
    return _factory(
        "factory-gas-components",
        _t("gas_components", language),
        FormAxisKind.DEPTH,
        [_axis_column(FormAxisKind.DEPTH, language), _curve_column("column-gases", _t("gas_c1_c5", language), gases, 420)],
        language,
    )


def _gas_ratio(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-gas-ratio",
        "Gas Ratio",
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-rop", _t("rop", language), [_binding("ROP", _t("rop", language), "m/h", "#111827")]),
            _curve_column(
                "column-total-gas",
                _t("raw_norm_gas", language),
                [
                    _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626"),
                    _binding("NORMALIZED_TOTAL_GAS", _t("normalized_total_gas", language), "%", "#7c3aed"),
                ],
            ),
            _curve_column("column-gas-ratios", _t("gas_ratio", language), _ratio_bindings(language)[:3], 320),
        ],
        language,
    )


def _pixler(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-pixler",
        "Pixler",
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-pixler", _t("pixler", language), _pixler_bindings(), 360),
        ],
        language,
    )


def _interpretation(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-interpretation",
        _t("interpretation", language),
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-total-gas", _t("total_gas", language), [_binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626")]),
            _special_column("column-interpretation", _t("intervals_comments", language), TrackKind.INTERPRETATION, 320),
        ],
        language,
    )


def _gas_ratio_pixler_depth(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-gas-ratio-pixler-depth",
        _t("gas_ratio_pixler_depth", language),
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column(
                "column-drilling",
                _t("drilling", language),
                [
                    _binding("ROP", _t("rop", language), "m/h", "#dc2626", width=1.8),
                    _binding("WOB", _t("wob", language), "t", "#2563eb"),
                    _binding("RPM", _t("rpm", language), "rpm", "#16a34a"),
                ],
                300,
            ),
            _curve_column(
                "column-mud",
                _t("mud", language),
                [
                    _binding("FLOW_IN", _t("flow_in", language), "L/s", "#0891b2"),
                    _binding("FLOW_OUT", _t("flow_out", language), "L/s", "#0f766e"),
                    _binding("SPP", _t("spp", language), "atm", "#dc2626"),
                    _binding("MUD_DENSITY", _t("mud_density", language), "g/cm³", "#7c3aed"),
                ],
                300,
            ),
            _curve_column(
                "column-raw-normalized-gas",
                _t("raw_norm_gas", language),
                [
                    _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626", width=2.0),
                    _binding("NORMALIZED_TOTAL_GAS", _t("normalized_total_gas", language), "%", "#7c3aed", width=2.0),
                    _binding("HC_SUM_RAW", _t("hc_sum_raw", language), "%", "#ea580c"),
                    _binding("HC_SUM_NORM", _t("hc_sum_norm", language), "%", "#0369a1"),
                ],
                340,
            ),
            _curve_column("column-components", _t("gas_c1_c5", language), _gas_component_bindings(language), 420),
            _curve_column("column-ratios", _t("gas_ratio", language), _ratio_bindings(language), 360),
            _curve_column("column-pixler-ratios", _t("pixler", language), _pixler_bindings(), 360),
            _special_column("column-lithology", _t("lithology", language), TrackKind.LITHOLOGY, 220),
            _special_column("column-interpretation", _t("interpretation", language), TrackKind.INTERPRETATION, 320),
        ],
        language,
    )


def _gas_ratio_pixler_time(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-gas-ratio-pixler-time",
        _t("gas_ratio_pixler_time", language),
        FormAxisKind.TIME,
        [
            _axis_column(FormAxisKind.TIME, language),
            _curve_column(
                "column-time-drilling",
                _t("drilling", language),
                [
                    _binding("ROP", _t("rop", language), "m/h", "#dc2626", width=1.8),
                    _binding("RPM", _t("rpm", language), "rpm", "#16a34a"),
                    _binding("SPP", _t("spp", language), "atm", "#2563eb"),
                ],
                300,
            ),
            _curve_column(
                "column-time-gas",
                _t("raw_norm_gas", language),
                [
                    _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626", width=2.0),
                    _binding("NORMALIZED_TOTAL_GAS", _t("normalized_total_gas", language), "%", "#7c3aed", width=2.0),
                ],
                320,
            ),
            _curve_column("column-time-components", _t("gas_c1_c5", language), _gas_component_bindings(language), 420),
            _curve_column("column-time-ratios", _t("gas_ratio", language), _ratio_bindings(language), 360),
            _curve_column("column-time-pixler", _t("pixler", language), _pixler_bindings(), 360),
            _special_column("column-time-interpretation", _t("interpretation", language), TrackKind.INTERPRETATION, 320),
        ],
        language,
    )


def _normalized_gas_qc(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-normalized-gas-qc",
        _t("normalized_gas_qc", language),
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column(
                "column-qc-drilling",
                _t("drilling", language),
                [
                    _binding("ROP", _t("rop", language), "m/h", "#dc2626"),
                    _binding("FLOW_IN", _t("flow_in", language), "L/s", "#0891b2"),
                    _binding("MUD_DENSITY", _t("mud_density", language), "g/cm³", "#7c3aed"),
                ],
                300,
            ),
            _curve_column(
                "column-qc-gas",
                _t("raw_norm_gas", language),
                [
                    _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626", width=2.0),
                    _binding("NORMALIZED_TOTAL_GAS", _t("normalized_total_gas", language), "%", "#7c3aed", width=2.0),
                    _binding("HC_SUM_RAW", _t("hc_sum_raw", language), "%", "#ea580c"),
                    _binding("HC_SUM_NORM", _t("hc_sum_norm", language), "%", "#0369a1"),
                ],
                360,
            ),
            _curve_column(
                "column-qc-status",
                _t("quality", language),
                [
                    _binding("K_NORM", _t("normalization_factor", language), "", "#111827"),
                    _binding("NORM_VALID", _t("normalization_valid", language), "", "#16a34a", line_style=CurveLineStyle.DASH),
                ],
                280,
            ),
        ],
        language,
    )


def _c1_c5_detailed(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-c1-c5-detailed",
        _t("c1_c5_detailed", language),
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column(
                "column-c1-c3",
                "C1–C3",
                _gas_component_bindings(language)[:3],
                340,
            ),
            _curve_column(
                "column-c4-c5",
                "C4–C5",
                _gas_component_bindings(language)[3:],
                340,
            ),
            _curve_column("column-isomers", _t("gas_ratio", language), _ratio_bindings(language)[3:], 280),
        ],
        language,
    )
