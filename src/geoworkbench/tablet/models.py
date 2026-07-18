from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
import re


class TrackKind(StrEnum):
    DEPTH = "depth"
    CURVE = "curve"
    GAS = "gas"
    DEXP = "dexp"
    LITHOLOGY = "lithology"
    CUTTINGS = "cuttings"
    CALCIMETRY = "calcimetry"
    LBA = "lba"
    STRATIGRAPHY = "stratigraphy"
    INTERPRETATION = "interpretation"
    TEXT = "text"


class XScale(StrEnum):
    LINEAR = "linear"
    LOGARITHMIC = "logarithmic"


class CurveLineStyle(StrEnum):
    SOLID = "solid"
    DASH = "dash"
    DOT = "dot"
    DASH_DOT = "dash_dot"


@dataclass(frozen=True, slots=True)
class CurveStyle:
    color: str = "#2563eb"
    width: float = 1.5
    line_style: CurveLineStyle = CurveLineStyle.SOLID

    def __post_init__(self) -> None:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.color):
            raise ValueError("Цвет кривой должен быть в формате #RRGGBB")
        if isinstance(self.width, bool) or not isinstance(self.width, (int, float)):
            raise ValueError("Толщина линии должна быть числом")
        if not isfinite(self.width) or not 0.5 <= self.width <= 10.0:
            raise ValueError("Толщина линии должна быть от 0.5 до 10 px")
        if not isinstance(self.line_style, CurveLineStyle):
            raise ValueError("Стиль линии не поддерживается")


