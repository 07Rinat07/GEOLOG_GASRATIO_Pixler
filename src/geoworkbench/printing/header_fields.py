from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class HeaderFieldDefinition:
    field_id: str
    ru: str
    kk: str
    en: str
    default: str = ""
    multiline: bool = False

    def label(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.kk
        if language is AppLanguage.EN:
            return self.en
        return self.ru


_SYSTEM_FIELDS: tuple[HeaderFieldDefinition, ...] = (
    HeaderFieldDefinition("project.name", "Название проекта", "Жоба атауы", "Project name"),
    HeaderFieldDefinition("well.name", "Название скважины", "Ұңғыма атауы", "Well name"),
    HeaderFieldDefinition("dataset.name", "Набор данных", "Деректер жинағы", "Dataset"),
    HeaderFieldDefinition("dataset.source_name", "Исходный файл", "Бастапқы файл", "Source file"),
    HeaderFieldDefinition("dataset.depth_min", "Начальная глубина", "Бастапқы тереңдік", "Start depth"),
    HeaderFieldDefinition("dataset.depth_max", "Конечная глубина", "Соңғы тереңдік", "End depth"),
    HeaderFieldDefinition("dataset.interval", "Диапазон набора", "Деректер ауқымы", "Dataset interval"),
    HeaderFieldDefinition("dataset.sample_count", "Количество отсчётов", "Өлшем саны", "Sample count"),
)

_EDITABLE_FIELDS: tuple[HeaderFieldDefinition, ...] = (
    HeaderFieldDefinition("header.country", "Страна", "Ел", "Country", "Казахстан"),
    HeaderFieldDefinition("header.field", "Месторождение", "Кен орны", "Field"),
    HeaderFieldDefinition("header.well_number", "Номер скважины", "Ұңғыма нөмірі", "Well number"),
    HeaderFieldDefinition("header.customer", "Заказчик", "Тапсырыс беруші", "Customer"),
    HeaderFieldDefinition("header.contractor", "Исполнитель", "Орындаушы", "Contractor"),
    HeaderFieldDefinition(
        "header.drilling_company", "Буровая компания", "Бұрғылау компаниясы", "Drilling company"
    ),
    HeaderFieldDefinition("header.actual_depth", "Фактическая глубина", "Нақты тереңдік", "Actual depth"),
    HeaderFieldDefinition("header.project_depth", "Проектная глубина", "Жобалық тереңдік", "Planned depth"),
    HeaderFieldDefinition("header.interval", "Интервал исследований", "Зерттеу аралығы", "Survey interval"),
    HeaderFieldDefinition("header.scale", "Масштаб", "Масштаб", "Scale", "1:500"),
    HeaderFieldDefinition("header.start_date", "Начало бурения", "Бұрғылау басталуы", "Spud date"),
    HeaderFieldDefinition("header.end_date", "Конец бурения", "Бұрғылау аяқталуы", "End drilling date"),
    HeaderFieldDefinition("header.latitude", "Широта", "Ендік", "Latitude"),
    HeaderFieldDefinition("header.longitude", "Долгота", "Бойлық", "Longitude"),
    HeaderFieldDefinition("header.rig_floor", "Высота ротора", "Ротор биіктігі", "Rig floor elevation"),
    HeaderFieldDefinition(
        "header.wellhead_altitude", "Альтитуда устья", "Саға альтитудасы", "Wellhead altitude"
    ),
    HeaderFieldDefinition("header.well_type", "Вид скважины", "Ұңғыма түрі", "Well type"),
    HeaderFieldDefinition("header.rig", "Буровая установка", "Бұрғылау қондырғысы", "Drilling rig"),
    HeaderFieldDefinition("header.engineers", "Инженеры / геологи", "Инженерлер / геологтар", "Engineers / geologists"),
    HeaderFieldDefinition(
        "header.well_construction",
        "Конструкция скважины",
        "Ұңғыма конструкциясы",
        "Well construction",
        multiline=True,
    ),
    HeaderFieldDefinition("header.notes", "Примечание", "Ескерту", "Notes", multiline=True),
)

HEADER_FIELD_DEFINITIONS: tuple[HeaderFieldDefinition, ...] = _SYSTEM_FIELDS + _EDITABLE_FIELDS
SUPPORTED_HEADER_FIELDS = tuple(item.field_id for item in HEADER_FIELD_DEFINITIONS)
EDITABLE_HEADER_FIELDS = tuple(item.field_id for item in _EDITABLE_FIELDS)

_FIELD_BY_ID = {item.field_id: item for item in HEADER_FIELD_DEFINITIONS}

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "header.country": ("CTRY", "COUNTRY"),
    "header.field": ("FLD", "FIELD"),
    "header.well_number": ("WELL", "WELLNO", "WELL_NUM", "WELLNUMBER"),
    "header.customer": ("CLIENT", "CUSTOMER", "OPERATOR", "COMP"),
    "header.contractor": ("SRVC", "SERVICE", "CONTRACTOR"),
    "header.drilling_company": ("DRILLING_COMPANY", "DRILLER", "RIG_COMPANY"),
    "header.actual_depth": ("TD", "STOP", "TDEP"),
    "header.project_depth": ("PD", "PROJ_DEPTH", "PLANNED_DEPTH"),
    "header.start_date": ("SPUD", "SPUD_DATE", "START_DATE"),
    "header.end_date": ("END_DATE", "FINISH_DATE", "TD_DATE"),
    "header.latitude": ("LATI", "LAT", "LATITUDE"),
    "header.longitude": ("LONG", "LON", "LONGITUDE"),
    "header.rig_floor": ("KB", "EREF", "RKB", "RIG_FLOOR"),
    "header.wellhead_altitude": ("GL", "ELEV", "WELLHEAD_ALTITUDE"),
    "header.well_type": ("WELL_TYPE", "TYPE"),
    "header.rig": ("RIG", "RIG_NAME"),
}


