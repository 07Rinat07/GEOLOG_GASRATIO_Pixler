from PySide6.QtWidgets import QLabel
import pytest

from geoworkbench.data.visualization_export import (
    VisualizationExportError,
    export_widget_pdf,
    export_widget_png,
    export_widget_svg,
)


def test_visualization_export_writes_valid_png_and_svg(qapp, tmp_path) -> None:
    widget = QLabel("GEOLOG visualization")
    widget.resize(320, 180)
    widget.show()
    qapp.processEvents()

    png = export_widget_png(widget, tmp_path / "plot.png")
    svg = export_widget_svg(widget, tmp_path / "plot.svg")

    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    svg_text = svg.read_text(encoding="utf-8")
    assert "<svg" in svg_text
    assert "GEOLOG visualization" in svg_text
    widget.close()


def test_visualization_export_writes_valid_pdf(qapp, tmp_path) -> None:
    widget = QLabel("GEOLOG PDF")
    widget.resize(640, 360)
    widget.show()
    qapp.processEvents()

    target = export_widget_pdf(widget, tmp_path / "plot.pdf")

    payload = target.read_bytes()
    assert payload.startswith(b"%PDF-")
    assert b"%%EOF" in payload[-1024:]
    widget.close()


def test_visualization_export_rejects_extension_and_overwrite(qapp, tmp_path) -> None:
    widget = QLabel("Plot")
    widget.resize(100, 100)
    target = tmp_path / "plot.png"
    target.write_bytes(b"original")

    with pytest.raises(VisualizationExportError, match="расширение"):
        export_widget_png(widget, tmp_path / "plot.jpg")
    with pytest.raises(FileExistsError):
        export_widget_png(widget, target)

    assert target.read_bytes() == b"original"
