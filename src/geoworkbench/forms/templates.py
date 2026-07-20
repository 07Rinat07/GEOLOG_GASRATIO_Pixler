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
    "dexp_form": {"ru": "D-экспонента и режим бурения", "kk": "D-экспонента және бұрғылау режимі", "en": "D-exponent and drilling regime"},
    "technology_form": {"ru": "Технологические параметры бурения", "kk": "Бұрғылаудың технологиялық параметрлері", "en": "Drilling technology parameters"},
    "geology_cuttings_form": {"ru": "Литология и шламограмма", "kk": "Литология және шламограмма", "en": "Lithology and cuttings log"},
    "calcimetry_form": {"ru": "Кальциметрия", "kk": "Кальциметрия", "en": "Calcimetry"},
    "lba_form": {"ru": "ЛБА — лабораторный анализ", "kk": "ЛБА — зертханалық талдау", "en": "LBA laboratory analysis"},
    "geotech_form": {"ru": "Комплексная геолого-технологическая форма", "kk": "Кешенді геологиялық-технологиялық пішін", "en": "Integrated geological and technological form"},
    "d_exponent": {"ru": "D-экспонента", "kk": "D-экспонента", "en": "D-exponent"},
    "corrected_d_exponent": {"ru": "Скорректированная D-экспонента", "kk": "Түзетілген D-экспонента", "en": "Corrected D-exponent"},
    "technology": {"ru": "Технология", "kk": "Технология", "en": "Technology"},
    "cuttings": {"ru": "Шламограмма", "kk": "Шламограмма", "en": "Cuttings log"},
    "rock_description": {"ru": "Описание пород", "kk": "Тау жыныстарының сипаттамасы", "en": "Rock description"},
    "calcimetry": {"ru": "Кальциметрия", "kk": "Кальциметрия", "en": "Calcimetry"},
    "lba": {"ru": "ЛБА", "kk": "ЛБА", "en": "LBA"},
    "stratigraphy": {"ru": "Стратиграфия", "kk": "Стратиграфия", "en": "Stratigraphy"},
    "engineering_control_time": {"ru": "Инженерно-технологический контроль — время", "kk": "Инженерлік-технологиялық бақылау — уақыт", "en": "Engineering control — time"},
    "pumps": {"ru": "Насосы и расходы", "kk": "Сорғылар және шығындар", "en": "Pumps and flow"},
    "mud_gas_monitoring": {"ru": "Раствор и газ", "kk": "Ерітінді және газ", "en": "Mud and gas"},
    "pit_volumes": {"ru": "Объёмы ёмкостей", "kk": "Ыдыстар көлемі", "en": "Pit volumes"},
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
        "factory-d-exponent": _d_exponent(lang),
        "factory-drilling-technology": _drilling_technology(lang),
        "factory-lithology-cuttings": _lithology_cuttings(lang),
        "factory-calcimetry": _calcimetry(lang),
        "factory-lba": _lba(lang),
        "factory-geotech-integrated": _geotech_integrated(lang),
        "factory-engineering-control-time": _engineering_control_time(lang),
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
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-curves", _t("curves", language), []),
        ],
        language,
    )


def _basic_time(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-time-basic",
        _t("basic_time", language),
        FormAxisKind.TIME,
        [
            _axis_column(FormAxisKind.TIME, language),
            _curve_column("column-time-curves", _t("curves", language), []),
        ],
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
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-gases", _t("gas_c1_c5", language), gases, 420),
        ],
        language,
    )


