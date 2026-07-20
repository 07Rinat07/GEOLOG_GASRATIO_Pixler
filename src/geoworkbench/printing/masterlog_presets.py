from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
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

LITHOLOGY_HEADER = MasterlogHeaderPreset(
    "project_well_lithology",
    _texts(
        "Проект, скважина и литология",
        "Жоба, ұңғыма және литология",
        "Project, well and lithology",
    ),
    _texts(
        "Расширенная шапка с автоматически формируемой литологической легендой.",
        "Автоматты литологиялық шартты белгілері бар кеңейтілген тақырып.",
        "Extended header with an automatically generated lithology legend.",
    ),
    60.0,
    tuple(deepcopy(STANDARD_HEADER.elements))
    + (
        _element(
            "lithology_legend",
            "lithology_legend",
            5,
            35,
            200,
            22,
            scope="all",
            columns=5,
            show_code=True,
            font_size_mm=2.6,
        ),
    ),
)

GEOLOGICAL_GEOCHEMICAL_HEADER = MasterlogHeaderPreset(
    "geological_geochemical",
    _texts(
        "Геолого-геохимический Masterlog",
        "Геологиялық-геохимиялық Masterlog",
        "Geological-geochemical Masterlog",
    ),
    _texts(
        "Редактируемая шапка по переданному эталону: реквизиты скважины, легенды, конструкция и исполнители.",
        "Берілген эталон бойынша өңделетін тақырып: ұңғыма деректері, шартты белгілер, конструкция және орындаушылар.",
        "Editable reference-based header with well metadata, legends, construction and personnel.",
    ),
    110.0,
    (
        _element(
            "geo_title", "text", 92, 2, 155, 10,
            text="МАСТЕРЛОГ", font_size_mm=6.2, color="#0f172a",
            bold=True, alignment="center", frame=True,
        ),
        _element("geo_country_label", "text", 5, 3, 28, 5, text="СТРАНА", font_size_mm=2.4, color="#334155", bold=True),
        _element("geo_country", "field", 34, 3, 52, 5, field="header.country", font_size_mm=2.8, color="#0f172a", frame=True),
        _element("geo_customer_label", "text", 252, 3, 30, 5, text="ЗАКАЗЧИК", font_size_mm=2.4, color="#334155", bold=True),
        _element("geo_customer", "field", 282, 3, 52, 5, field="header.customer", font_size_mm=2.6, color="#0f172a", frame=True),

        _element("geo_field_label", "text", 5, 10, 28, 5, text="Месторождение", font_size_mm=2.3, color="#334155"),
        _element("geo_field", "field", 34, 10, 52, 5, field="header.field", font_size_mm=2.7, color="#0f172a", frame=True),
        _element("geo_well_label", "text", 5, 17, 28, 5, text="СКВАЖИНА", font_size_mm=2.4, color="#334155", bold=True),
        _element("geo_well", "field", 34, 17, 52, 5, field="header.well_number", font_size_mm=3.0, color="#0f172a", bold=True, frame=True),
        _element("geo_interval_label", "text", 5, 24, 28, 5, text="Интервал", font_size_mm=2.3, color="#334155"),
        _element("geo_interval", "field", 34, 24, 52, 5, field="header.interval", font_size_mm=2.7, color="#0f172a", frame=True),
        _element("geo_scale_label", "text", 5, 31, 28, 5, text="Масштаб", font_size_mm=2.3, color="#334155"),
        _element("geo_scale", "field", 34, 31, 52, 5, field="header.scale", font_size_mm=2.7, color="#0f172a", frame=True),

        _element("geo_project_label", "text", 92, 14, 30, 5, text="Проект", font_size_mm=2.3, color="#334155"),
        _element("geo_project", "field", 122, 14, 60, 5, field="project.name", font_size_mm=2.7, color="#0f172a", frame=True),
        _element("geo_dataset_label", "text", 184, 14, 26, 5, text="Набор", font_size_mm=2.3, color="#334155"),
        _element("geo_dataset", "field", 210, 14, 37, 5, field="dataset.name", font_size_mm=2.5, color="#0f172a", frame=True),
        _element("geo_contractor_label", "text", 92, 21, 30, 5, text="Исполнитель", font_size_mm=2.3, color="#334155"),
        _element("geo_contractor", "field", 122, 21, 125, 5, field="header.contractor", font_size_mm=2.6, color="#0f172a", frame=True),
        _element("geo_driller_label", "text", 92, 28, 30, 5, text="Буровая компания", font_size_mm=2.2, color="#334155"),
        _element("geo_driller", "field", 122, 28, 125, 5, field="header.drilling_company", font_size_mm=2.6, color="#0f172a", frame=True),
        _element("geo_engineers_label", "text", 92, 35, 30, 5, text="Инженеры / геологи", font_size_mm=2.2, color="#334155"),
        _element("geo_engineers", "field", 122, 35, 125, 8, field="header.engineers", font_size_mm=2.5, color="#0f172a", frame=True),

        _element("geo_actual_label", "text", 252, 10, 38, 5, text="Фактическая глубина", font_size_mm=2.2, color="#334155"),
        _element("geo_actual", "field", 290, 10, 44, 5, field="header.actual_depth", font_size_mm=2.7, color="#0f172a", frame=True, alignment="center"),
        _element("geo_project_depth_label", "text", 252, 17, 38, 5, text="Проектная глубина", font_size_mm=2.2, color="#334155"),
        _element("geo_project_depth", "field", 290, 17, 44, 5, field="header.project_depth", font_size_mm=2.7, color="#0f172a", frame=True, alignment="center"),
        _element("geo_start_label", "text", 252, 24, 38, 5, text="Начало бурения", font_size_mm=2.2, color="#334155"),
        _element("geo_start", "field", 290, 24, 44, 5, field="header.start_date", font_size_mm=2.6, color="#0f172a", frame=True),
        _element("geo_end_label", "text", 252, 31, 38, 5, text="Конец бурения", font_size_mm=2.2, color="#334155"),
        _element("geo_end", "field", 290, 31, 44, 5, field="header.end_date", font_size_mm=2.6, color="#0f172a", frame=True),
        _element("geo_lat_label", "text", 252, 38, 18, 5, text="Широта", font_size_mm=2.2, color="#334155"),
        _element("geo_lat", "field", 270, 38, 64, 5, field="header.latitude", font_size_mm=2.5, color="#0f172a", frame=True),
        _element("geo_lon_label", "text", 252, 45, 18, 5, text="Долгота", font_size_mm=2.2, color="#334155"),
        _element("geo_lon", "field", 270, 45, 64, 5, field="header.longitude", font_size_mm=2.5, color="#0f172a", frame=True),

        _element("geo_rig_floor_label", "text", 5, 38, 28, 5, text="Высота ротора", font_size_mm=2.2, color="#334155"),
        _element("geo_rig_floor", "field", 34, 38, 52, 5, field="header.rig_floor", font_size_mm=2.5, color="#0f172a", frame=True),
        _element("geo_altitude_label", "text", 5, 45, 28, 5, text="Альтитуда устья", font_size_mm=2.2, color="#334155"),
        _element("geo_altitude", "field", 34, 45, 52, 5, field="header.wellhead_altitude", font_size_mm=2.5, color="#0f172a", frame=True),
        _element("geo_well_type_label", "text", 92, 45, 30, 5, text="Вид скважины", font_size_mm=2.2, color="#334155"),
        _element("geo_well_type", "field", 122, 45, 58, 5, field="header.well_type", font_size_mm=2.5, color="#0f172a", frame=True),
        _element("geo_rig_label", "text", 182, 45, 24, 5, text="Буровая", font_size_mm=2.2, color="#334155"),
        _element("geo_rig", "field", 206, 45, 41, 5, field="header.rig", font_size_mm=2.5, color="#0f172a", frame=True),

        _element("geo_separator", "line", 5, 53, 329, 0.1, color="#334155", width=0.5),
        _element(
            "geo_lithology_legend", "lithology_legend", 5, 56, 148, 49,
            scope="all", columns=4, show_code=True, font_size_mm=2.05, color="#0f172a", frame=True,
        ),
        _element(
            "geo_lba_legend", "lba_legend", 156, 56, 74, 49,
            font_size_mm=1.95, color="#0f172a", frame=True,
        ),
        _element(
            "geo_hc_legend", "text", 233, 56, 48, 49,
            text="УСЛОВНЫЕ ОБОЗНАЧЕНИЯ\n● Фоновый газ\n◆ Газ пластовый\n▲ Газ СПО\n■ Газ-тест\n○ Нефтепроявление\n◉ Нефтенасыщенность\n✦ Керн с признаками УВ",
            font_size_mm=1.95, color="#0f172a", bold=True, frame=True,
        ),
        _element(
            "geo_construction", "field", 284, 56, 50, 49,
            field="header.well_construction", font_size_mm=1.9, color="#0f172a",
            frame=True, alignment="left",
        ),
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

BUILTIN_MASTERLOG_HEADER_PRESETS = (
    STANDARD_HEADER,
    LITHOLOGY_HEADER,
    GEOLOGICAL_GEOCHEMICAL_HEADER,
    COMPACT_HEADER,
)


def _columns(
    *items: tuple[str, str, str, float, list[str], str, float | None, float | None],
) -> list[MasterlogColumnTemplate]:
    palette = ("#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2")
    columns: list[MasterlogColumnTemplate] = []
    for column_id, title, column_type, width, curves, scale, x_min, x_max in items:
        styles = {
            mnemonic: MasterlogCurveStyle(
                palette[index % len(palette)],
                1.5,
                "solid",
                x_min,
                x_max,
            )
            for index, mnemonic in enumerate(curves)
        }
        columns.append(
            MasterlogColumnTemplate(
                column_id,
                title,
                column_type,
                width,
                curves,
                x_scale=scale,
                x_min=x_min,
                x_max=x_max,
                curve_styles=styles,
                grid_x=bool(curves),
                grid_y=bool(curves),
                grid_major_divisions=5,
                grid_minor_divisions=5,
                grid_alpha=0.22,
            )
        )
    return columns


def _reference_drilling_column() -> MasterlogColumnTemplate:
    curves = ["WOB", "ROP", "DMC", "DEXP"]
    return MasterlogColumnTemplate(
        "drilling_geotech",
        "Нагрузка / скорость проходки / D-экспонента",
        "curves",
        58.0,
        curves,
        x_scale="linear",
        show_legend=True,
        curve_styles={
            "WOB": MasterlogCurveStyle("#2563eb", 1.4, "solid", 0.0, 20.0),
            "ROP": MasterlogCurveStyle("#dc2626", 1.3, "solid", 0.0, 100.0),
            "DMC": MasterlogCurveStyle("#ef4444", 1.0, "dash", 0.0, 50.0),
            "DEXP": MasterlogCurveStyle("#7c3aed", 1.4, "solid", 0.0, 3.0),
        },
        grid_x=True,
        grid_y=True,
        grid_major_divisions=5,
        grid_minor_divisions=5,
        grid_alpha=0.24,
    )


def _reference_gas_column() -> MasterlogColumnTemplate:
    curves = ["C1", "C2", "C3", "C4", "IC4", "C5", "IC5", "TG"]
    palette = ("#dc2626", "#84cc16", "#22d3ee", "#fb923c", "#65a30d", "#9333ea", "#d946ef", "#ef4444")
    return MasterlogColumnTemplate(
        "component_gas",
        "Газовые компоненты C1-C5 и сумма газов",
        "curves",
        72.0,
        curves,
        x_scale="logarithmic",
        x_min=0.001,
        x_max=100.0,
        show_legend=True,
        curve_styles={
            mnemonic: MasterlogCurveStyle(color, 1.25, "solid", 0.001, 100.0)
            for mnemonic, color in zip(curves, palette, strict=True)
        },
        grid_x=True,
        grid_y=True,
        grid_major_divisions=5,
        grid_minor_divisions=10,
        grid_alpha=0.23,
    )


BUILTIN_MASTERLOG_FORM_PRESETS = (
    MasterlogFormPreset(
        "geological_geochemical_reference",
        _texts(
            "Геолого-геохимический Masterlog",
            "Геологиялық-геохимиялық Masterlog",
            "Geological-geochemical Masterlog",
        ),
        _texts(
            "Рабочая форма по образцу: стратиграфия, бурение, глубина, шламограмма, ЛБА, кальциметрия, литология, газ и описание пород.",
            "Үлгі бойынша жұмыс пішіні: стратиграфия, бұрғылау, тереңдік, шламограмма, ЛБА, кальциметрия, литология, газ және жыныс сипаттамасы.",
            "Reference working layout with stratigraphy, drilling, depth, cuttings, LBA, calcimetry, lithology, gas and rock description.",
        ),
        MasterlogTemplate(
            "preset:geological_geochemical_reference",
            "Geological-geochemical Masterlog",
            header_height_mm=GEOLOGICAL_GEOCHEMICAL_HEADER.height_mm,
            header_elements=list(deepcopy(GEOLOGICAL_GEOCHEMICAL_HEADER.elements)),
            columns=[
                MasterlogColumnTemplate("stratigraphy", "Стратиграфия", "stratigraphy", 20.0),
                _reference_drilling_column(),
                MasterlogColumnTemplate("depth", "Глубина, м", "depth", 14.0),
                MasterlogColumnTemplate("cuttings", "Шламограмма, %", "cuttings", 34.0),
                MasterlogColumnTemplate("lba", "ЛБА", "lba", 24.0),
                MasterlogColumnTemplate(
                    "calcimetry",
                    "Карбонатность / кальциметрия, %",
                    "calcimetry",
                    28.0,
                    ["CACO3", "CAMG_CO3_2"],
                    x_scale="linear",
                    x_min=0.0,
                    x_max=100.0,
                    show_legend=True,
                    curve_styles={
                        "CACO3": MasterlogCurveStyle("#06b6d4", 1.4, "solid", 0.0, 100.0),
                        "CAMG_CO3_2": MasterlogCurveStyle("#8b5cf6", 1.4, "solid", 0.0, 100.0),
                    },
                    grid_x=True,
                    grid_y=True,
                    grid_major_divisions=5,
                    grid_minor_divisions=5,
                    grid_alpha=0.2,
                ),
                MasterlogColumnTemplate("lithology", "Литология", "lithology", 34.0),
                _reference_gas_column(),
                MasterlogColumnTemplate("description", "Описание пород и шлама", "cuttings_description", 112.0),
            ],
            properties={
                "preset_origin": "geological_geochemical_reference",
                "orientation": "landscape",
                "reference_document": "Masterlog Akshabulak well 494",
                "editable_columns": True,
            },
        ),
    ),
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
            header_height_mm=LITHOLOGY_HEADER.height_mm,
            header_elements=list(deepcopy(LITHOLOGY_HEADER.elements)),
            columns=_columns(
                (
                    "drilling",
                    "Drilling parameters: ROP / WOB / TORQUE / GR",
                    "curves",
                    42,
                    ["ROP", "WOB", "TORQUE", "GR"],
                    "linear",
                    0,
                    200,
                ),
                ("depth", "Depth", "depth", 14, [], "linear", None, None),
                (
                    "core_slide",
                    "Core / slide interval",
                    "curves",
                    18,
                    ["CORE_FLAG", "SLIDE_FLAG"],
                    "linear",
                    0,
                    1,
                ),
                ("cuttings", "Cuttings %", "cuttings", 32, [], "linear", None, None),
                (
                    "direct_fluorescence",
                    "Direct fluorescence",
                    "curves",
                    18,
                    ["DIR_FLUOR"],
                    "linear",
                    0,
                    5,
                ),
                (
                    "cut_fluorescence",
                    "Cut fluorescence",
                    "curves",
                    18,
                    ["CUT_FLUOR"],
                    "linear",
                    0,
                    5,
                ),
                (
                    "resistivity",
                    "ILM / ILD",
                    "curves",
                    42,
                    ["ILM", "ILD"],
                    "logarithmic",
                    0.2,
                    2000,
                ),
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
                (
                    "calcimetry",
                    "Total CO₃ / CaCO₃ / MgCO₃",
                    "calcimetry",
                    30,
                    ["CACO3", "CAMG_CO3_2"],
                    "linear",
                    0,
                    100,
                ),
                ("lithology", "Lithology", "lithology", 25, [], "linear", None, None),
                (
                    "interpretation",
                    "Interpretation",
                    "analysis_interpretation",
                    34,
                    [],
                    "linear",
                    None,
                    None,
                ),
                (
                    "description",
                    "Lith description and others",
                    "cuttings_description",
                    72,
                    [],
                    "linear",
                    None,
                    None,
                ),
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
            header_height_mm=LITHOLOGY_HEADER.height_mm,
            header_elements=list(deepcopy(LITHOLOGY_HEADER.elements)),
            columns=_columns(
                ("depth", "Depth", "depth", 14, [], "linear", None, None),
                ("stratigraphy", "Stratigraphy", "stratigraphy", 35, [], "linear", None, None),
                ("drilling", "ROP / GR", "curves", 38, ["ROP", "GR"], "linear", 0, 200),
                ("lithology", "Lithology", "lithology", 38, [], "linear", None, None),
                (
                    "description",
                    "Cuttings / shows / interpretation",
                    "cuttings_description",
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
