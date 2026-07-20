from geoworkbench.catalogs.sensors import default_sensor_catalog
from geoworkbench.ui.sensor_catalog_dialog import SensorCatalogDialog


def test_sensor_catalog_dialog_filters_reference_entries(qapp) -> None:
    dialog = SensorCatalogDialog(default_sensor_catalog())

    assert dialog.tree.topLevelItemCount() >= 400
    dialog.search.setText("methane")
    qapp.processEvents()

    rows = [
        dialog.tree.topLevelItem(index).text(0) for index in range(dialog.tree.topLevelItemCount())
    ]
    assert "C1" in rows
    assert len(rows) < 20
    dialog.close()
