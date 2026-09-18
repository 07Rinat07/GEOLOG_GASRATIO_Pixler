from geoworkbench.catalogs.sensors import default_sensor_catalog
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea

from geoworkbench.ui.sensor_catalog_dialog import MnemonicRuleDialog, SensorCatalogDialog


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



def test_sensor_catalog_uses_adaptive_toolbar_and_fits_work_area(qapp) -> None:
    dialog = SensorCatalogDialog(default_sensor_catalog())
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.actions_toolbar.objectName() == "sensor-catalog-actions"
        assert len(dialog.actions_toolbar.actions()) == 6
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
    finally:
        dialog.close()


def test_mnemonic_rule_keeps_actions_outside_scroll_area(qapp) -> None:
    dialog = MnemonicRuleDialog()
    try:
        scroll = dialog.findChild(QScrollArea)
        buttons = dialog.findChild(QDialogButtonBox)
        assert scroll is not None
        assert buttons is not None
        assert not scroll.isAncestorOf(buttons)
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
    finally:
        dialog.close()
