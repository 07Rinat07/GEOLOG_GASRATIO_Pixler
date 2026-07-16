from PySide6.QtGui import QPageLayout, QPageSize

from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.print_page_dialog import PrintPageDialog


def test_print_page_settings_map_to_qt_page_layout() -> None:
    settings = PrintPageSettings(
        PrintPageFormat.A3, PrintOrientation.LANDSCAPE
    )

    assert settings.qt_page_size.id() == QPageSize.PageSizeId.A3
    assert settings.qt_orientation is QPageLayout.Orientation.Landscape


def test_print_page_dialog_round_trips_settings(qapp) -> None:
    initial = PrintPageSettings(
        PrintPageFormat.A3, PrintOrientation.LANDSCAPE
    )
    dialog = PrintPageDialog(initial=initial, language=AppLanguage.EN)

    assert dialog.windowTitle() == "Page setup"
    assert dialog.page_settings() == initial
    assert dialog.orientation_combo.currentText() == "Landscape"
    dialog.close()
