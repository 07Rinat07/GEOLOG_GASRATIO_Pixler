from PySide6.QtGui import QPageLayout, QPageSize
import pytest

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
        PrintPageFormat.CUSTOM, PrintOrientation.LANDSCAPE, 420.0, 900.0
    )
    dialog = PrintPageDialog(initial=initial, language=AppLanguage.EN)

    assert dialog.windowTitle() == "Page setup"
    assert dialog.page_settings() == initial
    assert dialog.orientation_combo.currentText() == "Landscape"
    assert dialog.width_input.isEnabled() is True
    assert dialog.width_input.value() == 420.0
    dialog.close()


def test_custom_print_page_maps_millimeter_dimensions() -> None:
    settings = PrintPageSettings(
        PrintPageFormat.CUSTOM, PrintOrientation.PORTRAIT, 300.0, 1200.0
    )

    size = settings.qt_page_size.size(QPageSize.Unit.Millimeter)
    assert size.width() == 300.0
    assert size.height() == 1200.0


def test_roll_page_length_follows_content_aspect_and_is_bounded() -> None:
    settings = PrintPageSettings(
        PrintPageFormat.ROLL, PrintOrientation.LANDSCAPE, 300.0, 297.0
    )

    regular = settings.page_size_for_content(1000, 3000).size(
        QPageSize.Unit.Millimeter
    )
    bounded = settings.page_size_for_content(100, 10000).size(
        QPageSize.Unit.Millimeter
    )

    assert regular.width() == 300.0
    assert regular.height() == 900.0
    assert bounded.height() == 5000.0
    assert settings.qt_orientation is QPageLayout.Orientation.Portrait


def test_roll_dialog_enables_width_but_not_manual_height(qapp) -> None:
    dialog = PrintPageDialog(
        initial=PrintPageSettings(page_format=PrintPageFormat.ROLL)
    )

    assert dialog.width_input.isEnabled() is True
    assert dialog.height_input.isEnabled() is False
    dialog.close()


@pytest.mark.parametrize("width", [0.0, 5000.1, float("nan"), True])
def test_print_page_settings_reject_invalid_custom_width(width: object) -> None:
    with pytest.raises(ValueError, match="ширина"):
        PrintPageSettings(custom_width_mm=width)  # type: ignore[arg-type]
