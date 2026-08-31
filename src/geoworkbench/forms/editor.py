from __future__ import annotations

from dataclasses import dataclass, replace

from geoworkbench.forms.models import FormColumn, FormDocument, FormTrack
from geoworkbench.tablet.models import (
    MAX_TRACK_WIDTH,
    TrackKind,
    minimum_width_for_track_kinds,
)
from geoworkbench.tablet.vertical_ruler import VerticalRulerTrackSettings


@dataclass(slots=True)
class FormStructureEditor:
    """Mutable editing facade for one user form.

    The class deliberately contains no Qt dependencies so structural edits can be
    validated and tested independently from the visual editor dialog.
    """

    form: FormDocument
    dirty: bool = False

    def __post_init__(self) -> None:
        if self.form.read_only:
            raise PermissionError("Заводскую форму нужно сначала скопировать")

    def rename_form(self, name: str) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Название формы не должно быть пустым")
        if len(normalized) > 160:
            raise ValueError("Название формы не должно превышать 160 символов")
        self.form.name = normalized
        self.form.__post_init__()
        self.dirty = True

    def column(self, column_id: str) -> FormColumn:
        for column in self.form.columns:
            if column.column_id == column_id:
                return column
        raise KeyError(column_id)

    def track(self, track_id: str) -> tuple[FormColumn, FormTrack]:
        for column in self.form.columns:
            for track in column.tracks:
                if track.track_id == track_id:
                    return column, track
        raise KeyError(track_id)

    def add_column(
        self,
        title: str = "Новая колонка",
        *,
        width: int = 260,
        index: int | None = None,
    ) -> FormColumn:
        column = FormColumn.create(title, width=width)
        self.form.add_column(column, index)
        self.dirty = True
        return column

    def remove_column(self, column_id: str) -> FormColumn:
        column = self.form.remove_column(column_id)
        self.dirty = True
        return column

    def move_column(self, column_id: str, target_index: int) -> None:
        self.form.move_column(column_id, target_index)
        self.form.validate()
        self.dirty = True

    def rename_column(self, column_id: str, title: str) -> None:
        column = self.column(column_id)
        title = title.strip()
        if not title:
            raise ValueError("Название колонки не должно быть пустым")
        column.title = title
        column.__post_init__()
        self.form.validate()
        self.dirty = True

    def set_column_visible(self, column_id: str, visible: bool) -> None:
        column = self.column(column_id)
        if column.locked:
            raise PermissionError("Колонка заблокирована")
        if not isinstance(visible, bool):
            raise ValueError("visible должен быть логическим")
        validated = replace(column, visible=visible)
        column.visible = validated.visible
        self.form.validate()
        self.dirty = True


    def set_column_title_presentation(
        self, column_id: str, *, orientation: str, position: str
    ) -> None:
        column = self.column(column_id)
        column.title_orientation = orientation
        column.title_position = position
        column.__post_init__()
        self.form.validate()
        self.dirty = True

    def set_column_group(self, column_id: str, group_title: str) -> None:
        """Rename the complete contiguous merged section containing ``column_id``.

        The top row is rendered as one merged caption for adjacent columns with the
        same ``group_title``. Updating only one column would split that visual group,
        therefore the whole contiguous run is renamed atomically.
        """

        selected_index = next(
            (index for index, item in enumerate(self.form.columns) if item.column_id == column_id),
            None,
        )
        if selected_index is None:
            raise KeyError(column_id)
        normalized = group_title.strip()
        if len(normalized) > 120:
            raise ValueError("Название раздела не должно превышать 120 символов")
        original = self.form.columns[selected_index].group_title
        left = selected_index
        while left > 0 and self.form.columns[left - 1].group_title == original:
            left -= 1
        right = selected_index
        while right + 1 < len(self.form.columns) and self.form.columns[right + 1].group_title == original:
            right += 1
        for column in self.form.columns[left : right + 1]:
            column.group_title = normalized
            column.__post_init__()
        self.form.validate()
        self.dirty = True

    def set_column_width(self, column_id: str, width: int) -> None:
        column = self.column(column_id)
        minimum = minimum_width_for_track_kinds(track.kind for track in column.tracks)
        if not minimum <= width <= MAX_TRACK_WIDTH:
            raise ValueError(
                f"Ширина колонки должна быть от {minimum} до {MAX_TRACK_WIDTH} px"
            )
        column.width = int(width)
        column.__post_init__()
        self.form.validate()
        self.dirty = True

    def add_track(
        self,
        column_id: str,
        *,
        title: str = "Новая дорожка",
        kind: TrackKind = TrackKind.CURVE,
        index: int | None = None,
    ) -> FormTrack:
        column = self.column(column_id)
        if column.locked:
            raise PermissionError("Колонка заблокирована")
        track = FormTrack.create(title, kind)
        column.add_track(track, index)
        self.form.validate()
        self.dirty = True
        return track

    def remove_track(self, track_id: str) -> FormTrack:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        removed = column.remove_track(track_id)
        self.form.validate()
        self.dirty = True
        return removed

    def move_track(self, track_id: str, target_column_id: str, target_index: int) -> None:
        source_column, track = self.track(track_id)
        target_column = self.column(target_column_id)
        if track.locked or source_column.locked or target_column.locked:
            raise PermissionError("Дорожка или колонка заблокирована")
        source_column.remove_track(track_id)
        target_column.add_track(track, target_index)
        self.form.validate()
        self.dirty = True

    def rename_track(self, track_id: str, title: str) -> None:
        _column, track = self.track(track_id)
        if track.locked:
            raise PermissionError("Дорожка заблокирована")
        title = title.strip()
        if not title:
            raise ValueError("Название дорожки не должно быть пустым")
        track.title = title
        track.__post_init__()
        self.form.validate()
        self.dirty = True

    def set_track_visible(self, track_id: str, visible: bool) -> None:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        if not isinstance(visible, bool):
            raise ValueError("visible должен быть логическим")
        validated = replace(track, visible=visible)
        track.visible = validated.visible
        self.form.validate()
        self.dirty = True

    def set_track_grid(
        self,
        track_id: str,
        *,
        grid_x: bool,
        grid_y: bool,
        grid_major_divisions: int,
        grid_minor_divisions: int,
        grid_alpha: float,
        grid_print: bool,
    ) -> None:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        validated = replace(
            track,
            grid_x=grid_x,
            grid_y=grid_y,
            grid_major_divisions=grid_major_divisions,
            grid_minor_divisions=grid_minor_divisions,
            grid_alpha=grid_alpha,
            grid_print=grid_print,
        )
        track.grid_x = validated.grid_x
        track.grid_y = validated.grid_y
        track.grid_major_divisions = validated.grid_major_divisions
        track.grid_minor_divisions = validated.grid_minor_divisions
        track.grid_alpha = validated.grid_alpha
        track.grid_print = validated.grid_print
        self.form.validate()
        self.dirty = True

    def set_track_vertical_ruler(
        self,
        track_id: str,
        settings: VerticalRulerTrackSettings,
    ) -> None:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        validated = replace(track, vertical_ruler=settings)
        track.vertical_ruler = validated.vertical_ruler
        self.form.validate()
        self.dirty = True


    def set_track_title_presentation(
        self, track_id: str, *, orientation: str, position: str
    ) -> None:
        _column, track = self.track(track_id)
        if track.locked:
            raise PermissionError("Дорожка заблокирована")
        track.title_orientation = orientation
        track.title_position = position
        track.__post_init__()
        self.form.validate()
        self.dirty = True

    def set_track_interval_labels(self, track_id: str, enabled: bool) -> None:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        if track.kind not in {TrackKind.LITHOLOGY, TrackKind.CUTTINGS}:
            enabled = False
        track.show_interval_labels = bool(enabled)
        track.__post_init__()
        self.form.validate()
        self.dirty = True

    def set_track_lba_label_orientation(
        self, track_id: str, orientation: str
    ) -> None:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        if track.kind is not TrackKind.LBA:
            raise ValueError("Направление подписей «Цвет / Битум» доступно только для ЛБА")
        validated = replace(track, lba_label_orientation=orientation)
        track.lba_label_orientation = validated.lba_label_orientation
        self.form.validate()
        self.dirty = True

    def set_track_calcimetry_label_orientation(
        self, track_id: str, orientation: str
    ) -> None:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        if track.kind is not TrackKind.CALCIMETRY:
            raise ValueError("Направление подписей доступно только для кальциметрии")
        validated = replace(track, calcimetry_label_orientation=orientation)
        track.calcimetry_label_orientation = validated.calcimetry_label_orientation
        self.form.validate()
        self.dirty = True

    def set_track_description_borders(self, track_id: str, enabled: bool) -> None:
        column, track = self.track(track_id)
        if track.locked or column.locked:
            raise PermissionError("Дорожка заблокирована")
        if track.kind not in {TrackKind.TEXT, TrackKind.INTERPRETATION}:
            raise ValueError("Границы интервалов доступны только для описаний пород")
        track.show_description_borders = bool(enabled)
        track.__post_init__()
        self.form.validate()
        self.dirty = True

    def binding(self, track_id: str, binding_id: str):
        _column, track = self.track(track_id)
        for binding in track.bindings:
            if binding.binding_id == binding_id:
                return binding
        raise KeyError(binding_id)

    def rename_binding(self, track_id: str, binding_id: str, display_name: str) -> None:
        from dataclasses import replace

        column, track = self.track(track_id)
        if column.locked or track.locked:
            raise PermissionError("Дорожка заблокирована")
        normalized = display_name.strip()
        if not normalized:
            raise ValueError("Название параметра не должно быть пустым")
        if len(normalized) > 120:
            raise ValueError("Название параметра не должно превышать 120 символов")
        for index, binding in enumerate(track.bindings):
            if binding.binding_id == binding_id:
                track.bindings[index] = replace(binding, display_name=normalized)
                track.__post_init__()
                self.form.validate()
                self.dirty = True
                return
        raise KeyError(binding_id)

    def set_track_axis_label(self, track_id: str, label: str) -> None:
        _column, track = self.track(track_id)
        if track.locked:
            raise PermissionError("Дорожка заблокирована")
        normalized = label.strip()
        if len(normalized) > 100:
            raise ValueError("Подпись оси не должна превышать 100 символов")
        track.x_axis_label = normalized
        track.__post_init__()
        self.form.validate()
        self.dirty = True

    def set_track_kind(self, track_id: str, kind: TrackKind) -> None:
        column, track = self.track(track_id)
        if track.locked:
            raise PermissionError("Дорожка заблокирована")
        track.kind = kind
        track.__post_init__()
        minimum = minimum_width_for_track_kinds(item.kind for item in column.tracks)
        if column.width < minimum:
            column.width = minimum
        column.__post_init__()
        self.form.validate()
        self.dirty = True
