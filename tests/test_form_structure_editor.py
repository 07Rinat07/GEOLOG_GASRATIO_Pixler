from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QHeaderView

from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.templates import factory_templates
from geoworkbench.tablet.models import TrackKind
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerTrackSettings,
)
from geoworkbench.ui.form_structure_editor_dialog import (
    FormStructureEditorDialog,
    _FormPreview,
)


def test_structure_editor_column_and_track_crud() -> None:
    form = FormDocument.create("Test", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)

    first = editor.add_column("Gas", width=300)
    second = editor.add_column("Drilling", width=240)
    track = editor.add_track(first.column_id, title="Total gas", kind=TrackKind.CURVE)

    editor.rename_column(first.column_id, "Gas curves")
    editor.set_column_width(first.column_id, 420)
    editor.rename_track(track.track_id, "TG")
    editor.set_column_title_presentation(
        first.column_id, orientation="vertical_top_to_bottom", position="top"
    )
    editor.set_track_title_presentation(
        track.track_id, orientation="vertical_bottom_to_top", position="bottom"
    )
    editor.move_track(track.track_id, second.column_id, 0)
    editor.move_column(second.column_id, 0)

    assert form.columns[0].column_id == second.column_id
    assert form.columns[1].title == "Gas curves"
    assert form.columns[1].width == 420
    assert form.columns[0].tracks[0].title == "TG"
    assert form.columns[1].title_orientation == "vertical_top_to_bottom"
    assert form.columns[1].title_position == "top"
    assert form.columns[0].tracks[0].title_orientation == "vertical_bottom_to_top"
    assert form.columns[0].tracks[0].title_position == "bottom"
    assert editor.dirty is True


def test_structure_editor_rejects_factory_form() -> None:
    factory = next(iter(factory_templates().values()))
    with pytest.raises(PermissionError):
        FormStructureEditor(factory)


def test_structure_editor_validates_width() -> None:
    form = FormDocument.create("Test", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)
    column = editor.add_column("Gas")
    with pytest.raises(ValueError):
        editor.set_column_width(column.column_id, 10)


def test_structure_editor_manages_visibility_and_track_grid() -> None:
    form = FormDocument.create("Test", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)
    column = editor.add_column("Gas")
    track = editor.add_track(column.column_id, title="Total gas")
    editor.dirty = False

    editor.set_column_visible(column.column_id, False)
    editor.set_track_visible(track.track_id, False)
    editor.set_track_grid(
        track.track_id,
        grid_x=False,
        grid_y=True,
        grid_major_divisions=4,
        grid_minor_divisions=10,
        grid_alpha=0.35,
        grid_print=False,
    )

    assert column.visible is False
    assert track.visible is False
    assert (
        track.grid_x,
        track.grid_y,
        track.grid_major_divisions,
        track.grid_minor_divisions,
        track.grid_alpha,
        track.grid_print,
    ) == (False, True, 4, 10, 0.35, False)
    assert editor.dirty is True

    with pytest.raises(ValueError):
        editor.set_track_grid(
            track.track_id,
            grid_x=True,
            grid_y=True,
            grid_major_divisions=0,
            grid_minor_divisions=5,
            grid_alpha=0.2,
            grid_print=True,
        )
    assert track.grid_major_divisions == 4


def test_structure_editor_manages_per_track_inner_ruler() -> None:
    form = FormDocument.create("Test", FormAxisKind.TIME)
    editor = FormStructureEditor(form)
    column = editor.add_column("Gas")
    track = editor.add_track(column.column_id, title="Gas", kind=TrackKind.GAS)
    settings = VerticalRulerTrackSettings(
        mode=VerticalRulerMode.OFF,
        label_every_major=2,
        major_tick_every=3,
        minor_tick_every=4,
    )

    editor.set_track_vertical_ruler(track.track_id, settings)

    assert track.vertical_ruler == settings
    column.locked = True
    with pytest.raises(PermissionError):
        editor.set_track_vertical_ruler(
            track.track_id,
            VerticalRulerTrackSettings(mode=VerticalRulerMode.TICKS_ONLY),
        )


