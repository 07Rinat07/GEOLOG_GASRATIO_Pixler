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


def test_document_passport_preserves_authored_geometry_and_independent_copy() -> None:
    from geoworkbench.domain.models import MasterlogHeaderElement, MasterlogTemplate
    from geoworkbench.printing.document_renderer import _print_header_template

    template = MasterlogTemplate("passport", "Masterlog", header_elements=[
        MasterlogHeaderElement("customer", "text", 10, 5, 45, 5,
                               {"font_size_mm": 2.0, "text": "ALMEX PLUS",
                                "style": {"color": "#123456"}}),
    ])
    prepared = _print_header_template(template)
    assert prepared == template
    assert prepared is not template
    assert prepared.header_elements[0] is not template.header_elements[0]
    assert prepared.header_elements[0].properties["font_size_mm"] == 2.0
    assert prepared.header_elements[0].width_mm == 45
    assert prepared.header_elements[0].height_mm == 5
    prepared.header_elements[0].properties["font_size_mm"] = 4.0
    prepared.header_elements[0].properties["style"]["color"] = "#ffffff"
    assert template.header_elements[0].properties["font_size_mm"] == 2.0
    assert template.header_elements[0].properties["style"]["color"] == "#123456"
