from PySide6.QtWidgets import QTableWidget

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics
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
    assert table.item(0, 5).text() == "2.5"
    dialog.close()
