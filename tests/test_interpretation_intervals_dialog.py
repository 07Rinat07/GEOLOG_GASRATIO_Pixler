import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QScrollArea, QTableWidget, QTabWidget

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


def test_interpretation_dialog_saves_all_interval_languages(qapp) -> None:
    controller = _controller()
    dialog = InterpretationIntervalsDialog(controller, language=AppLanguage.EN)
    dialog.name_inputs["ru"].setText("Основная")
    dialog.name_inputs["kk"].setText("Негізгі")
    dialog.name_inputs["en"].setText("Primary")
    dialog.description_inputs["ru"].setText("Описание")
    dialog.description_inputs["kk"].setText("Сипаттама")
    dialog.description_inputs["en"].setText("Description")
    dialog._save_description()
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(150.0)
    dialog.type_input.setCurrentText("Reservoir")
    dialog.color_input.setText("#fde68a")
    for language, label, comment in (
        ("ru", "Пласт А", "Газ"),
        ("kk", "А қабаты", "Газ белгісі"),
        ("en", "Sand A", "Gas show"),
    ):
        dialog.label_inputs[language].setText(label)
        dialog.comment_inputs[language].setText(comment)

    dialog._add_interval()

    interval = controller.available_intervals()[0]
    interpretation = controller.current_interpretation()
    assert dialog.findChild(QTabWidget, "interpretation-language-tabs").count() == 3
    assert dialog.findChild(QTabWidget, "interpretation-interval-language-tabs").count() == 3
    assert interval.label_i18n == {
        "ru": "Пласт А",
        "kk": "А қабаты",
        "en": "Sand A",
    }
    assert interval.comment_i18n["kk"] == "Газ белгісі"
    assert interpretation.name_i18n["kk"] == "Негізгі"
    assert interpretation.description_i18n["en"] == "Description"
    dialog.close()


def test_interpretation_dialog_preserves_legacy_fallback(qapp) -> None:
    controller = _controller()
    interval = controller.add_interval(100.0, 150.0, "Reservoir", "Legacy label")
    dialog = InterpretationIntervalsDialog(controller, language=AppLanguage.RU)
    dialog.table.selectRow(0)

    assert dialog.label_input.text() == "Legacy label"
    assert interval.label_i18n == {}
    dialog.close()



def test_interpretation_dialog_fits_work_area_with_sticky_close(qapp) -> None:
    dialog = InterpretationIntervalsDialog(_controller(), language=AppLanguage.EN)
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()

        scroll = dialog.findChild(QScrollArea, "interpretation-intervals-body-scroll")
        buttons = dialog.findChild(QDialogButtonBox)
        table = dialog.findChild(QTableWidget, "interpretation-intervals-table")
        assert scroll is not None
        assert buttons is not None
        assert table is not None
        assert scroll.widget() is not None
        assert scroll.widget().isAncestorOf(table)
        assert not scroll.isAncestorOf(buttons)
        assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    finally:
        dialog.close()