@dataclass(slots=True)
class TrackDefinition:
    track_id: str
    title: str
    kind: TrackKind
    curve_mnemonics: list[str] = field(default_factory=list)
    width: int = 260
    visible: bool = True
    locked: bool = False
    x_scale: XScale = XScale.LINEAR
    x_min: float | None = None
    x_max: float | None = None
    curve_styles: dict[str, CurveStyle] = field(default_factory=dict)
    grid_x: bool = True
    grid_y: bool = True
    grid_alpha: float = 0.2
    x_axis_label: str = ""

    def __post_init__(self) -> None:
        if self.width < 80:
            raise ValueError("Ширина трека должна быть не меньше 80 px")
        self._validate_x_settings(self.x_scale, self.x_min, self.x_max)
        if not all(isinstance(key, str) and key.strip() for key in self.curve_styles):
            raise ValueError("Ключи стилей кривых должны быть непустыми строками")
        if not all(isinstance(style, CurveStyle) for style in self.curve_styles.values()):
            raise ValueError("Настройки кривых должны использовать CurveStyle")
        self._validate_grid(self.grid_x, self.grid_y, self.grid_alpha)
        self._validate_x_axis_label(self.x_axis_label)

    def set_x_scale(self, scale: XScale) -> None:
        self._validate_x_settings(scale, self.x_min, self.x_max)
        self.x_scale = scale

    def set_x_range(self, minimum: float | None, maximum: float | None) -> None:
        self._validate_x_settings(self.x_scale, minimum, maximum)
        self.x_min = minimum
        self.x_max = maximum

    def update_view_settings(
        self,
        *,
        width: int,
        x_scale: XScale,
        x_min: float | None,
        x_max: float | None,
    ) -> None:
        if width < 80 or width > 2000:
            raise ValueError("Ширина трека должна быть от 80 до 2000 px")
        self._validate_x_settings(x_scale, x_min, x_max)
        self.width = width
        self.x_scale = x_scale
        self.x_min = x_min
        self.x_max = x_max

    def set_curve_style(self, mnemonic: str, style: CurveStyle) -> None:
        normalized = mnemonic.strip()
        if normalized not in self.curve_mnemonics:
            raise KeyError(f"Кривая отсутствует в треке: {mnemonic}")
        if not isinstance(style, CurveStyle):
            raise ValueError("Настройки кривой должны использовать CurveStyle")
        self.curve_styles[normalized] = style

    def curve_style(self, mnemonic: str) -> CurveStyle | None:
        return self.curve_styles.get(mnemonic)

    def set_grid(self, show_x: bool, show_y: bool, alpha: float) -> None:
        self._validate_grid(show_x, show_y, alpha)
        self.grid_x = show_x
        self.grid_y = show_y
        self.grid_alpha = alpha

    def set_x_axis_label(self, label: str) -> None:
        normalized = label.strip()
        self._validate_x_axis_label(normalized)
        self.x_axis_label = normalized

    @staticmethod
    def _validate_x_axis_label(label: str) -> None:
        if not isinstance(label, str):
            raise ValueError("Подпись оси X должна быть строкой")
        if len(label) > 100:
            raise ValueError("Подпись оси X не должна превышать 100 символов")

    @staticmethod
    def _validate_grid(show_x: bool, show_y: bool, alpha: float) -> None:
        if not isinstance(show_x, bool) or not isinstance(show_y, bool):
            raise ValueError("Параметры видимости сетки должны быть логическими")
        if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
            raise ValueError("Прозрачность сетки должна быть числом")
        if not isfinite(alpha) or not 0.0 <= alpha <= 1.0:
            raise ValueError("Прозрачность сетки должна быть от 0 до 1")

    @staticmethod
    def _validate_x_settings(
        scale: XScale,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        if (minimum is None) != (maximum is None):
            raise ValueError("Минимум и максимум диапазона должны задаваться вместе")
        if minimum is None or maximum is None:
            return
        if not isfinite(minimum) or not isfinite(maximum):
            raise ValueError("Границы диапазона должны быть конечными числами")
        if minimum >= maximum:
            raise ValueError("Минимум диапазона должен быть меньше максимума")
        if scale is XScale.LOGARITHMIC and minimum <= 0:
            raise ValueError("Логарифмический диапазон должен быть положительным")


@dataclass(slots=True)
class TabletLayout:
    tracks: list[TrackDefinition] = field(default_factory=list)
    visible_depth_top: float | None = None
    visible_depth_bottom: float | None = None
    cursor_depth: float | None = None

    def __post_init__(self) -> None:
        self._validate_visible_depth(self.visible_depth_top, self.visible_depth_bottom)
        if self.cursor_depth is not None and not isfinite(self.cursor_depth):
            raise ValueError("Глубина визира должна быть конечным числом или null")

    def add_track(self, track: TrackDefinition, index: int | None = None) -> None:
        if any(existing.track_id == track.track_id for existing in self.tracks):
            raise ValueError(f"Трек уже существует: {track.track_id}")
        if index is None:
            self.tracks.append(track)
        else:
            self.tracks.insert(index, track)

    def remove_track(self, track_id: str) -> TrackDefinition:
        for index, track in enumerate(self.tracks):
            if track.track_id == track_id:
                return self.tracks.pop(index)
        raise KeyError(track_id)

    def track_by_id(self, track_id: str) -> TrackDefinition:
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        raise KeyError(track_id)

    def move_track(self, track_id: str, target_index: int) -> None:
        track = self.remove_track(track_id)
        target_index = max(0, min(target_index, len(self.tracks)))
        self.tracks.insert(target_index, track)

    def visible_tracks(self) -> list[TrackDefinition]:
        return [track for track in self.tracks if track.visible]

    def set_track_width(self, track_id: str, width: int) -> None:
        if width < 80:
            raise ValueError("Ширина трека должна быть не меньше 80 px")
        self.track_by_id(track_id).width = width

    def set_track_visible(self, track_id: str, visible: bool) -> None:
        self.track_by_id(track_id).visible = visible

    def set_track_x_scale(self, track_id: str, scale: XScale) -> None:
        self.track_by_id(track_id).set_x_scale(scale)

    def set_track_x_range(
        self,
        track_id: str,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        self.track_by_id(track_id).set_x_range(minimum, maximum)

    def set_visible_depth(self, top: float | None, bottom: float | None) -> bool:
        self._validate_visible_depth(top, bottom)
        if self.visible_depth_top == top and self.visible_depth_bottom == bottom:
            return False
        self.visible_depth_top = top
        self.visible_depth_bottom = bottom
        return True

    def set_cursor_depth(self, depth: float | None) -> bool:
        if depth is not None and not isfinite(depth):
            raise ValueError("Глубина визира должна быть конечным числом или null")
        if self.cursor_depth == depth:
            return False
        self.cursor_depth = depth
        return True

    def update_track_view_settings(
        self,
        track_id: str,
        *,
        width: int,
        x_scale: XScale,
        x_min: float | None,
        x_max: float | None,
    ) -> None:
        self.track_by_id(track_id).update_view_settings(
            width=width,
            x_scale=x_scale,
            x_min=x_min,
            x_max=x_max,
        )

    @staticmethod
    def _validate_visible_depth(top: float | None, bottom: float | None) -> None:
        if (top is None) != (bottom is None):
            raise ValueError("Границы видимого интервала должны задаваться вместе")
        if top is None or bottom is None:
            return
        if not isfinite(top) or not isfinite(bottom):
            raise ValueError("Границы видимого интервала должны быть конечными")
        if top >= bottom:
            raise ValueError("Верхняя граница глубины должна быть меньше нижней")
