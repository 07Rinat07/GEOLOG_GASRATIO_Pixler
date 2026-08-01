from PySide6.QtCore import QPoint
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QLabel

from geoworkbench.data.visualization_export import export_widget_page_image
from geoworkbench.printing.page_settings import PrintOrientation, PrintPageSettings
from geoworkbench.printing.print_job import (
    PrintExportPreferences,
    PrintHeaderPlacement,
    PrintJobSettings,
    PrintOutputFormat,
    available_output_formats,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.print_center_dialog import PrintCenterDialog


def test_universal_output_formats_include_printer_pdf_and_common_images(qapp) -> None:
    formats = set(available_output_formats())

    assert PrintOutputFormat.PRINTER in formats
    assert PrintOutputFormat.PDF in formats
    assert PrintOutputFormat.PNG in formats
    assert PrintOutputFormat.JPEG in formats
    assert PrintOutputFormat.BMP in formats
    assert PrintOutputFormat.SVG in formats


def test_print_center_builds_a4_landscape_jpeg_job(qapp, tmp_path) -> None:
    dialog = PrintCenterDialog(
        initial_page=PrintPageSettings(
            orientation=PrintOrientation.LANDSCAPE,
            margin_left_mm=8.0,
            margin_top_mm=9.0,
            margin_right_mm=10.0,
            margin_bottom_mm=11.0,
        ),
        initial_preferences=PrintExportPreferences(
            output_format=PrintOutputFormat.JPEG,
            dpi=300,
            image_quality=88,
        ),
        language=AppLanguage.EN,
        source_name="Gas Ratio form",
    )
    dialog.path_input.setText(str(tmp_path / "gas-ratio.jpeg"))

    job = dialog.job_settings()

    assert job.output_format is PrintOutputFormat.JPEG
    assert job.target == tmp_path / "gas-ratio.jpeg"
    assert job.page.orientation is PrintOrientation.LANDSCAPE
    assert job.page.fit_form_columns is True
    assert job.page.margin_left_mm == 8.0
    assert job.page.margin_bottom_mm == 11.0
    assert job.dpi == 300
    assert job.image_quality == 88
    assert dialog.ok_button.text() == "Export"
    dialog.close()


def test_print_center_switches_to_physical_printer_without_file(qapp) -> None:
    dialog = PrintCenterDialog(language=AppLanguage.RU)
    dialog.destination_tabs.setCurrentIndex(0)

    job = dialog.job_settings()
    preferences = dialog.preferences()

    assert job.output_format is PrintOutputFormat.PRINTER
    assert job.target is None
    assert not dialog.path_input.isEnabled()
    assert dialog.ok_button.text() == "Печатать"
    assert preferences.output_format is PrintOutputFormat.PRINTER
    dialog.close()


def test_print_center_separates_printer_and_file_destinations(qapp) -> None:
    dialog = PrintCenterDialog(language=AppLanguage.RU)

    assert dialog.destination_tabs.currentIndex() == 0
    assert dialog.selected_output() is PrintOutputFormat.PRINTER
    dialog.destination_tabs.setCurrentIndex(1)

    assert dialog.selected_output() is PrintOutputFormat.PDF
    assert dialog.path_input.isEnabled()
    assert dialog.ok_button.text() == "Экспортировать"
    dialog.close()


def test_print_center_keeps_primary_action_visible_in_short_window(qapp) -> None:
    dialog = PrintCenterDialog(language=AppLanguage.RU, source_name="Планшет")
    dialog.resize(640, 480)
    dialog.show()
    qapp.processEvents()

    button_bottom = dialog.ok_button.mapTo(
        dialog, QPoint(0, dialog.ok_button.height())
    ).y()

    assert dialog.settings_scroll.verticalScrollBar().maximum() > 0
    assert dialog.ok_button.isVisibleTo(dialog)
    assert button_bottom <= dialog.contentsRect().bottom() + 1
    assert dialog.settings_scroll.geometry().bottom() < dialog.action_bar.geometry().top()
    assert dialog.ok_button.objectName() == "print-center-primary-action"
    assert "принтера" in dialog.action_summary.text()
    assert dialog.ok_button.text() == "Печатать"
    assert dialog.header_preview.maximumHeight() == 68
    dialog.close()


def test_print_center_switches_paired_header_with_a4_orientation(qapp) -> None:
    portrait = "factory-header:a4_technology_portrait"
    landscape = "factory-header:a4_technology_landscape"
    dialog = PrintCenterDialog(
        language=AppLanguage.RU,
        header_choices=((portrait, "Portrait"), (landscape, "Landscape")),
        paired_header_template_ids={
            "portrait": portrait,
            "landscape": landscape,
        },
    )

    assert dialog.header_combo.currentData() == portrait
    dialog.orientation_combo.setCurrentIndex(
        dialog.orientation_combo.findData(PrintOrientation.LANDSCAPE.value)
    )

    assert dialog.header_combo.currentData() == landscape
    dialog.header_placement_combo.setCurrentIndex(
        dialog.header_placement_combo.findData(PrintHeaderPlacement.FIRST_PAGE.value)
    )

    assert dialog.job_settings().header_placement is PrintHeaderPlacement.FIRST_PAGE
    dialog.close()


def test_print_center_can_repeat_column_header_at_bottom(qapp, tmp_path) -> None:
    dialog = PrintCenterDialog(
        initial_preferences=PrintExportPreferences(repeat_column_header_at_bottom=True)
    )
    dialog.path_input.setText(str(tmp_path / "repeat.pdf"))

    job = dialog.job_settings()
    preferences = dialog.preferences()

    assert job.repeat_column_header_at_bottom is True
    assert preferences.repeat_column_header_at_bottom is True
    dialog.close()


def test_page_raster_export_writes_a4_png_and_jpeg(qapp, tmp_path) -> None:
    widget = QLabel("Universal print center")
    widget.resize(640, 360)
    widget.show()
    qapp.processEvents()
    settings = PrintPageSettings(
        orientation=PrintOrientation.PORTRAIT,
        margin_left_mm=10.0,
        margin_top_mm=10.0,
        margin_right_mm=10.0,
        margin_bottom_mm=10.0,
    )

    png = export_widget_page_image(
        widget,
        tmp_path / "page.png",
        output_format=PrintOutputFormat.PNG,
        page_settings=settings,
        dpi=96,
    )
    jpg = export_widget_page_image(
        widget,
        tmp_path / "page.jpg",
        output_format=PrintOutputFormat.JPEG,
        page_settings=settings,
        dpi=96,
        quality=85,
    )

    expected = settings.page_pixel_size(widget.width(), widget.height(), 96)
    for path in (png, jpg):
        reader = QImageReader(str(path))
        assert reader.canRead()
        assert reader.size() == expected
        assert path.stat().st_size > 100
    widget.close()


def test_print_job_normalizes_jpeg_and_tiff_extensions(tmp_path) -> None:
    jpeg = PrintJobSettings(
        output_format=PrintOutputFormat.JPEG,
        target=tmp_path / "report.png",
    )
    tiff = PrintJobSettings(
        output_format=PrintOutputFormat.TIFF,
        target=tmp_path / "report",
    )

    assert jpeg.normalized_target() == tmp_path / "report.jpg"
    assert tiff.normalized_target() == tmp_path / "report.tiff"


def test_every_available_raster_format_can_be_written(qapp, tmp_path) -> None:
    widget = QLabel("All raster formats")
    widget.resize(320, 180)
    widget.show()
    qapp.processEvents()
    settings = PrintPageSettings()

    raster_formats = [item for item in available_output_formats() if item.is_raster]
    assert PrintOutputFormat.PNG in raster_formats
    assert PrintOutputFormat.JPEG in raster_formats
    for output in raster_formats:
        target = tmp_path / f"page{output.suffix}"
        export_widget_page_image(
            widget,
            target,
            output_format=output,
            page_settings=settings,
            dpi=72,
            quality=80,
        )
        reader = QImageReader(str(target))
        assert reader.canRead(), f"{output.value}: {reader.errorString()}"
        assert reader.size() == settings.page_pixel_size(widget.width(), widget.height(), 72)
    widget.close()
