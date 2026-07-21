from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.templates import factory_templates
from geoworkbench.tablet.models import TrackKind
from geoworkbench.ui.form_structure_editor_dialog import FormStructureEditorDialog


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
