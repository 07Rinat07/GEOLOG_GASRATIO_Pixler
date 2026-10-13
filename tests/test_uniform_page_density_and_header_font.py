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


def test_document_passport_preserves_authored_typography_in_independent_print_copy() -> None:
    from geoworkbench.domain.models import MasterlogHeaderElement, MasterlogTemplate
    from geoworkbench.printing.document_renderer import _print_header_template

    template = MasterlogTemplate("passport", "Passport", header_elements=[
        MasterlogHeaderElement("title", "text", 5, 8, 45, 7,
                               {"font_size_mm": 3.5, "text": "Field company"}),
    ])
    prepared = _print_header_template(template)
    element = prepared.header_elements[0]
    assert (element.x_mm, element.y_mm, element.width_mm, element.height_mm) == (5, 8, 45, 7)
    assert element.properties["font_size_mm"] == 3.5
    element.properties["font_size_mm"] = 9.0
    assert template.header_elements[0].properties["font_size_mm"] == 3.5
