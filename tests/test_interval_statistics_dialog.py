from PySide6.QtWidgets import QDialogButtonBox, QLabel, QTableWidget

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interval_statistics_dialog import IntervalStatisticsDialog


def test_interval_statistics_dialog_renders_rows(qapp) -> None:
    dialog = IntervalStatisticsDialog(
        100.0,
        200.0,
        (CurveIntervalStatistics("ROP", "m/h", 5, 1.0, 4.0, 2.5),),
    )

    table = dialog.findChild(QTableWidget, "interval-statistics-table")
    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "ROP"
    assert table.item(0, 8).text() == "2.5"
    dialog.close()


def test_interval_statistics_dialog_uses_selected_language(qapp) -> None:
    dialog = IntervalStatisticsDialog(
        100.0,
        200.0,
        (CurveIntervalStatistics("ROP", "m/h", 5, 1.0, 4.0, 2.5),),
        language=AppLanguage.EN,
    )

    table = dialog.findChild(QTableWidget, "interval-statistics-table")
    assert table is not None
    assert dialog.windowTitle() == "Depth interval statistics"
    assert table.horizontalHeaderItem(0).text() == "Curve"
    assert table.horizontalHeaderItem(8).text() == "Mean"
    assert any(label.text() == "Interval: 100–200" for label in dialog.findChildren(QLabel))
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()
