from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class AnnotationStyle:
    """Renderer-neutral style shared by tablet and report annotations."""

    font_family: str = "Arial"
    font_size: float = 10.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    text_color: str = "#0f172a"
    fill_color: str = "#ffffff"
    fill_opacity: float = 0.94
    border_color: str = "#2563eb"
    border_width: float = 1.2
    border_style: str = "solid"
    corner_radius: float = 6.0
    padding: float = 7.0
    alignment: str = "left"
    vertical_alignment: str = "top"
    leader_color: str = "#2563eb"
    leader_width: float = 1.2
    leader_style: str = "solid"
    arrow_style: str = "triangle"
    shadow: bool = True
    shadow_blur: float = 5.0
    shadow_offset_x: float = 2.0
    shadow_offset_y: float = 2.0
    rotation: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "font_family": self.font_family,
            "font_size": self.font_size,
            "bold": self.bold,
            "italic": self.italic,
            "underline": self.underline,
            "text_color": self.text_color,
            "fill_color": self.fill_color,
            "fill_opacity": self.fill_opacity,
            "border_color": self.border_color,
            "border_width": self.border_width,
            "border_style": self.border_style,
            "corner_radius": self.corner_radius,
            "padding": self.padding,
            "alignment": self.alignment,
            "vertical_alignment": self.vertical_alignment,
            "leader_color": self.leader_color,
            "leader_width": self.leader_width,
            "leader_style": self.leader_style,
            "arrow_style": self.arrow_style,
            "shadow": self.shadow,
            "shadow_blur": self.shadow_blur,
            "shadow_offset_x": self.shadow_offset_x,
            "shadow_offset_y": self.shadow_offset_y,
            "rotation": self.rotation,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> AnnotationStyle:
        raw = dict(value or {})
        return cls(
            font_family=_string(raw.get("font_family"), "Arial", maximum=120),
            font_size=_number(raw.get("font_size"), 10.0, 4.0, 96.0),
            bold=bool(raw.get("bold", False)),
            italic=bool(raw.get("italic", False)),
            underline=bool(raw.get("underline", False)),
            text_color=_color(raw.get("text_color"), "#0f172a"),
            fill_color=_color(raw.get("fill_color"), "#ffffff"),
            fill_opacity=_number(raw.get("fill_opacity"), 0.94, 0.0, 1.0),
            border_color=_color(raw.get("border_color"), "#2563eb"),
            border_width=_number(raw.get("border_width"), 1.2, 0.0, 20.0),
            border_style=_choice(raw.get("border_style"), "solid", {"solid", "dash", "dot"}),
            corner_radius=_number(raw.get("corner_radius"), 6.0, 0.0, 64.0),
            padding=_number(raw.get("padding"), 7.0, 0.0, 64.0),
            alignment=_choice(raw.get("alignment"), "left", {"left", "center", "right"}),
            vertical_alignment=_choice(
                raw.get("vertical_alignment"), "top", {"top", "center", "bottom"}
            ),
            leader_color=_color(raw.get("leader_color"), "#2563eb"),
            leader_width=_number(raw.get("leader_width"), 1.2, 0.0, 20.0),
            leader_style=_choice(raw.get("leader_style"), "solid", {"solid", "dash", "dot"}),
            arrow_style=_choice(
                raw.get("arrow_style"), "triangle", {"none", "triangle", "open", "circle"}
            ),
            shadow=bool(raw.get("shadow", True)),
            shadow_blur=_number(raw.get("shadow_blur"), 5.0, 0.0, 32.0),
            shadow_offset_x=_number(raw.get("shadow_offset_x"), 2.0, -64.0, 64.0),
            shadow_offset_y=_number(raw.get("shadow_offset_y"), 2.0, -64.0, 64.0),
            rotation=_number(raw.get("rotation"), 0.0, -180.0, 180.0),
        )


ANNOTATION_STYLE_KEYS = frozenset(AnnotationStyle().to_dict())


def _finite_number(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    normalized = float(value)
    return normalized if isfinite(normalized) else None


def _number(value: object, default: float, minimum: float, maximum: float) -> float:
    normalized = _finite_number(value)
    if normalized is None:
        return default
    return max(minimum, min(maximum, normalized))


def _string(value: object, default: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip()
    return normalized[:maximum] if normalized else default


def _choice(value: object, default: str, choices: set[str]) -> str:
    normalized = str(value) if value is not None else default
    return normalized if normalized in choices else default


def _color(value: object, default: str) -> str:
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
        except ValueError:
            return default
        return value.lower()
    return default


__all__ = ["ANNOTATION_STYLE_KEYS", "AnnotationStyle"]