def _gas_ratio(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-gas-ratio",
        "Gas Ratio",
        FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column(
                "column-rop",
                _t("rop", language),
                [_binding("ROP", _t("rop", language), "m/h", "#111827")],
            ),
            _curve_column(
                "column-total-gas",
                _t("raw_norm_gas", language),
                [
                    _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626"),
                    _binding(
                        "NORMALIZED_TOTAL_GAS", _t("normalized_total_gas", language), "%", "#7c3aed"
                    ),
                ],
            ),
            _curve_column(
                "column-gas-ratios", _t("gas_ratio", language), _ratio_bindings(language)[:3], 320
            ),
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
            _curve_column(
                "column-total-gas",
                _t("total_gas", language),
                [_binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626")],
            ),
            _special_column(
                "column-interpretation",
                _t("intervals_comments", language),
                TrackKind.INTERPRETATION,
                320,
            ),
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
                    _binding(
                        "NORMALIZED_TOTAL_GAS",
                        _t("normalized_total_gas", language),
                        "%",
                        "#7c3aed",
                        width=2.0,
                    ),
                    _binding("HC_SUM_RAW", _t("hc_sum_raw", language), "%", "#ea580c"),
                    _binding("HC_SUM_NORM", _t("hc_sum_norm", language), "%", "#0369a1"),
                ],
                340,
            ),
            _curve_column(
                "column-components",
                _t("gas_c1_c5", language),
                _gas_component_bindings(language),
                420,
            ),
            _curve_column(
                "column-ratios", _t("gas_ratio", language), _ratio_bindings(language), 360
            ),
            _curve_column("column-pixler-ratios", _t("pixler", language), _pixler_bindings(), 360),
            _special_column(
                "column-lithology", _t("lithology", language), TrackKind.LITHOLOGY, 220
            ),
            _special_column(
                "column-interpretation",
                _t("interpretation", language),
                TrackKind.INTERPRETATION,
                320,
            ),
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
                    _binding(
                        "NORMALIZED_TOTAL_GAS",
                        _t("normalized_total_gas", language),
                        "%",
                        "#7c3aed",
                        width=2.0,
                    ),
                ],
                320,
            ),
            _curve_column(
                "column-time-components",
                _t("gas_c1_c5", language),
                _gas_component_bindings(language),
                420,
            ),
            _curve_column(
                "column-time-ratios", _t("gas_ratio", language), _ratio_bindings(language), 360
            ),
            _curve_column("column-time-pixler", _t("pixler", language), _pixler_bindings(), 360),
            _special_column(
                "column-time-interpretation",
                _t("interpretation", language),
                TrackKind.INTERPRETATION,
                320,
            ),
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
                    _binding(
                        "NORMALIZED_TOTAL_GAS",
                        _t("normalized_total_gas", language),
                        "%",
                        "#7c3aed",
                        width=2.0,
                    ),
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
                    _binding(
                        "NORM_VALID",
                        _t("normalization_valid", language),
                        "",
                        "#16a34a",
                        line_style=CurveLineStyle.DASH,
                    ),
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
            _curve_column(
                "column-isomers", _t("gas_ratio", language), _ratio_bindings(language)[3:], 280
            ),
        ],
        language,
    )


def _d_exponent(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-d-exponent", _t("dexp_form", language), FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-dexp-drilling", _t("drilling", language), [
                _binding("ROP", _t("rop", language), "m/h", "#dc2626"),
                _binding("WOB", _t("wob", language), "t", "#2563eb"),
                _binding("RPM", _t("rpm", language), "rpm", "#16a34a"),
            ], 320),
            _curve_column("column-dexp", _t("d_exponent", language), [
                _binding("DEXP", _t("d_exponent", language), "", "#7c3aed"),
                _binding("D_EXP_CORR", _t("corrected_d_exponent", language), "", "#ea580c"),
            ], 300),
            _curve_column("column-dexp-gas", _t("total_gas", language), [
                _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626"),
            ], 260),
            _special_column("column-dexp-interpretation", _t("interpretation", language), TrackKind.INTERPRETATION, 300),
        ], language,
    )


def _drilling_technology(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-drilling-technology", _t("technology_form", language), FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-tech-mechanics", _t("technology", language), [
                _binding("ROP", _t("rop", language), "m/h", "#dc2626"),
                _binding("WOB", _t("wob", language), "t", "#2563eb"),
                _binding("RPM", _t("rpm", language), "rpm", "#16a34a"),
                _binding("TQ", "Torque", "", "#9333ea"),
                _binding("HKLD", "Hook load", "", "#475569"),
            ], 380),
            _curve_column("column-tech-hydraulics", _t("mud", language), [
                _binding("SPP", _t("spp", language), "atm", "#dc2626"),
                _binding("FLOW_IN", _t("flow_in", language), "L/s", "#0891b2"),
                _binding("FLOW_OUT", _t("flow_out", language), "L/s", "#0f766e"),
                _binding("MUD_DENSITY", _t("mud_density", language), "g/cm³", "#7c3aed"),
            ], 360),
            _special_column("column-tech-events", _t("intervals_comments", language), TrackKind.TEXT, 300),
        ], language,
    )


def _lithology_cuttings(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-lithology-cuttings", _t("geology_cuttings_form", language), FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _special_column("column-stratigraphy", _t("stratigraphy", language), TrackKind.STRATIGRAPHY, 180),
            _special_column("column-lithology", _t("lithology", language), TrackKind.LITHOLOGY, 220),
            _special_column("column-cuttings", _t("cuttings", language), TrackKind.CUTTINGS, 260),
            _special_column("column-rock-description", _t("rock_description", language), TrackKind.TEXT, 360),
            _curve_column("column-geology-gas", _t("total_gas", language), [_binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626")], 240),
        ], language,
    )


def _calcimetry(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-calcimetry", _t("calcimetry_form", language), FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _special_column("column-calcimetry", _t("calcimetry", language), TrackKind.CALCIMETRY, 340),
            _special_column("column-calcimetry-lithology", _t("lithology", language), TrackKind.LITHOLOGY, 220),
            _special_column("column-calcimetry-comments", _t("intervals_comments", language), TrackKind.TEXT, 320),
        ], language,
    )


