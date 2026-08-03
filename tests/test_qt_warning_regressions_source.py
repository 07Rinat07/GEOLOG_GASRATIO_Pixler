from pathlib import Path


def test_color_button_stylesheet_has_one_closing_brace() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/ui/depth_annotations_dialog.py"
    ).read_text(encoding="utf-8")
    assert 'padding:4px 8px; }"' in source
    assert 'padding:4px 8px; }}"' not in source


def test_annotation_font_combo_receives_positive_point_size() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/ui/depth_annotations_dialog.py"
    ).read_text(encoding="utf-8")
    assert "selected_font.setPointSizeF(max(1.0, float(style.font_size)))" in source
    assert "setCurrentFont(QFont(style.font_family))" not in source


def test_statistics_overlay_logs_only_after_drag_release() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/ui/interval_statistics_overlay.py"
    ).read_text(encoding="utf-8")
    assert "move_constrained(self._drag_origin_local + delta, user_move=False)" in source
    assert "if self._drag_moved:" in source
    assert "self.movedByUser.emit()" in source


def test_wits0_dialog_open_failure_is_reported_without_crashing_main_window() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/ui/main_window.py"
    ).read_text(encoding="utf-8")
    start = source.index("    def open_wits0_capture")
    end = source.index("    def _on_wits0_dataset_changed", start)
    block = source[start:end]
    assert "except Exception as exc:" in block
    assert 'log_exception("wits0.capture.open_failed", exc)' in block
    assert 'self._t("wits0.open_error", error=str(exc))' in block


def test_print_font_never_passes_nonpositive_point_size_to_qt() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/printing/unicode_support.py"
    ).read_text(encoding="utf-8")
    assert "safe_point_size = max(1.0, float(point_size))" in source
    assert "base.setPointSizeF(safe_point_size)" in source
