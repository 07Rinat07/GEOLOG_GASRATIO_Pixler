from PySide6.QtWidgets import QTableWidget

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interval_statistics_panel import IntervalStatisticsPanel


def test_interval_statistics_panel_renders_and_copies(qapp) -> None:
    panel = IntervalStatisticsPanel(language=AppLanguage.EN)
    panel.set_report(
        dataset_name="Dataset A",
        interval_label="Depth: 100–120 m",
        statistics=(CurveIntervalStatistics("ROP", "m/h", 3, 1.0, 5.0, 3.0, 4),),
        display_names={"ROP": "Rate of Penetration"},
    )

    table = panel.findChild(QTableWidget, "interval-statistics-panel-table")
    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "Rate of Penetration\nROP"
    assert table.item(0, 1).text() == "1"
    assert table.item(0, 2).text() == "3"
    assert table.item(0, 3).text() == "5"
    assert "Observed: 3" in table.item(0, 0).toolTip()
    assert "Zeros: 0" in table.item(0, 0).toolTip()
    assert "Missing: 1" in table.item(0, 0).toolTip()

    panel.copy_to_clipboard()

    assert "Dataset\tDataset A" in qapp.clipboard().text()
    assert "Rate of Penetration\tROP\tm/h\tAvailable\t3\t0\t1\t75" in qapp.clipboard().text()
    panel.close()


def test_interval_statistics_panel_marks_missing_values(qapp) -> None:
    panel = IntervalStatisticsPanel(language=AppLanguage.RU)
    panel.set_report(
        dataset_name="Dataset A",
        interval_label="Глубина: 100–120 м",
        statistics=(
            CurveIntervalStatistics(
                "EMPTY", "ppm", 0, float("nan"), float("nan"), float("nan"), 4
            ),
        ),
    )

    assert panel.table.item(0, 1).text() == "—"
    assert panel.table.item(0, 2).text() == "—"
    assert panel.table.item(0, 3).text() == "—"
    panel.close()
