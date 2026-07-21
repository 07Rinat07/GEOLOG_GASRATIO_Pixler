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


def text_graphics_anchor(
    orientation: str | None, position: str | None
) -> tuple[float, float]:
    """Return the anchor that keeps a 0/±90° text item inside its interval.

    For rotated text the original vertical direction maps to the text item's
    horizontal axis.  Anchoring every orientation at its centre makes labels
    selected as *top* or *bottom* extend beyond the interval boundary.
    """

    normalized_orientation = normalize_text_orientation(orientation)
    normalized_position = normalize_text_vertical_position(position)
    if normalized_orientation == "horizontal":
        return (
            0.5,
            {"top": 0.0, "center": 0.5, "bottom": 1.0}[normalized_position],
        )
    if normalized_orientation == "vertical_bottom_to_top":
        return (
            {"top": 1.0, "center": 0.5, "bottom": 0.0}[normalized_position],
            0.5,
        )
    return (
        {"top": 0.0, "center": 0.5, "bottom": 1.0}[normalized_position],
        0.5,
    )


def rotated_text_alignment(orientation: str | None, position: str | None) -> str:
    """Map original top/centre/bottom to left/centre/right after rotation."""

    normalized_orientation = normalize_text_orientation(orientation)
    normalized_position = normalize_text_vertical_position(position)
    if normalized_position == "center":
        return "center"
    if normalized_orientation == "vertical_bottom_to_top":
        return "right" if normalized_position == "top" else "left"
    if normalized_orientation == "vertical_top_to_bottom":
        return "left" if normalized_position == "top" else "right"
    return "center"
