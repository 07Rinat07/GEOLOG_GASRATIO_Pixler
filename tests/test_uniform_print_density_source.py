from pathlib import Path


def test_renderer_uses_shared_physical_gap_contract() -> None:
    source = Path("src/geoworkbench/printing/document_renderer.py").read_text(
        encoding="utf-8"
    )

    assert "vertical_gap = _vertical_gap_height(painter)" in source
    assert "header.bottom() + vertical_gap / 2.0" in source
    assert "footer.top() - header.bottom() - vertical_gap" in source
    assert "header.bottom() + 2.0" not in source


def test_hidden_print_viewport_preserves_requested_graph_body() -> None:
    source = Path("src/geoworkbench/printing/tablet_print.py").read_text(
        encoding="utf-8"
    )

    assert "requested_body_height = max(" in source
    assert "int(target_content_height) - header_height" in source
    assert "desired_height = measured_header_height + requested_body_height" in source
    assert "minimum_height = header_height + 240" not in source


def test_document_renderer_passes_authored_header_fonts_to_painter(qapp, monkeypatch) -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QWidget

    from geoworkbench.domain.models import MasterlogHeaderElement, MasterlogTemplate
    from geoworkbench.printing import document_renderer
    from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
    from geoworkbench.project.session import ProjectSession

    template = MasterlogTemplate("passport", "Masterlog", header_elements=[
        MasterlogHeaderElement("customer", "text", 10, 5, 45, 5,
                               {"font_size_mm": 2.0, "text": "ALMEX PLUS"}),
    ])
    context = document_renderer.PrintDocumentContext(
        "Masterlog", header_template=template, session=ProjectSession(),
    )
    captured = []

    def capture_header(painter, target, prepared, session, **keywords):
        captured.append(prepared)

    monkeypatch.setattr(document_renderer, "paint_masterlog_header", capture_header)
    monkeypatch.setattr(document_renderer, "paint_widget_page", lambda *args, **kwargs: None)
    widget = QWidget()
    widget.resize(800, 600)
    job = PrintJobSettings(output_format=PrintOutputFormat.PRINTER)
    plan = document_renderer.build_document_plan(widget, job, context=context)
    image = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    try:
        document_renderer.paint_document_page(
            widget, painter, QRectF(0, 0, 800, 600),
            page=plan.pages[0], plan=plan, job=job, context=context,
        )
    finally:
        painter.end()
        widget.close()
        widget.deleteLater()
        qapp.processEvents()
    assert len(captured) == 1
    assert captured[0] == template
    assert captured[0] is not template
    assert captured[0].header_elements[0].properties["font_size_mm"] == 2.0
    assert captured[0].header_elements[0].width_mm == 45
    assert captured[0].header_elements[0].height_mm == 5
