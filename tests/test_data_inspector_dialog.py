import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QPlainTextEdit, QTableWidget

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.project.data_inspector_controller import DataInspectorController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
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
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", "Methane", dataset.dataset_id),
        np.array([1.0, 2.0]),
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
    depth_summary = dialog.findChild(QPlainTextEdit, "depth-header-summary")
    source_profile = dialog.findChild(QPlainTextEdit, "las-source-profile")
    assert indexes is not None and indexes.rowCount() == 2
    assert curves is not None and curves.rowCount() == 1
    assert issues is not None and issues.rowCount() == 0
    assert headers is not None and headers.rowCount() == 2
    assert headers.item(1, 2).text() == "редактор"
    assert depth_summary is not None and "STRT=1" in depth_summary.toPlainText()
    assert source_profile is not None
    assert "нет сохранённого отчёта" in source_profile.toPlainText()

    curves.selectRow(0)
    dialog.curve_mnemonic.setText("CH4")
    dialog.curve_unit.setText("ppm")
    dialog.curve_description.setText("Methane ppm")
    dialog._update_curve_metadata()
    assert controller.session.current_dataset.curves["c1"].metadata.original_mnemonic == "CH4"  # type: ignore[union-attr]

    indexes.selectRow(1)
    dialog._activate_selected_index()

    assert controller.session.current_dataset.active_index_id == "time"  # type: ignore[union-attr]
    assert indexes.item(1, 0).text() == "●"
    dialog.close()


def test_data_inspector_dialog_uses_selected_language(qapp) -> None:
    dialog = DataInspectorDialog(make_controller(), language=AppLanguage.EN)
    buttons = dialog.findChild(QDialogButtonBox)

    assert buttons is not None
    assert dialog.windowTitle() == "Data and index information"
    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "Summary", "Indexes", "Curves", "Import diagnostics", "LAS source", "LAS header"
    ]
    assert dialog.index_table.horizontalHeaderItem(0).text() == "Active"
    assert dialog.curve_table.horizontalHeaderItem(2).text() == "Description"
    assert "The dataset has no saved LAS import report" in dialog.source_text.toPlainText()
    assert dialog.header_table.item(1, 2).text() == "editor"
    assert "Direction: ascending" in dialog.depth_header_summary.toPlainText()
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()
