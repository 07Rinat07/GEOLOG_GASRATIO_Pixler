from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class MasterlogFormPreset:
    preset_id: str
    names: dict[AppLanguage, str]
    descriptions: dict[AppLanguage, str]
    template: MasterlogTemplate

    def name(self, language: AppLanguage) -> str:
        return self.names[language]

    def description(self, language: AppLanguage) -> str:
        return self.descriptions[language]


@dataclass(frozen=True, slots=True)
class MasterlogHeaderPreset:
    preset_id: str
    names: dict[AppLanguage, str]
    descriptions: dict[AppLanguage, str]
    height_mm: float
    elements: tuple[MasterlogHeaderElement, ...]

    def name(self, language: AppLanguage) -> str:
        return self.names[language]

    def description(self, language: AppLanguage) -> str:
        return self.descriptions[language]


def _texts(ru: str, kk: str, en: str) -> dict[AppLanguage, str]:
    return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}


def _element(
    element_id: str,
    element_type: str,
    x: float,
    y: float,
    width_mm: float,
    height_mm: float,
    **properties: object,
) -> MasterlogHeaderElement:
    return MasterlogHeaderElement(element_id, element_type, x, y, width_mm, height_mm, properties)


STANDARD_HEADER = MasterlogHeaderPreset(
    "project_well",
    _texts("Проект и скважина", "Жоба және ұңғыма", "Project and well"),
    _texts(
        "Универсальная редактируемая шапка с реквизитами проекта и подрядчика.",
        "Жоба мен мердігер деректемелері бар өңделетін әмбебап тақырып.",
        "Editable general header with project and contractor details.",
    ),
    42.0,
    (
        _element(
            "title", "text", 5, 3, 200, 8, text="MASTERLOG", font_size_mm=6.0, color="#0f172a"
        ),
        _element(
            "project_label",
            "text",
            5,
            14,
            25,
            6,
            text="Project:",
            font_size_mm=3.2,
            color="#334155",
        ),
        _element(
            "project",
            "field",
            30,
            14,
            70,
            6,
            field="project.name",
            font_size_mm=3.5,
            color="#0f172a",
        ),
        _element(
            "well_label", "text", 105, 14, 20, 6, text="Well:", font_size_mm=3.2, color="#334155"
        ),
        _element(
            "well", "field", 125, 14, 80, 6, field="well.name", font_size_mm=3.5, color="#0f172a"
        ),
        _element(
            "dataset_label",
            "text",
            5,
            23,
            25,
            6,
            text="Dataset:",
            font_size_mm=3.2,
            color="#334155",
        ),
        _element(
            "dataset",
            "field",
            30,
            23,
            70,
            6,
            field="dataset.name",
            font_size_mm=3.5,
            color="#0f172a",
        ),
        _element(
            "operator",
            "text",
            105,
            23,
            48,
            6,
            text="Operator: [edit]",
            font_size_mm=3.2,
            color="#334155",
        ),
        _element(
            "contractor",
            "text",
            155,
            23,
            50,
            6,
            text="Contractor: [edit]",
            font_size_mm=3.2,
            color="#334155",
        ),
        _element("separator", "line", 5, 34, 200, 0.1, color="#334155", width=0.6),
    ),
)

COMPACT_HEADER = MasterlogHeaderPreset(
    "compact",
    _texts("Компактная", "Ықшам", "Compact"),
    _texts(
        "Низкая шапка для длинного разреза.",
        "Ұзын қимаға арналған ықшам тақырып.",
        "Low header for long sections.",
    ),
    25.0,
    (
        _element("title", "text", 5, 3, 55, 7, text="MASTERLOG", font_size_mm=5.0, color="#0f172a"),
        _element(
            "project",
            "field",
            62,
            3,
            65,
            7,
            field="project.name",
            font_size_mm=3.5,
            color="#0f172a",
        ),
        _element(
            "well", "field", 130, 3, 75, 7, field="well.name", font_size_mm=3.5, color="#0f172a"
        ),
        _element(
            "dataset",
            "field",
            5,
            13,
            100,
            6,
            field="dataset.name",
            font_size_mm=3.2,
            color="#334155",
        ),
        _element(
            "rig",
            "text",
            110,
            13,
            95,
            6,
            text="Rig / Unit: [edit]",
            font_size_mm=3.2,
            color="#334155",
        ),
    ),
)

BUILTIN_MASTERLOG_HEADER_PRESETS = (STANDARD_HEADER, COMPACT_HEADER)


def _columns(
    *items: tuple[str, str, str, float, list[str], str, float | None, float | None],
) -> list[MasterlogColumnTemplate]:
    return [
        MasterlogColumnTemplate(
            column_id,
            title,
            column_type,
            width,
            curves,
            x_scale=scale,
            x_min=x_min,
            x_max=x_max,
        )
        for column_id, title, column_type, width, curves, scale, x_min, x_max in items
    ]


