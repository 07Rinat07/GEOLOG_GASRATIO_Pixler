from geoworkbench.catalogs.lithotypes import load_lithotype_catalog
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lithology_interval_dialog import LithologyIntervalDialog


def test_lithology_interval_dialog_fits_current_work_area(qapp) -> None:
    dialog = LithologyIntervalDialog(
        100.0,
        101.0,
        load_lithotype_catalog(),
        language=AppLanguage.EN,
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert dialog.lithotype_input.count() > 0
    finally:
        dialog.close()
