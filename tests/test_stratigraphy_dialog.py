import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QTableWidget, QTabWidget

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.stratigraphy_dialog import (
    StratigraphyDialog,
    StratigraphyIntervalDialog,
)


def _controller() -> StratigraphyController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 300.0]))
    )
    return StratigraphyController(session)


def test_stratigraphy_dialog_adds_project_interval(qapp) -> None:
    controller = _controller()
    dialog = StratigraphyDialog(controller, language=AppLanguage.EN)
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(200.0)
    dialog.rank_input.setCurrentText("System / Period")
    dialog.code_input.setText("K")
    dialog.name_input.setText("Cretaceous")
    dialog.color_input.setText("#7fc64e")

    dialog._add()

    table = dialog.findChild(QTableWidget, "stratigraphy-intervals-table")
    assert table is not None and table.rowCount() == 1
    assert table.horizontalHeaderItem(2).text() == "Rank"
    assert table.item(0, 3).text() == "K"
    assert dialog.findChild(QPushButton, "stratigraphy-add-button").text() == "Add"
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()


def test_interval_dialog_returns_mouse_selected_depths(qapp) -> None:
    dialog = StratigraphyIntervalDialog(150.0, 175.0, language=AppLanguage.RU)
    dialog.rank_input.setCurrentText("Stage / Age")
    dialog.code_input.setText("K1a")
    dialog.name_input.setText("Альб")
    dialog.set_text_presentation("vertical_bottom_to_top", "bottom")

    values = dialog.values()

    assert values["top_depth"] == 150.0
    assert values["bottom_depth"] == 175.0
    assert values["rank"] == "Stage / Age"
    assert values["code"] == "K1a"
    assert values["text_orientation"] == "vertical_bottom_to_top"
    assert values["text_position"] == "bottom"
    dialog.close()


def test_interval_dialog_returns_all_languages_from_catalog(qapp) -> None:
    dialog = StratigraphyIntervalDialog(150.0, 175.0, language=AppLanguage.EN)
    dialog.catalog_input.setCurrentIndex(1)
    dialog.description_inputs["ru"].setText("Описание")
    dialog.description_inputs["kk"].setText("Сипаттама")
    dialog.description_inputs["en"].setText("Description")

    values = dialog.values()

    tabs = dialog.findChild(QTabWidget, "stratigraphy-quick-language-tabs")
    assert tabs is not None and tabs.count() == 3
    assert set(values["name_i18n"]) == {"ru", "kk", "en"}
    assert values["description_i18n"] == {
        "ru": "Описание",
        "kk": "Сипаттама",
        "en": "Description",
    }
    dialog.close()


def test_stratigraphy_dialog_edits_all_languages_and_catalog_fills_names(qapp) -> None:
    controller = _controller()
    dialog = StratigraphyDialog(controller, language=AppLanguage.EN)
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(200.0)
    dialog.catalog_input.setCurrentIndex(1)

    tabs = dialog.findChild(QTabWidget, "stratigraphy-language-tabs")
    assert tabs is not None and tabs.count() == 3
    assert all(dialog.name_inputs[language].text() for language in ("ru", "kk", "en"))
    dialog.description_inputs["ru"].setText("Описание")
    dialog.description_inputs["kk"].setText("Сипаттама")
    dialog.description_inputs["en"].setText("Description")
    dialog._add()

    interval = controller.available()[0]
    assert set(interval.name_i18n) == {"ru", "kk", "en"}
    assert interval.description_i18n == {
        "ru": "Описание",
        "kk": "Сипаттама",
        "en": "Description",
    }
    dialog.close()


def test_stratigraphy_dialog_does_not_promote_legacy_fallback(qapp) -> None:
    controller = _controller()
    interval = controller.add(100.0, 180.0, "K1", name="Legacy name")
    dialog = StratigraphyDialog(controller, language=AppLanguage.RU)
    dialog.table.selectRow(0)
    dialog.code_input.setText("K1-updated")
    dialog._update()

    assert interval.name == "Legacy name"
    assert interval.name_i18n == {}
    dialog.close()