BUILTIN_MASTERLOG_FORM_PRESETS = (
    MasterlogFormPreset(
        "international_mudlog",
        _texts("Полевой Masterlog", "Далалық Masterlog", "Field Masterlog"),
        _texts(
            "Нейтральный отраслевой образец: бурение, литология, газ и описание.",
            "Бұрғылау, литология, газ және сипаттамасы бар бейтарап салалық үлгі.",
            "Neutral industry layout for drilling, lithology, gas and descriptions.",
        ),
        MasterlogTemplate(
            "preset:international_mudlog",
            "Field Masterlog",
            header_elements=list(deepcopy(STANDARD_HEADER.elements)),
            columns=_columns(
                ("depth", "Depth", "depth", 14, [], "linear", None, None),
                (
                    "drilling",
                    "ROP / WOB / RPM / TORQUE",
                    "curves",
                    42,
                    ["ROP", "WOB", "RPM", "TORQUE"],
                    "linear",
                    0,
                    200,
                ),
                ("lithology", "Lithology", "lithology", 25, [], "linear", None, None),
                ("cuttings", "Cuttings %", "cuttings", 32, [], "linear", None, None),
                ("calcimetry", "Calcimetry", "calcimetry", 30, [], "linear", 0, 100),
                ("lba", "LBA", "lba", 42, [], "linear", None, None),
                (
                    "gas",
                    "TG / C1 / C2 / C3 / iC4 / nC4 / iC5 / nC5",
                    "curves",
                    62,
                    ["TG", "C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5"],
                    "logarithmic",
                    1,
                    1000000,
                ),
                ("description", "Lithological description", "text", 67, [], "linear", None, None),
            ),
            properties={"preset_origin": "international_mudlog", "orientation": "landscape"},
        ),
    ),
    MasterlogFormPreset(
        "gas_evaluation",
        _texts("Газовый Masterlog", "Газдық Masterlog", "Gas evaluation Masterlog"),
        _texts(
            "Форма для компонентного газа и расчётных Gas Ratio.",
            "Компоненттік газ және Gas Ratio есептері үшін пішін.",
            "Layout for component gas and calculated Gas Ratio curves.",
        ),
        MasterlogTemplate(
            "preset:gas_evaluation",
            "Gas evaluation Masterlog",
            header_elements=list(deepcopy(COMPACT_HEADER.elements)),
            header_height_mm=COMPACT_HEADER.height_mm,
            columns=_columns(
                ("depth", "Depth", "depth", 14, [], "linear", None, None),
                (
                    "gas",
                    "Gas components",
                    "curves",
                    70,
                    ["TG", "C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5"],
                    "logarithmic",
                    1,
                    1000000,
                ),
                (
                    "ratios",
                    "Wetness / Balance / Character / Pixler",
                    "curves",
                    55,
                    ["WETNESS", "BALANCE", "CHARACTER", "PIXLER"],
                    "linear",
                    0,
                    100,
                ),
                ("lithology", "Lithology", "lithology", 25, [], "linear", None, None),
                ("description", "Description", "text", 46, [], "linear", None, None),
            ),
            properties={"preset_origin": "gas_evaluation", "orientation": "landscape"},
        ),
    ),
    MasterlogFormPreset(
        "geological_description",
        _texts("Геологическое описание", "Геологиялық сипаттама", "Geological description"),
        _texts(
            "Расширенная литологическая колонка и текстовое описание шлама.",
            "Кеңейтілген литологиялық баған және шламның мәтіндік сипаттамасы.",
            "Expanded lithology column and textual cuttings description.",
        ),
        MasterlogTemplate(
            "preset:geological_description",
            "Geological description",
            header_elements=list(deepcopy(STANDARD_HEADER.elements)),
            columns=_columns(
                ("depth", "Depth", "depth", 14, [], "linear", None, None),
                ("drilling", "ROP / GR", "curves", 38, ["ROP", "GR"], "linear", 0, 200),
                ("lithology", "Lithology", "lithology", 38, [], "linear", None, None),
                (
                    "description",
                    "Cuttings / shows / interpretation",
                    "text",
                    120,
                    [],
                    "linear",
                    None,
                    None,
                ),
            ),
            properties={"preset_origin": "geological_description", "orientation": "landscape"},
        ),
    ),
)


def builtin_form_preset(preset_id: str) -> MasterlogFormPreset:
    try:
        return next(item for item in BUILTIN_MASTERLOG_FORM_PRESETS if item.preset_id == preset_id)
    except StopIteration as exc:
        raise KeyError(f"Встроенный образец masterlog не найден: {preset_id}") from exc


def builtin_header_preset(preset_id: str) -> MasterlogHeaderPreset:
    try:
        return next(
            item for item in BUILTIN_MASTERLOG_HEADER_PRESETS if item.preset_id == preset_id
        )
    except StopIteration as exc:
        raise KeyError(f"Встроенный образец шапки не найден: {preset_id}") from exc
