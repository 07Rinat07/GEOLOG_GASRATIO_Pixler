from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QPushButton

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
