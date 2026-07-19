from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from geoworkbench.forms.draft import DraftFormController
from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.preview import FormPreviewController
from geoworkbench.forms.repository import FormRepository
from geoworkbench.ui.form_structure_editor_dialog import FormStructureEditorDialog


def test_draft_controller_tracks_save_and_revert() -> None:
    original = FormDocument.create("Original", FormAxisKind.DEPTH)
    controller = DraftFormController.create(original)

    controller.form.name = "Changed"
    controller.changed()
    assert controller.dirty is True

    restored = controller.revert()
    assert restored.name == "Original"
    assert controller.dirty is False

    controller.form.name = "Saved"
    controller.mark_saved()
    assert controller.dirty is False
    assert controller.saved_copy().name == "Saved"


def test_preview_controller_supports_manual_and_auto_apply() -> None:
    form = FormDocument.create("Form", FormAxisKind.DEPTH)
    applied: list[str] = []
    controller = FormPreviewController(lambda item: applied.append(item.name), auto_apply=False)

    controller.changed(form)
    assert controller.pending is True
    assert applied == []

    controller.apply(form)
    assert applied == ["Form"]
    assert controller.pending is False

    controller.auto_apply = True
    form.name = "Live"
    controller.changed(form)
    assert applied[-1] == "Live"


def test_structure_editor_live_preview_save_and_revert(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    repository = FormRepository(tmp_path / "forms")
    form = FormDocument.create("Editable", FormAxisKind.DEPTH)
    previews: list[FormDocument] = []
    dialog = FormStructureEditorDialog(
        form,
        repository,
        language="en",
        preview_callback=lambda item: previews.append(item),
    )

    dialog._add_column()
    assert dialog.draft.dirty is True
    assert previews

    dialog._save()
    assert dialog.draft.dirty is False
    assert dialog.saved_form is not None
    assert repository.load(form.form_id).columns

    dialog._add_column()
    assert len(dialog.editor.form.columns) == 2
    dialog._revert()
    assert len(dialog.editor.form.columns) == 1
    assert dialog.draft.dirty is False
