from __future__ import annotations

import inspect

import numpy as np
from PySide6.QtWidgets import QLabel, QPushButton

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.ui.las_editor_dialog import LasEditorDialog, LasEditorOperation


def test_las_editor_disables_dataset_operations_without_dataset(qapp) -> None:
    dialog = LasEditorDialog(None)
    buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}

    assert buttons["Создать новый LAS"].isEnabled()
    assert buttons["Открыть LAS"].isEnabled()
    assert not buttons["Редактировать таблицу"].isEnabled()
    assert not buttons["Вставить данные из LAS"].isEnabled()
    assert dialog.operation is None


def test_las_editor_uses_shared_palette_aware_presentation(qapp) -> None:
    dialog = LasEditorDialog(None)
    try:
        assert dialog.objectName() == "las-editor-dialog"

        title = dialog.findChild(QLabel, "las-editor-title")
        summary = dialog.findChild(QLabel, "las-editor-summary")
        note = dialog.findChild(QLabel, "las-editor-safety-note")

        assert title is not None
        assert summary is not None
        assert note is not None
        assert "Рабочий LAS не выбран" in summary.text()
        assert title.styleSheet() == ""
        assert summary.styleSheet() == ""
        assert note.styleSheet() == ""
    finally:
        dialog.close()


def test_las_editor_records_selected_operation(qapp) -> None:
    dataset = Dataset(
        "data",
        "Well",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([100.0, 100.5, 101.0]),
    )
    dialog = LasEditorDialog(dataset)
    dialog._choose(LasEditorOperation.INSERT_CURVES)

    assert dialog.operation is LasEditorOperation.INSERT_CURVES
    assert dialog.result() == dialog.DialogCode.Accepted


def test_las_editor_source_has_no_local_presentation_qss() -> None:
    source = inspect.getsource(LasEditorDialog)

    assert ".setStyleSheet(" not in source
    assert "#475569" not in source
    assert 'setObjectName("las-editor-title")' in source
    assert 'setObjectName("las-editor-summary")' in source
    assert 'setObjectName("las-editor-safety-note")' in source
