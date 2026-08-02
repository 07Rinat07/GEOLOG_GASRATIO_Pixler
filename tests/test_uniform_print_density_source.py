from pathlib import Path


def test_renderer_uses_shared_physical_gap_contract() -> None:
    source = Path("src/geoworkbench/printing/document_renderer.py").read_text(
        encoding="utf-8"
    )

    assert "vertical_gap = _vertical_gap_height(painter)" in source
    assert "header.bottom() + vertical_gap / 2.0" in source
    assert "footer.top() - header.bottom() - vertical_gap" in source
    assert "header.bottom() + 2.0" not in source


def test_hidden_print_viewport_does_not_force_240_pixel_body() -> None:
    source = Path("src/geoworkbench/printing/tablet_print.py").read_text(
        encoding="utf-8"
    )

    assert "minimum_height = header_height + 1" in source
    assert "minimum_height = header_height + 240" not in source


def test_document_header_uses_print_only_font_scaling() -> None:
    source = Path("src/geoworkbench/printing/document_renderer.py").read_text(
        encoding="utf-8"
    )

    assert "_DOCUMENT_HEADER_FONT_SCALE = 1.28" in source
    assert "_print_header_template(context.header_template)" in source
    assert "float(raw_size) * _DOCUMENT_HEADER_FONT_SCALE" in source
