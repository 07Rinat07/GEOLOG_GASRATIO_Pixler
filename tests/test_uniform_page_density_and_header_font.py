from pathlib import Path


def test_fit_print_uses_one_horizontal_scale_on_every_page() -> None:
    source = Path("src/geoworkbench/printing/tablet_print.py").read_text(encoding="utf-8")

    # The page interval may change, but the physical grid pitch must not.
    assert "scale = horizontal_scale" in source
    assert "scale = min(horizontal_scale, vertical_scale)" not in source
    assert "y = page.top()" in source
    assert "автоматическая пагинация нарушила единый масштаб" in source


def test_document_passport_uses_larger_print_only_typography() -> None:
    source = Path("src/geoworkbench/printing/document_renderer.py").read_text(encoding="utf-8")

    assert "_DOCUMENT_HEADER_FONT_SCALE = 1.60" in source
    assert "prepared = deepcopy(template)" in source
    assert 'element.properties["font_size_mm"]' in source
