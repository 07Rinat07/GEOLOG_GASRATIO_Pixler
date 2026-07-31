from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    _chart_block,
)


_LABELS = {
    "title": "Графики интерпретационных кривых по глубине",
    "note": "Печатная проверка графика.",
}


def test_print_chart_uses_dedicated_page_and_safe_width() -> None:
    html = _chart_block(
        "data:image/png;base64,AAAA",
        _LABELS,
        print_layout=True,
    )

    assert "page-break-before: always" in html
    assert "page-break-after: always" in html
    assert "page-break-inside: avoid" in html
    assert "width: 86%" in html
    assert "max-width: 880px" in html


def test_preview_chart_remains_responsive_without_forced_page_break() -> None:
    html = _chart_block(
        "data:image/png;base64,AAAA",
        _LABELS,
        print_layout=False,
    )

    assert "page-break-before: always" not in html
    assert "page-break-after: always" not in html
    assert "width: 100%" in html
    assert "max-width: 1050px" in html
