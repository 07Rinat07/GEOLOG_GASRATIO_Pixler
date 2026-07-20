from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
import re
from uuid import uuid4

from geoworkbench.tablet.models import CurveStyle, TrackKind, XScale


class FormAxisKind(StrEnum):
    DEPTH = "depth"
    TIME = "time"


class FormTemplateOrigin(StrEnum):
    FACTORY = "factory"
    USER = "user"


@dataclass(frozen=True, slots=True)
class ParameterBinding:
    binding_id: str
    canonical_parameter_id: str
    display_name: str
    source_mnemonic: str | None = None
    unit: str = ""
    visible: bool = True
    style: CurveStyle = field(default_factory=CurveStyle)
    x_scale: XScale = XScale.LINEAR
    x_min: float | None = None
    x_max: float | None = None

    def __post_init__(self) -> None:
        _require_id(self.binding_id, "binding_id")
        _require_id(self.canonical_parameter_id, "canonical_parameter_id")
        _require_text(self.display_name, "display_name", max_length=120)
        if self.source_mnemonic is not None:
            _require_text(self.source_mnemonic, "source_mnemonic", max_length=80)
        _require_text(self.unit, "unit", max_length=40, allow_empty=True)
        _validate_range(self.x_scale, self.x_min, self.x_max)

    @classmethod
    def create(
        cls,
        canonical_parameter_id: str,
        display_name: str,
        *,
        source_mnemonic: str | None = None,
        unit: str = "",
        style: CurveStyle | None = None,
        x_scale: XScale = XScale.LINEAR,
        x_min: float | None = None,
        x_max: float | None = None,
    ) -> ParameterBinding:
        return cls(
            binding_id=str(uuid4()),
            canonical_parameter_id=canonical_parameter_id,
            display_name=display_name,
            source_mnemonic=source_mnemonic,
            unit=unit,
            style=style or CurveStyle(),
            x_scale=x_scale,
            x_min=x_min,
            x_max=x_max,
        )


@dataclass(slots=True)
class FormTrack:
    track_id: str
    title: str
    kind: TrackKind
    bindings: list[ParameterBinding] = field(default_factory=list)
    visible: bool = True
    locked: bool = False
    grid_x: bool = True
    grid_y: bool = True
    grid_alpha: float = 0.2
    x_axis_label: str = ""

    def __post_init__(self) -> None:
        _require_id(self.track_id, "track_id")
        _require_text(self.title, "title", max_length=120)
        if not isinstance(self.kind, TrackKind):
            raise ValueError("kind должен использовать TrackKind")
        if not isinstance(self.visible, bool) or not isinstance(self.locked, bool):
            raise ValueError("visible и locked должны быть логическими")
        if not isinstance(self.grid_x, bool) or not isinstance(self.grid_y, bool):
            raise ValueError("grid_x и grid_y должны быть логическими")
        if isinstance(self.grid_alpha, bool) or not isinstance(self.grid_alpha, (int, float)):
            raise ValueError("grid_alpha должен быть числом")
        if not isfinite(self.grid_alpha) or not 0.0 <= self.grid_alpha <= 1.0:
            raise ValueError("grid_alpha должен быть от 0 до 1")
        _require_text(self.x_axis_label, "x_axis_label", max_length=100, allow_empty=True)
        _ensure_unique([item.binding_id for item in self.bindings], "binding_id")

    @classmethod
    def create(
        cls,
        title: str,
        kind: TrackKind,
        *,
        bindings: list[ParameterBinding] | None = None,
        visible: bool = True,
        locked: bool = False,
        grid_x: bool = True,
        grid_y: bool = True,
        grid_alpha: float = 0.2,
        x_axis_label: str = "",
    ) -> FormTrack:
        return cls(
            track_id=str(uuid4()),
            title=title,
            kind=kind,
            bindings=list(bindings or []),
            visible=visible,
            locked=locked,
            grid_x=grid_x,
            grid_y=grid_y,
            grid_alpha=grid_alpha,
            x_axis_label=x_axis_label,
        )

    def add_binding(self, binding: ParameterBinding, index: int | None = None) -> None:
        if any(item.binding_id == binding.binding_id for item in self.bindings):
            raise ValueError(f"Привязка уже существует: {binding.binding_id}")
        if index is None:
            self.bindings.append(binding)
        else:
            self.bindings.insert(max(0, min(index, len(self.bindings))), binding)

    def remove_binding(self, binding_id: str) -> ParameterBinding:
        for index, binding in enumerate(self.bindings):
            if binding.binding_id == binding_id:
                return self.bindings.pop(index)
        raise KeyError(binding_id)


