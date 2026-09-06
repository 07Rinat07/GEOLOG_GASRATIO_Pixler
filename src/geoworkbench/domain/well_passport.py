from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import isfinite
import re

from geoworkbench.domain.localized_content import validate_localized_texts


CONSTRUCTION_ROWS = 5
CONSTRUCTION_FIELDS = frozenset(
    f"header.casing_{row}_{part}"
    for row in range(CONSTRUCTION_ROWS)
    for part in ("diameter", "name", "depth")
)
SHARED_TEXT_FIELDS = frozenset({"header.well_number", "header.rig"})
LOCALIZED_FIELDS = frozenset(
    f"header.{name}"
    for name in (
        "country",
        "field",
        "region",
        "district",
        "target",
        "customer",
        "contractor",
        "drilling_company",
        "geologists",
        "engineers",
        "well_type",
        "customer_representative",
        "shift_personnel",
        "well_construction",
        "notes",
    )
) | frozenset(f"header.casing_{row}_name" for row in range(CONSTRUCTION_ROWS))
NUMERIC_FIELDS = frozenset(
    f"header.{name}"
    for name in (
        "actual_depth",
        "project_depth",
        "rig_floor",
        "wellhead_altitude",
        "latitude",
        "longitude",
    )
) | (CONSTRUCTION_FIELDS - LOCALIZED_FIELDS)
DATE_FIELDS = frozenset({"header.start_date", "header.end_date"})
_DEPTH_FIELDS = frozenset({"header.actual_depth", "header.project_depth"}) | frozenset(
    f"header.casing_{row}_depth" for row in range(CONSTRUCTION_ROWS)
)
_LOGO_ROLES = frozenset({"customer", "contractor"})
_MAX_TEXT_LENGTH = 20_000


class PassportValidationError(ValueError):
    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(message)
        self.field_name = field_name


@dataclass(slots=True)
class WellPassport:
    """Shared well metadata; an active passport never inherits legacy header values."""

    values: dict[str, str | float] = field(default_factory=dict)
    texts_i18n: dict[str, dict[str, str]] = field(default_factory=dict)
    logo_refs: dict[str, str] = field(default_factory=dict)


def validate_passport(passport: WellPassport) -> WellPassport:
    """Return an independent validated copy without changing an editing draft."""

    if not isinstance(passport, WellPassport):
        raise PassportValidationError("", "Паспорт скважины имеет неверный формат")
    if not all(
        isinstance(value, dict)
        for value in (passport.values, passport.texts_i18n, passport.logo_refs)
    ):
        raise PassportValidationError("", "Поля паспорта должны быть объектами")
    normalized = WellPassport()
    for field_name, value in passport.values.items():
        if field_name not in SHARED_TEXT_FIELDS | NUMERIC_FIELDS | DATE_FIELDS:
            raise PassportValidationError(str(field_name), "Неизвестное поле паспорта")
        if value == "":
            normalized.values[field_name] = ""
        elif field_name in NUMERIC_FIELDS:
            normalized.values[field_name] = _validated_number(field_name, value)
        elif field_name in DATE_FIELDS:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise PassportValidationError(field_name, "Дата должна иметь формат YYYY-MM-DD")
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise PassportValidationError(field_name, "Указана некорректная дата") from exc
            normalized.values[field_name] = value
        else:
            if not isinstance(value, str) or len(value) > _MAX_TEXT_LENGTH:
                raise PassportValidationError(field_name, "Некорректный текст паспорта")
            normalized.values[field_name] = value.strip()
    start_date = normalized.values.get("header.start_date")
    end_date = normalized.values.get("header.end_date")
    if isinstance(start_date, str) and isinstance(end_date, str) and start_date and end_date:
        if end_date < start_date:
            raise PassportValidationError(
                "header.end_date", "Конец бурения не может предшествовать началу"
            )
    for field_name, translations in passport.texts_i18n.items():
        if field_name not in LOCALIZED_FIELDS:
            raise PassportValidationError(str(field_name), "Неизвестное переводимое поле паспорта")
        if not isinstance(translations, dict):
            raise PassportValidationError(field_name, "Переводы поля должны быть объектом")
        try:
            normalized.texts_i18n[field_name] = validate_localized_texts(
                translations, maximum=_MAX_TEXT_LENGTH
            )
        except ValueError as exc:
            raise PassportValidationError(field_name, str(exc)) from exc
    for role, asset_ref in passport.logo_refs.items():
        if role not in _LOGO_ROLES:
            raise PassportValidationError("", "Неизвестная роль логотипа")
        if not isinstance(asset_ref, str) or (
            asset_ref and not re.fullmatch(r"sha256:[0-9a-f]{64}", asset_ref)
        ):
            raise PassportValidationError("", "Некорректная ссылка на логотип")
        normalized.logo_refs[role] = asset_ref
    return normalized


def _validated_number(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PassportValidationError(field_name, "Значение должно быть числом")
    try:
        number = float(value)
    except OverflowError as exc:
        raise PassportValidationError(field_name, "Число вне допустимого диапазона") from exc
    if not isfinite(number):
        raise PassportValidationError(field_name, "Значение должно быть конечным числом")
    if field_name in _DEPTH_FIELDS and number < 0:
        raise PassportValidationError(field_name, "Глубина не может быть отрицательной")
    if field_name in CONSTRUCTION_FIELDS and field_name.endswith("_diameter") and number <= 0:
        raise PassportValidationError(field_name, "Диаметр должен быть положительным")
    if field_name == "header.latitude" and not -90 <= number <= 90:
        raise PassportValidationError(field_name, "Широта должна быть от -90 до 90 градусов")
    if field_name == "header.longitude" and not -180 <= number <= 180:
        raise PassportValidationError(field_name, "Долгота должна быть от -180 до 180 градусов")
    return number
