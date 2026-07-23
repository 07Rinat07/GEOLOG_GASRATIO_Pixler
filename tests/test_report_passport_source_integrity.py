from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_print_center_builds_and_writes_report_passport() -> None:
    window = _source("src/geoworkbench/ui/main_window.py")
    jobs = _source("src/geoworkbench/services/print_jobs.py")

    assert "ReportPassportBuilder().build(self.session, request)" in window
    assert "report_render_settings(job)" in window
    assert "passport=passport" in window
    assert "passport_sidecar_path(target)" in window
    assert "write_report_passport(passport, target" in jobs
    assert "passport_sha256" in jobs
    assert "_build_visualization_passport" in window
    assert "write_report_passport(passport, exported" in window


def test_masterlog_pdf_builds_template_revision_passport() -> None:
    dialog = _source("src/geoworkbench/ui/masterlog_templates_dialog.py")
    renderer = _source("src/geoworkbench/printing/masterlog_renderer.py")

    assert "masterlog_template_snapshot(template)" in dialog
    assert "ReportKind.MASTERLOG" in dialog
    assert 'renderer="masterlog-renderer:1"' in dialog
    assert "passport=passport" in dialog
    assert "write_report_passport(passport, destination" in renderer


def test_report_passport_does_not_persist_absolute_output_path_or_timestamp() -> None:
    service = _source("src/geoworkbench/services/report_passport.py")

    assert "created_at" not in service
    assert "generated_at" not in service
    assert "output_path" not in service
    assert "datetime.now" not in service
    assert "Path(output).resolve" not in service
    assert "target.name + REPORT_PASSPORT_SUFFIX" in service


def test_interpretation_report_uses_well_level_artifact_passport() -> None:
    dialog = _source("src/geoworkbench/ui/interpretation_report_dialog.py")
    renderer = _source("src/geoworkbench/printing/interpretation_report.py")

    assert "ReportPassportBuilder().build_artifact" in dialog
    assert "depth_interval_snapshot" in dialog
    assert "report_definition_snapshot" in dialog
    assert "passport=passport" in dialog
    assert "write_report_passport(passport, destination" in renderer
