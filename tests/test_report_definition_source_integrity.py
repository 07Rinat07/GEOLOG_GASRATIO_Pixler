from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_print_preview_and_file_export_share_resolved_report_definition() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    preview = source[source.index("    def _preview_print_job(") : source.index("    def _execute_print_job(")]
    execute = source[source.index("    def _execute_print_job(") : source.index("    def _resolve_print_report(")]
    resolver = source[source.index("    def _resolve_print_report(") : source.index("    def _confirm_print_overwrite(")]

    assert "self._resolve_print_report(" in preview
    assert "self._resolve_print_report(" in execute
    assert "range_mode=PrintRangeMode.CUSTOM" in resolver
    assert "widget.vertical_index_id" in resolver
    assert "index_id=index_id or """ in resolver
    assert "report_definition_snapshot(" in resolver


def test_table_export_uses_resolved_report_not_raw_selection_bounds() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    block = source[source.index("    def _export_selected_table(") : source.index("    def _confirm_export_overwrite(")]

    assert "ReportIntervalMode.SELECTION" in block
    assert "resolve_report(" in block
    assert "export_resolved_report_excel(" in block
    assert "export_resolved_report_text(" in block
    assert "export_current_selection_excel(" not in block
    assert "export_current_selection_text(" not in block


def test_masterlog_preview_pdf_and_system_preview_resolve_definition() -> None:
    source = (ROOT / "src/geoworkbench/ui/masterlog_templates_dialog.py").read_text(
        encoding="utf-8"
    )

    assert source.count("self._resolve_report_definition(template, settings)") >= 3
    assert "profile=ReportProfile.MASTERLOG" in source
    assert "form=report_definition_snapshot(" in source


def test_selection_export_no_longer_imports_qt_selection_object() -> None:
    source = (ROOT / "src/geoworkbench/data/selection_export.py").read_text(encoding="utf-8")
    localization = (ROOT / "src/geoworkbench/services/localization.py").read_text(
        encoding="utf-8"
    )

    assert "services.interval_selection import depth_interval_indices" in source
    assert "services.dataset_selection import depth_interval_indices" not in source
    assert "from PySide6.QtCore import QSettings" not in localization.split(
        "class LanguageSettings", 1
    )[0]


def test_print_center_only_exposes_depth_selection_for_matching_axis() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    block = source[source.index("    def open_print_center(") : source.index("    def _preview_print_job(")]

    assert "paged_tablet.vertical_index_id" in block
    assert "self.session.current_dataset.active_index_id" in block
    assert "selected_vertical_range=selected_range" in block
