from pathlib import Path


def test_fit_print_prefers_one_horizontal_scale_but_never_aborts_pdf() -> None:
    source = Path("src/geoworkbench/printing/tablet_print.py").read_text(encoding="utf-8")

    # Normal pages retain the document-wide horizontal scale. If Qt adds a few
    # runtime pixels after wrapping headers, a bounded uniform fallback keeps
    # every column visible instead of cancelling the complete PDF.
    assert "scale = horizontal_scale" in source
    assert "scale = min(horizontal_scale, vertical_scale)" in source
    assert "must not abort the whole PDF" in source
    assert "y = page.top()" in source
    assert "автоматическая пагинация нарушила единый масштаб" not in source


def test_document_passport_uses_larger_print_only_typography() -> None:
    source = Path("src/geoworkbench/printing/document_renderer.py").read_text(encoding="utf-8")

    # The screen template stays unchanged; only its print copy is enlarged.
    assert "_DOCUMENT_HEADER_FONT_SCALE = 1.60" in source
    assert "prepared = deepcopy(template)" in source
    assert 'element.properties["font_size_mm"]' in source
