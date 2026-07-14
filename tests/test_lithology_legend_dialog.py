from PySide6.QtWidgets import QTableWidget

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
