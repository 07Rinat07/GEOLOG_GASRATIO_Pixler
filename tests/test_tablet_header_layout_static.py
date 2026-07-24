from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text("utf-8")


def test_curve_header_stack_is_top_aligned_with_trailing_stretch() -> None:
    assert "self.curve_header_layout.setAlignment(Qt.AlignmentFlag.AlignTop)" in SOURCE
    assert "self.curve_header_layout.addStretch(1)" in SOURCE
    assert "label, 0, Qt.AlignmentFlag.AlignTop" in SOURCE


def test_shared_header_band_keeps_plot_alignment_contract() -> None:
    body = SOURCE.split("def _synchronize_track_header_bands", 1)[1].split(
        "def _synchronize_track_heights", 1
    )[0]
    assert "curve_height = max(" in body
    assert "set_synchronized_header_height(curve_height)" in body
