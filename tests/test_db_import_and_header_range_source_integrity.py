from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_import_review_can_normalize_mixed_index_without_touching_source() -> None:
    service = (ROOT / "src/geoworkbench/services/import_review.py").read_text(
        encoding="utf-8"
    )
    dialog = (ROOT / "src/geoworkbench/ui/import_review_dialog.py").read_text(
        encoding="utf-8"
    )

    assert "sort_by_index: bool = False" in service
    assert "_sort_dataset_by_active_index(candidate)" in service
    assert 'IMPORT_REVIEW_SORTED_BY_INDEX' in service
    assert 'self.sort_index = QCheckBox' in dialog
    assert 'sort_by_index=self.sort_index.isChecked()' in dialog


def test_paradox_batch_prefers_explicit_index_and_sorts_export_copy() -> None:
    source = (ROOT / "src/geoworkbench/importers/paradox/batch.py").read_text(
        encoding="utf-8"
    )

    assert '_PREFERRED_DEPTH_FIELDS' in source
    assert '_select_automatic_candidate' in source
    assert 'replace(plan, active_role=mode, sort_by_index=True)' in source


def test_curve_header_contains_direct_range_editor_and_persists_via_controller() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert "class CurveHeaderEditor(QFrame):" in tablet
    assert "range_changed = Signal(str, float, float)" in tablet
    assert "auto_range_requested = Signal(str)" in tablet
    assert "track_curve_range_requested = Signal(str, str, float, float)" in tablet
    assert "self.tablet_controller.set_curve_display_settings" in window
    assert "_set_curve_range_from_header" in window
    assert "_set_curve_auto_range_from_header" in window
    assert "header_text_color_button" in (
        ROOT / "src/geoworkbench/ui/curve_settings_dialog.py"
    ).read_text(encoding="utf-8")
    assert "header_line_color_button" in (
        ROOT / "src/geoworkbench/ui/curve_settings_dialog.py"
    ).read_text(encoding="utf-8")


def test_curve_header_has_visible_grid_aligned_scale_and_editable_unit() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")
    window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "class CurveScaleRuler(QWidget):" in tablet
    assert "normalized_grid_lines(self._major_divisions, self._minor_divisions)" in tablet
    assert "unit_changed = Signal(str, str)" in tablet
    assert "scale_changed = Signal(str, str)" in tablet
    assert "track_curve_unit_requested = Signal(str, str, str)" in tablet
    assert "track_curve_scale_requested = Signal(str, str, str)" in tablet
    assert tablet.count("apply_range_tooltip=self._localizer.text(") == 2
    assert "elif definition.kind is TrackKind.CALCIMETRY:" in tablet
    assert "_set_curve_unit_from_header" in window
    assert "_set_curve_scale_from_header" in window