def _lba(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-lba", _t("lba_form", language), FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _special_column("column-lba", _t("lba", language), TrackKind.LBA, 360),
            _special_column("column-lba-lithology", _t("lithology", language), TrackKind.LITHOLOGY, 220),
            _special_column("column-lba-comments", _t("intervals_comments", language), TrackKind.TEXT, 320),
        ], language,
    )


def _geotech_integrated(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-geotech-integrated", _t("geotech_form", language), FormAxisKind.DEPTH,
        [
            _axis_column(FormAxisKind.DEPTH, language),
            _curve_column("column-geotech-drilling", _t("drilling", language), [
                _binding("ROP", _t("rop", language), "m/h", "#dc2626"),
                _binding("WOB", _t("wob", language), "t", "#2563eb"),
                _binding("RPM", _t("rpm", language), "rpm", "#16a34a"),
                _binding("SPP", _t("spp", language), "atm", "#9333ea"),
            ], 360),
            _curve_column("column-geotech-gas", _t("gas_c1_c5", language), [_binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626"), *_gas_component_bindings(language)], 420),
            _curve_column("column-geotech-dexp", _t("d_exponent", language), [
                _binding("DEXP", _t("d_exponent", language), "", "#7c3aed"),
                _binding("D_EXP_CORR", _t("corrected_d_exponent", language), "", "#ea580c"),
            ], 280),
            _special_column("column-geotech-lithology", _t("lithology", language), TrackKind.LITHOLOGY, 220),
            _special_column("column-geotech-cuttings", _t("cuttings", language), TrackKind.CUTTINGS, 240),
            _special_column("column-geotech-interpretation", _t("interpretation", language), TrackKind.INTERPRETATION, 320),
        ], language,
    )


def _engineering_control_time(language: TemplateLanguage) -> FormDocument:
    return _factory(
        "factory-engineering-control-time",
        _t("engineering_control_time", language),
        FormAxisKind.TIME,
        [
            _axis_column(FormAxisKind.TIME, language),
            _curve_column(
                "column-time-drilling-control",
                _t("drilling", language),
                [
                    _binding("WOB", _t("wob", language), "t", "#2563eb"),
                    _binding("HKLD", "Hook load", "t", "#0f766e"),
                    _binding("ROP", _t("rop", language), "m/h", "#dc2626"),
                    _binding("RPM", _t("rpm", language), "rpm", "#16a34a"),
                    _binding("TQ", "Torque", "kN·m", "#9333ea"),
                ],
                360,
            ),
            _curve_column(
                "column-time-pumps-flow",
                _t("pumps", language),
                [
                    _binding("SPP", _t("spp", language), "atm", "#dc2626"),
                    _binding("SPM1", "Pump 1 SPM", "min⁻¹", "#2563eb"),
                    _binding("SPM2", "Pump 2 SPM", "min⁻¹", "#9333ea"),
                    _binding("FLOW_IN", _t("flow_in", language), "L/s", "#0891b2"),
                    _binding("FLOW_OUT", _t("flow_out", language), "L/s", "#0f766e"),
                ],
                360,
            ),
            _curve_column(
                "column-time-mud-gas",
                _t("mud_gas_monitoring", language),
                [
                    _binding("HOLE_DEPTH", "Hole depth", "m", "#2563eb"),
                    _binding("BIT_DEPTH", "Bit depth", "m", "#111827"),
                    _binding("TEMP_IN", "Mud temperature in", "°C", "#16a34a"),
                    _binding("TEMP_OUT", "Mud temperature out", "°C", "#d946ef"),
                    _binding("TOTAL_GAS", _t("total_gas", language), "%", "#dc2626"),
                    _binding("C1", _t("methane", language), "%", "#2563eb"),
                ],
                380,
            ),
            _curve_column(
                "column-time-pit-volumes",
                _t("pit_volumes", language),
                [
                    _binding("PIT_VOL", "Total pit volume", "m³", "#111827"),
                    _binding("PIT1", "Pit 1", "m³", "#fb923c"),
                    _binding("PIT2", "Pit 2", "m³", "#facc15"),
                    _binding("PIT3", "Pit 3", "m³", "#84cc16"),
                    _binding("PIT4", "Pit 4", "m³", "#38bdf8"),
                    _binding("MW_IN", "Mud density in", "g/cm³", "#16a34a"),
                    _binding("MW_OUT", "Mud density out", "g/cm³", "#dc2626"),
                ],
                380,
            ),
            _special_column(
                "column-time-technology-comments",
                _t("intervals_comments", language),
                TrackKind.TEXT,
                320,
            ),
        ],
        language,
    )