@dataclass(slots=True)
class FormColumn:
    column_id: str
    title: str
    width: int = 260
    visible: bool = True
    locked: bool = False
    tracks: list[FormTrack] = field(default_factory=list)
    group_title: str = ""

    def __post_init__(self) -> None:
        _require_id(self.column_id, "column_id")
        _require_text(self.title, "title", max_length=120)
        _require_text(self.group_title, "group_title", max_length=120, allow_empty=True)
        if isinstance(self.width, bool) or not isinstance(self.width, int):
            raise ValueError("width должен быть целым числом")
        if not 80 <= self.width <= 2000:
            raise ValueError("Ширина колонки должна быть от 80 до 2000 px")
        if not isinstance(self.visible, bool) or not isinstance(self.locked, bool):
            raise ValueError("visible и locked должны быть логическими")
        _ensure_unique([track.track_id for track in self.tracks], "track_id")

    @classmethod
    def create(
        cls,
        title: str,
        *,
        group_title: str = "",
        width: int = 260,
        visible: bool = True,
        locked: bool = False,
        tracks: list[FormTrack] | None = None,
    ) -> FormColumn:
        return cls(
            column_id=str(uuid4()),
            title=title,
            group_title=group_title,
            width=width,
            visible=visible,
            locked=locked,
            tracks=list(tracks or []),
        )

    def add_track(self, track: FormTrack, index: int | None = None) -> None:
        if any(item.track_id == track.track_id for item in self.tracks):
            raise ValueError(f"Дорожка уже существует: {track.track_id}")
        if index is None:
            self.tracks.append(track)
        else:
            self.tracks.insert(max(0, min(index, len(self.tracks))), track)

    def remove_track(self, track_id: str) -> FormTrack:
        for index, track in enumerate(self.tracks):
            if track.track_id == track_id:
                return self.tracks.pop(index)
        raise KeyError(track_id)


@dataclass(slots=True)
class FormDocument:
    form_id: str
    name: str
    axis_kind: FormAxisKind
    columns: list[FormColumn] = field(default_factory=list)
    description: str = ""
    origin: FormTemplateOrigin = FormTemplateOrigin.USER
    read_only: bool = False
    style_id: str = "default-screen"
    print_header_template_id: str | None = None

    def __post_init__(self) -> None:
        _require_id(self.form_id, "form_id")
        _require_text(self.name, "name", max_length=160)
        _require_text(self.description, "description", max_length=2000, allow_empty=True)
        _require_id(self.style_id, "style_id")
        if self.print_header_template_id is not None:
            _require_id(self.print_header_template_id, "print_header_template_id")
        if not isinstance(self.axis_kind, FormAxisKind):
            raise ValueError("axis_kind должен использовать FormAxisKind")
        if not isinstance(self.origin, FormTemplateOrigin):
            raise ValueError("origin должен использовать FormTemplateOrigin")
        if self.origin is FormTemplateOrigin.FACTORY and not self.read_only:
            raise ValueError("Заводская форма должна быть read_only")
        _ensure_unique([column.column_id for column in self.columns], "column_id")
        self.validate()

    @classmethod
    def create(
        cls,
        name: str,
        axis_kind: FormAxisKind,
        *,
        description: str = "",
    ) -> FormDocument:
        return cls(
            form_id=str(uuid4()),
            name=name,
            axis_kind=axis_kind,
            description=description,
        )

    def validate(self) -> None:
        track_ids: list[str] = []
        binding_ids: list[str] = []
        for column in self.columns:
            track_ids.extend(track.track_id for track in column.tracks)
            for track in column.tracks:
                binding_ids.extend(binding.binding_id for binding in track.bindings)
        _ensure_unique(track_ids, "track_id")
        _ensure_unique(binding_ids, "binding_id")
        axis_kinds = {
            track.kind
            for column in self.columns
            for track in column.tracks
            if track.kind is TrackKind.DEPTH
        }
        if len(axis_kinds) > 1:
            raise ValueError("Форма содержит несколько несовместимых вертикальных осей")

    def add_column(self, column: FormColumn, index: int | None = None) -> None:
        if self.read_only:
            raise PermissionError("Заводскую форму нельзя изменять")
        if any(item.column_id == column.column_id for item in self.columns):
            raise ValueError(f"Колонка уже существует: {column.column_id}")
        if index is None:
            self.columns.append(column)
        else:
            self.columns.insert(max(0, min(index, len(self.columns))), column)
        self.validate()

    def remove_column(self, column_id: str) -> FormColumn:
        if self.read_only:
            raise PermissionError("Заводскую форму нельзя изменять")
        for index, column in enumerate(self.columns):
            if column.column_id == column_id:
                return self.columns.pop(index)
        raise KeyError(column_id)

    def move_column(self, column_id: str, target_index: int) -> None:
        if self.read_only:
            raise PermissionError("Заводскую форму нельзя изменять")
        column = self.remove_column(column_id)
        self.columns.insert(max(0, min(target_index, len(self.columns))), column)

    def editable_copy(self, *, name: str | None = None) -> FormDocument:
        from copy import deepcopy

        clone = deepcopy(self)
        clone.form_id = str(uuid4())
        clone.name = name or f"{self.name} — копия"
        clone.origin = FormTemplateOrigin.USER
        clone.read_only = False
        return clone


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} должен быть непустой строкой")
    if len(value) > 160 or not re.fullmatch(r"[\w.:-]+", value, flags=re.UNICODE):
        raise ValueError(f"{name} содержит недопустимые символы")


def _require_text(value: str, name: str, *, max_length: int, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} должен быть строкой")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} должен быть непустой строкой")
    if len(value) > max_length:
        raise ValueError(f"{name} не должен превышать {max_length} символов")


def _ensure_unique(values: list[str], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"Обнаружены повторяющиеся {name}")


def _validate_range(scale: XScale, minimum: float | None, maximum: float | None) -> None:
    if (minimum is None) != (maximum is None):
        raise ValueError("Минимум и максимум должны задаваться вместе")
    if minimum is None or maximum is None:
        return
    if not isfinite(minimum) or not isfinite(maximum) or minimum >= maximum:
        raise ValueError("Некорректный диапазон параметра")
    if scale is XScale.LOGARITHMIC and minimum <= 0:
        raise ValueError("Логарифмический диапазон должен быть положительным")
