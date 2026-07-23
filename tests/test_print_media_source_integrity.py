from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_document_renderer_builds_cartesian_vertical_and_horizontal_pages() -> None:
    source = (ROOT / "src/geoworkbench/printing/document_renderer.py").read_text()

    assert "build_horizontal_continuations" in source
    assert "for vertical in vertical_pages" in source
    assert "for continuation in continuations" in source
    assert "PrintDocumentPage(vertical, continuation, index, total)" in source


def test_physical_output_requires_printer_gate_after_dialog() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text()

    assert "require_physical_gate=True" in source
    assert "result.printer_gate.warnings" in source


def test_preview_and_output_share_the_same_job_scale_mode() -> None:
    renderer = (ROOT / "src/geoworkbench/printing/document_renderer.py").read_text()
    export = (ROOT / "src/geoworkbench/printing/document_export.py").read_text()

    assert "scale_mode=job.page.scale_mode" in renderer
    assert "job=job" in export
    assert "fit_form_columns=job.page.fit_form_columns" not in export


def test_report_passport_signs_scale_and_continuation_settings() -> None:
    source = (ROOT / "src/geoworkbench/services/print_jobs.py").read_text()

    assert 'renderer="document-renderer:2"' in source
    assert "scale_mode=page.scale_mode.value" in source
    assert "continuation_overlap_mm=page.continuation_overlap_mm" in source


def test_direct_pdf_uses_continuation_plan_and_single_page_formats_fail_explicitly() -> None:
    source = (ROOT / "src/geoworkbench/data/visualization_export.py").read_text()

    assert "build_document_plan" in source
    assert "for page_index, page in enumerate(plan.pages)" in source
    assert "writer.newPage()" in source
    assert "_require_single_output_page(plan" in source
    assert "Используйте Центр печати" in source


def test_printer_margins_are_normalized_to_millimeters() -> None:
    source = (ROOT / "src/geoworkbench/services/print_jobs.py").read_text()

    assert "layout.setUnits(QPageLayout.Unit.Millimeter)" in source


def test_system_print_dialog_receives_full_continuation_range() -> None:
    jobs = (ROOT / "src/geoworkbench/services/print_jobs.py").read_text()
    export = (ROOT / "src/geoworkbench/printing/document_export.py").read_text()

    assert "printer.setFromTo(1, plan.page_count)" in jobs
    assert "selected_page_count(" in jobs
    assert "return selected_page_count(plan.page_count, first, last)" in export
