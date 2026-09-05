from tools.capture_interpretation_report import _normalized_text


def test_pdf_marker_text_normalization_collapses_line_wrapping() -> None:
    assert (
        _normalized_text("Относительная\nсила\tаномалии")
        == "Относительная сила аномалии"
    )
