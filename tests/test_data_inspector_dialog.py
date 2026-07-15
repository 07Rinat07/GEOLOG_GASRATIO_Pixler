import numpy as np
from PySide6.QtWidgets import QTableWidget

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.project.data_inspector_controller import DataInspectorController
from geoworkbench.project.session import ProjectSession
from geoworkbench.ui.data_inspector_dialog import DataInspectorDialog


def make_controller() -> DataInspectorController:
    session = ProjectSession()
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0, 2.0]),
        headers={"WELL": "Test Well", "STRT": "1"},
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 1.0]),
        )
    )
    session.add_dataset(dataset)
    session.dirty = False
    return DataInspectorController(session)


def test_data_inspector_dialog_renders_and_activates_index(qapp) -> None:
    controller = make_controller()
    dialog = DataInspectorDialog(controller)

    indexes = dialog.findChild(QTableWidget, "data-indexes")
    curves = dialog.findChild(QTableWidget, "data-curves")
    issues = dialog.findChild(QTableWidget, "import-issues")
    headers = dialog.findChild(QTableWidget, "las-header")
    assert indexes is not None and indexes.rowCount() == 2
    assert curves is not None and curves.rowCount() == 0
    assert issues is not None and issues.rowCount() == 0
    assert headers is not None and headers.rowCount() == 2
    assert headers.item(1, 2).text() == "редактор"

    indexes.selectRow(1)
    dialog._activate_selected_index()

    assert controller.session.current_dataset.active_index_id == "time"  # type: ignore[union-attr]
    assert indexes.item(1, 0).text() == "●"
    dialog.close()
