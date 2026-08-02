from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "tools/capture_a4_masterlog_control.py"


def test_control_pdf_matches_requested_a4_landscape_auto_contract() -> None:
    source = CONTROL.read_text(encoding="utf-8")

    assert "page_format=PrintPageFormat.A4" in source
    assert "orientation=PrintOrientation.LANDSCAPE" in source
    assert "scale_mode=PrintScaleMode.FIT" in source
    assert "fit_form_columns=True" in source
    assert "range_mode=PrintRangeMode.FULL" in source
    assert "auto_units_per_page=True" in source
    assert "header_placement=PrintHeaderPlacement.FIRST_PAGE" in source
    assert "repeat_column_header_at_bottom=True" in source


def test_control_pdf_exercises_dense_print_curve_header() -> None:
    source = CONTROL.read_text(encoding="utf-8")

    assert '"components"' in source
    assert '("C1", "C2", "C3", "IC4", "NC4", "IC5")' in source
    assert '"kazgeology_reference_blank"' in source
    assert 'preview_names = ("first-page.png", "second-page.png", "last-page.png")' in source
