import numpy as np
from PySide6.QtWidgets import QTableWidget

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.session import ProjectSession
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
    dialog.close()
