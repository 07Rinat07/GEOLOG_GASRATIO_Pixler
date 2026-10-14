from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from test_report_annotations import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("extension", [".json", ".geologpkg"])
def test_author_batch_print_controls_apply_cancel_history_and_reopen(qapp, tmp_path, language, extension):
    session = _session()
    dialog = InterpretationReportAnnotationDialog(session, language=language)
    depths = session.current_dataset.depth.copy()
    try:
        for text in ("First author note", "Second author note"):
            dialog.annotation.setCurrentIndex(0)
            if text == "Second author note":
                dialog.kind.setCurrentIndex(dialog.kind.findData("symbol"))
                dialog.symbol.setCurrentIndex(dialog.symbol.findData("diamond"))
            dialog.text.setText(text)
            dialog.depth_spin.setValue(1001.0)
            dialog.add_button.click()
        original = dialog.controller.available()
        assert len(original) == 2
        dialog.apply_button.click()
        dialog.print_none_button.click()
        disabled = dialog.controller.available()
        assert disabled == tuple(replace(record, print_enabled=False) for record in original)
        dialog.undo_button.click()
        assert dialog.controller.available() == original
        dialog.redo_button.click()
        assert dialog.controller.available() == disabled
        dialog.apply_button.click()
        dialog.print_all_button.click()
        assert dialog.controller.available() == original
        dialog.reject()
        assert dialog.controller.available() == disabled
        target = tmp_path / ("author-print" + extension)
        ProjectController(session=session).save_project(target)
        reopened = ProjectController().open_project(target)
        restored = InterpretationReportAnnotationDialog(reopened, language=language)
        try:
            assert restored.controller.available() == disabled
            assert not reopened.dirty
            np.testing.assert_array_equal(reopened.current_dataset.depth, depths)
        finally:
            restored.reject()
            restored.close()
    finally:
        dialog.close()


def test_batch_print_rejects_invalid_selection_before_any_mutation(qapp):
    session = _session()
    dialog = InterpretationReportAnnotationDialog(session)
    try:
        dialog.text.setText("Author note")
        dialog.depth_spin.setValue(1001.0)
        dialog.add_button.click()
        records = dialog.controller.available()
        ident = records[0].annotation_id
        session.dirty = False
        for ids in ((ident, "missing"), (ident, ident), ()):
            with pytest.raises((ValueError, KeyError)):
                dialog.controller.set_print_enabled_many(ids, False)
            assert dialog.controller.available() == records
            assert not session.dirty
        assert dialog.controller.set_print_enabled_many((ident,), True) == 0
        assert not session.dirty
    finally:
        dialog.reject()
        dialog.close()
