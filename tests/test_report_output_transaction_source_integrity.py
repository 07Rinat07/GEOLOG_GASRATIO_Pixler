from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_report_passport_writer_is_owned_by_transaction_service() -> None:
    matches: list[str] = []
    for source in (ROOT / "src/geoworkbench").rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        if "write_report_passport(" in text:
            matches.append(source.relative_to(ROOT).as_posix())

    assert sorted(matches) == sorted([
        "src/geoworkbench/services/report_output_transaction.py",
        "src/geoworkbench/services/report_passport.py",
    ])


def test_all_active_report_exports_use_recoverable_transaction() -> None:
    expected = {
        "src/geoworkbench/services/print_jobs.py",
        "src/geoworkbench/ui/main_window.py",
        "src/geoworkbench/printing/masterlog_renderer.py",
        "src/geoworkbench/printing/interpretation_report.py",
    }
    for relative in expected:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "execute_report_output_transaction" in source, relative


def test_passport_schema_contains_written_output_fingerprints() -> None:
    source = (
        ROOT / "src/geoworkbench/services/report_passport.py"
    ).read_text(encoding="utf-8")

    assert "REPORT_PASSPORT_SCHEMA_VERSION = 4" in source
    assert "class ReportOutputArtifactSnapshot" in source
    assert "finalize_report_passport(" in source
    assert "verify_report_output_artifacts(" in source
    assert "Fingerprint output artifact не совпадает" in source


def test_transaction_journals_before_replacing_outputs() -> None:
    source = (
        ROOT / "src/geoworkbench/services/report_output_transaction.py"
    ).read_text(encoding="utf-8")

    prepared = source.index('"prepared"')
    backed_up = source.index('"backed-up"')
    committed = source.index('"committed"')
    assert prepared < backed_up < committed
    assert "operation.backup" in source
    assert "recover_report_output_transaction(target)" in source
    assert "_verify_installed_outputs" in source
