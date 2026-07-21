from __future__ import annotations

from geoworkbench.domain.text_presentation import (
    TEXT_ORIENTATIONS,
    TEXT_VERTICAL_POSITIONS,
    normalize_text_orientation,
    normalize_text_vertical_position,
    text_angle,
    text_position_fraction,
)


STRATIGRAPHY_TEXT_ORIENTATIONS = TEXT_ORIENTATIONS
STRATIGRAPHY_TEXT_POSITIONS = TEXT_VERTICAL_POSITIONS


def normalize_stratigraphy_text_orientation(value: str | None) -> str:
    try:
        return normalize_text_orientation(value)
    except ValueError as exc:
        raise ValueError("Неподдерживаемое направление текста стратиграфии") from exc


def normalize_stratigraphy_text_position(value: str | None) -> str:
    try:
        return normalize_text_vertical_position(value)
    except ValueError as exc:
        raise ValueError("Неподдерживаемое положение текста стратиграфии") from exc


def stratigraphy_text_angle(value: str | None) -> float:
    return text_angle(value)


def stratigraphy_text_position_fraction(value: str | None) -> float:
    return text_position_fraction(value)
