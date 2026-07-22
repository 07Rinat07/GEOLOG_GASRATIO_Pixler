import numpy as np
import pytest
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QTableWidget

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.depth_annotations_dialog import DepthAnnotationsDialog


def make_controller() -> DepthAnnotationController:
    dataset = Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    session = ProjectSession()
    session.add_dataset(dataset)
    return DepthAnnotationController(session)


def test_depth_annotations_dialog_adds_and_lists_annotation(qapp) -> None:
    controller = make_controller()
    dialog = DepthAnnotationsDialog(controller)
    dialog.depth_input.setValue(150.0)
    dialog.text_input.setText("Маркер")

    dialog._add()

    table = dialog.findChild(QTableWidget, "depth-annotations-table")
    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "Маркер"
    assert dialog.undo_button.isEnabled() is True

    dialog._undo()
    assert table.rowCount() == 0
    assert dialog.redo_button.isEnabled() is True

    dialog._redo()
    assert table.rowCount() == 1
    dialog.close()


def test_depth_annotations_dialog_uses_selected_language(qapp) -> None:
    dialog = DepthAnnotationsDialog(make_controller(), language=AppLanguage.EN)
    table = dialog.findChild(QTableWidget, "depth-annotations-table")
    buttons = dialog.findChild(QDialogButtonBox)

    assert table is not None
    assert buttons is not None
    assert dialog.windowTitle() == "Depth annotations"
    assert table.horizontalHeaderItem(0).text() == "Depth"
    assert table.horizontalHeaderItem(1).text() == "Comment"
    assert dialog.findChild(QPushButton, "annotation-add-button").text() == "Add"
    assert dialog.findChild(QPushButton, "annotation-update-button").text() == "Update"
    assert dialog.findChild(QPushButton, "annotation-remove-button").text() == "Remove"
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()


def test_time_annotation_axis_uses_seconds_for_datetime_index(qapp) -> None:
    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    values = np.array(["2026-07-22T00:00:00", "2026-07-22T00:00:10"], dtype="datetime64[ns]")
    dataset.add_index(
        DatasetIndex(
            "clock",
            "DATE_TIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            "UTC",
            values,
        ),
        make_active=True,
    )

    dialog = DepthAnnotationsDialog(controller)

    assert dialog.axis_id_input.currentData() == "clock"
    expected = values.astype(np.int64).astype(np.float64) / 1_000_000_000.0
    assert dialog.axis_input.minimum() == pytest.approx(float(expected[0]))
    assert dialog.axis_input.maximum() == pytest.approx(float(expected[1]))
    dialog.close()