def test_structure_editor_manages_lba_colour_and_bitumen_label_direction() -> None:
    form = FormDocument.create("Test", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)
    column = editor.add_column("LBA", width=180)
    track = editor.add_track(column.column_id, title="LBA", kind=TrackKind.LBA)

    editor.set_track_lba_label_orientation(track.track_id, "horizontal")

    assert track.lba_label_orientation == "horizontal"
    with pytest.raises(ValueError, match="только для ЛБА"):
        curve = editor.add_track(column.column_id, title="Curve", kind=TrackKind.CURVE)
        editor.set_track_lba_label_orientation(
            curve.track_id, "vertical_top_to_bottom"
        )


def test_structure_editor_rejects_visibility_and_grid_edits_on_locked_column() -> None:
    form = FormDocument.create("Test", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)
    column = editor.add_column("Gas")
    track = editor.add_track(column.column_id, title="Total gas")
    column.locked = True

    with pytest.raises(PermissionError):
        editor.set_column_visible(column.column_id, False)
    with pytest.raises(PermissionError):
        editor.set_track_visible(track.track_id, False)
    with pytest.raises(PermissionError):
        editor.set_track_grid(
            track.track_id,
            grid_x=True,
            grid_y=True,
            grid_major_divisions=5,
            grid_minor_divisions=5,
            grid_alpha=0.2,
            grid_print=True,
        )


