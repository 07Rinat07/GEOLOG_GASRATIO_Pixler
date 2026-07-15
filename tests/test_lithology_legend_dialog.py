from PySide6.QtWidgets import QDialogButtonBox, QLabel, QTableWidget

from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.lithology_legend import LithologyLegendEntry
from geoworkbench.ui.lithology_legend_dialog import LithologyLegendDialog


def test_lithology_legend_dialog_shows_entries(qapp) -> None:
    dialog = LithologyLegendDialog(
        (LithologyLegendEntry("sandstone", "SS", "Песчаник", "#e7cf8b", "dots"),)
    )

    table = dialog.findChild(QTableWidget, "lithology-legend-table")

    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "SS"
    assert table.item(0, 2).text() == "Песчаник"
    dialog.close()


def test_lithology_legend_dialog_uses_selected_language(qapp) -> None:
    dialog = LithologyLegendDialog(
        (LithologyLegendEntry("sandstone", "SS", "Sandstone", "#e7cf8b", "dots"),),
        language=AppLanguage.EN,
    )
    table = dialog.findChild(QTableWidget, "lithology-legend-table")
    buttons = dialog.findChild(QDialogButtonBox)

    assert table is not None
    assert buttons is not None
    assert dialog.windowTitle() == "Lithology legend"
    assert table.horizontalHeaderItem(0).text() == "Symbol"
    assert table.horizontalHeaderItem(2).text() == "Rock"
    assert table.item(0, 2).text() == "Sandstone"
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()


def test_lithology_legend_dialog_localizes_empty_state(qapp) -> None:
    dialog = LithologyLegendDialog((), language=AppLanguage.KK)

    empty = dialog.findChild(QLabel, "lithology-legend-empty")
    assert empty is not None
    assert empty.text() == "Ағымдағы ұңғымада литологиялық аралықтар жоқ"
    dialog.close()
