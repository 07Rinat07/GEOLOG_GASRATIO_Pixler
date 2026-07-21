from __future__ import annotations


TEXT_ORIENTATIONS = (
    "horizontal",
    "vertical_bottom_to_top",
    "vertical_top_to_bottom",
)

TEXT_VERTICAL_POSITIONS = (
    "top",
    "center",
    "bottom",
)


def normalize_text_orientation(value: str | None) -> str:
    normalized = (value or "horizontal").strip().casefold()
    if normalized not in TEXT_ORIENTATIONS:
        raise ValueError("Неподдерживаемое направление текста")
    return normalized


def normalize_text_vertical_position(value: str | None) -> str:
    normalized = (value or "center").strip().casefold()
    if normalized not in TEXT_VERTICAL_POSITIONS:
        raise ValueError("Неподдерживаемое вертикальное положение текста")
    return normalized


def text_angle(value: str | None) -> float:
    orientation = normalize_text_orientation(value)
    return {
        "horizontal": 0.0,
        "vertical_bottom_to_top": -90.0,
        "vertical_top_to_bottom": 90.0,
    }[orientation]


def text_position_fraction(value: str | None) -> float:
    position = normalize_text_vertical_position(value)
    return {"top": 0.15, "center": 0.5, "bottom": 0.85}[position]