def header_field_label(field_name: str, language: AppLanguage) -> str:
    definition = _FIELD_BY_ID.get(field_name)
    return definition.label(language) if definition is not None else field_name


def editable_header_field_definitions() -> tuple[HeaderFieldDefinition, ...]:
    return _EDITABLE_FIELDS


def header_field_defaults() -> dict[str, str]:
    return {item.field_id: item.default for item in _EDITABLE_FIELDS if item.default}


def template_header_values(template: MasterlogTemplate) -> dict[str, str]:
    raw = template.properties.get("header_fields", {})
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, (str, int, float))
    }


def resolve_header_field(
    session: ProjectSession,
    field_name: str,
    template: MasterlogTemplate | None = None,
) -> str | None:
    if field_name == "project.name":
        return session.project.name
    if field_name == "well.name":
        return session.current_well.name if session.current_well is not None else None
    if field_name == "dataset.name":
        return session.current_dataset.name if session.current_dataset is not None else None
    if field_name == "dataset.source_name":
        source = session.current_dataset.source_path if session.current_dataset is not None else None
        return Path(source).name if source is not None else None
    if field_name == "dataset.sample_count":
        dataset = session.current_dataset
        return str(len(dataset.depth)) if dataset is not None else None
    if field_name in {"dataset.depth_min", "dataset.depth_max", "dataset.interval"}:
        return _resolve_dataset_depth(session, field_name)
    if field_name.startswith("header."):
        return _resolve_editable_header_field(session, field_name, template)
    return None


def _resolve_editable_header_field(
    session: ProjectSession,
    field_name: str,
    template: MasterlogTemplate | None,
) -> str | None:
    if template is not None:
        value = template_header_values(template).get(field_name, "").strip()
        if value:
            return value

    dataset = session.current_dataset
    if dataset is not None:
        value = _first_dataset_header(dataset.headers, _HEADER_ALIASES.get(field_name, ()))
        if value:
            return value

    if field_name == "header.well_number" and session.current_well is not None:
        return session.current_well.name
    if field_name == "header.actual_depth":
        return _resolve_dataset_depth(session, "dataset.depth_max")
    if field_name == "header.interval":
        return _resolve_dataset_depth(session, "dataset.interval")

    definition = _FIELD_BY_ID.get(field_name)
    return definition.default if definition is not None and definition.default else None


def _resolve_dataset_depth(session: ProjectSession, field_name: str) -> str | None:
    dataset = session.current_dataset
    if dataset is None:
        return None
    values = np.asarray(dataset.depth, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    minimum = float(np.min(finite))
    maximum = float(np.max(finite))
    unit = (dataset.active_index.unit or "м").strip()
    if field_name == "dataset.depth_min":
        return f"{minimum:g} {unit}".strip()
    if field_name == "dataset.depth_max":
        return f"{maximum:g} {unit}".strip()
    return f"{minimum:g}–{maximum:g} {unit}".strip()


def _first_dataset_header(headers: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    normalized = {str(key).strip().upper(): str(value).strip() for key, value in headers.items()}
    for alias in aliases:
        value = normalized.get(alias.upper())
        if value:
            return value
    return None