def test_form_preview_skips_hidden_tracks_and_draws_grid_for_visible_tracks(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    form = FormDocument.create("Test", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)
    column = editor.add_column("Gas")
    visible = editor.add_track(column.column_id, title="Visible")
    hidden = editor.add_track(column.column_id, title="Hidden")
    hidden.visible = False
    drawn_track_ids: list[str] = []
    monkeypatch.setattr(
        _FormPreview,
        "_draw_track_grid",
        staticmethod(lambda _painter, _rect, track: drawn_track_ids.append(track.track_id)),
    )
    preview = _FormPreview()
    preview.resize(480, 220)
    preview.set_form(form)
    image = QImage(480, 220, QImage.Format.Format_ARGB32)

    preview.render(image)

    assert drawn_track_ids == [visible.track_id]
    assert hidden.track_id not in drawn_track_ids
    preview.close()


def test_structure_editor_dialog_saves_user_form(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    repository = FormRepository(tmp_path / "forms")
    form = FormDocument.create("Editable", FormAxisKind.DEPTH)
    dialog = FormStructureEditorDialog(form, repository, language="en")

    dialog._add_column()
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
    dialog.title_edit.setText("Gas")
    dialog._apply_title()
    dialog.width_spin.setValue(360)
    dialog._apply_width(360)
    dialog.title_orientation_combo.setCurrentIndex(
        dialog.title_orientation_combo.findData("vertical_bottom_to_top")
    )
    dialog.title_position_combo.setCurrentIndex(
        dialog.title_position_combo.findData("bottom")
    )
    dialog._add_track()
    dialog._save()

    loaded = repository.load(form.form_id)
    assert loaded.columns[0].title == "Gas"
    assert loaded.columns[0].width == 360
    assert loaded.columns[0].title_orientation == "vertical_bottom_to_top"
    assert loaded.columns[0].title_position == "bottom"
    assert len(loaded.columns[0].tracks) == 1
    assert dialog.saved_form is not None


def test_structure_editor_dialog_exposes_visibility_grid_and_tree_status(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    repository = FormRepository(tmp_path / "forms")
    form = FormDocument.create("Editable", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)
    column = editor.add_column("Gas")
    track = editor.add_track(column.column_id, title="Total gas curve parameters")
    column.visible = False
    track.visible = False
    track.grid_x = False
    track.grid_y = False
    dialog = FormStructureEditorDialog(form, repository, language="en")

    column_item = dialog.tree.topLevelItem(0)
    track_item = column_item.child(0)
    assert "hidden" in column_item.text(3)
    assert "hidden" in track_item.text(3)
    assert "grid off" in track_item.text(3)
    header = dialog.tree.header()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert all(
        header.sectionResizeMode(index) == QHeaderView.ResizeMode.ResizeToContents
        for index in (1, 2)
    )
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.Interactive
    dialog.resize(1200, 800)
    dialog.show()
    qapp.processEvents()
    title_width = dialog.tree.fontMetrics().horizontalAdvance(track_item.text(0))
    assert dialog.tree.columnWidth(0) >= title_width + 30

    dialog.tree.setCurrentItem(track_item)
    qapp.processEvents()
    assert dialog.grid_group.isHidden() is False
    assert dialog.visible_check.text() == "Show track"
    assert dialog.visible_check.isChecked() is False

    dialog.visible_check.setChecked(True)
    qapp.processEvents()
    _column, edited_track = dialog.editor.track(track.track_id)
    assert edited_track.visible is True

    dialog.grid_editor.standard_button.click()
    qapp.processEvents()
    assert (
        edited_track.grid_x,
        edited_track.grid_y,
        edited_track.grid_major_divisions,
        edited_track.grid_minor_divisions,
        edited_track.grid_alpha,
        edited_track.grid_print,
    ) == (True, True, 5, 5, 0.2, True)
    dialog.close()


def test_structure_editor_dialog_edits_inner_ruler_of_selected_graph_track(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    repository = FormRepository(tmp_path / "forms")
    form = FormDocument.create("Editable", FormAxisKind.TIME)
    editor = FormStructureEditor(form)
    column = editor.add_column("Gas")
    track = editor.add_track(column.column_id, title="Gas", kind=TrackKind.GAS)
    dialog = FormStructureEditorDialog(form, repository, language="en")
    track_item = dialog.tree.topLevelItem(0).child(0)

    dialog.tree.setCurrentItem(track_item)
    qapp.processEvents()

    assert dialog.vertical_ruler_group.isHidden() is False
    off_index = dialog.vertical_ruler_mode_input.findData(VerticalRulerMode.OFF.value)
    dialog.vertical_ruler_mode_input.setCurrentIndex(off_index)
    qapp.processEvents()

    _column, edited = dialog.editor.track(track.track_id)
    assert edited.vertical_ruler.mode is VerticalRulerMode.OFF
    assert "inner ruler off" in track_item.text(3)
    assert not dialog.vertical_ruler_label_every_input.isEnabled()
    assert not dialog.vertical_ruler_major_tick_every_input.isEnabled()
    assert not dialog.vertical_ruler_minor_tick_every_input.isEnabled()
    dialog.close()


def test_structure_editor_dialog_edits_lba_label_direction(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    repository = FormRepository(tmp_path / "forms")
    form = FormDocument.create("Editable", FormAxisKind.DEPTH)
    editor = FormStructureEditor(form)
    column = editor.add_column("LBA", width=180)
    track = editor.add_track(column.column_id, title="LBA", kind=TrackKind.LBA)
    dialog = FormStructureEditorDialog(form, repository, language="en")
    track_item = dialog.tree.topLevelItem(0).child(0)

    dialog.tree.setCurrentItem(track_item)
    qapp.processEvents()

    assert dialog.lba_label_orientation_combo.isHidden() is False
    assert (
        dialog.lba_label_orientation_combo.currentData()
        == "vertical_top_to_bottom"
    )
    dialog.lba_label_orientation_combo.setCurrentIndex(
        dialog.lba_label_orientation_combo.findData("vertical_bottom_to_top")
    )
    qapp.processEvents()

    _column, edited = dialog.editor.track(track.track_id)
    assert edited.lba_label_orientation == "vertical_bottom_to_top"
    dialog.close()
