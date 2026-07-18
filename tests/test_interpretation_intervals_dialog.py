import numpy as np
from PySide6.QtWidgets import QPushButton, QTableWidget

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_intervals_dialog import InterpretationIntervalsDialog


def _controller() -> InterpretationController:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "dataset",
            "Well",
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([100.0, 300.0]),
        )
    )
    controller = InterpretationController(session)
    controller.add_interpretation("Primary")
    session.dirty = False
    return controller


def test_interpretation_dialog_adds_interval_in_english(qapp) -> None:
    controller = _controller()
    dialog = InterpretationIntervalsDialog(controller, language=AppLanguage.EN)
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(150.0)
    dialog.type_input.setCurrentText("Reservoir")
    dialog.label_input.setText("Sand A")
    dialog.color_input.setText("#fde68a")
    dialog.comment_input.setText("Potential pay")

    dialog._add_interval()

    table = dialog.findChild(QTableWidget, "interpretation-intervals-table")
    assert table is not None and table.rowCount() == 1
    assert table.horizontalHeaderItem(3).text() == "Label"
    assert table.item(0, 3).text() == "Sand A"
    add_button = dialog.findChild(QPushButton, "interpretation-interval-add-button")
    assert add_button is not None and add_button.text() == "Add"
    dialog.close()


def test_interpretation_dialog_accepts_external_interval_selection(qapp) -> None:
    controller = _controller()
    interval = controller.add_interval(100.0, 150.0, "Reservoir", "Sand A")
    controller.selected_interval_id = None
    dialog = InterpretationIntervalsDialog(controller)
    emitted: list[tuple[str, str]] = []
    dialog.interval_selected.connect(lambda first, second: emitted.append((first, second)))
    interpretation_id = controller.current_interpretation().interpretation_id

    assert dialog.select_interval(interpretation_id, interval.interval_id) is True

    assert controller.selected_interval_id == interval.interval_id
    assert dialog.table.currentRow() == 0
    assert emitted == []
    dialog.close()
