from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from tools.windows_release_matrix import (
    AUTOMATED_CASES,
    CHECKLIST_SCHEMA,
    PHYSICAL_CASES,
    CaseResult,
    SUPPORTED_SCALE_FACTORS,
    build_checklist,
    configure_qt_environment,
    validate_effective_scale,
    validate_physical_arguments,
    wait_for_pdf_ready,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"


def _result(case_id: str, status: str = "passed") -> CaseResult:
    return CaseResult(
        case_id=case_id,
        status=status,
        page_count=1,
        pdf_path=f"{case_id}/{case_id}.pdf",
        screenshot_path=f"{case_id}/{case_id}.png",
        pdf_sha256="a" * 64,
        pdf_size_bytes=2048,
        page_sizes_points=((595.0, 842.0),),
    )


def _args(**changes) -> argparse.Namespace:
    values = {
        "printer": None,
        "operator": None,
        "print_test": False,
        "confirm_physical_output": False,
    }
    values.update(changes)
    return argparse.Namespace(**values)


def test_matrix_covers_required_media_scale_and_hidpi_contract() -> None:
    assert SUPPORTED_SCALE_FACTORS == (1.0, 1.25, 1.5, 2.0)
    assert {case.page_format for case in AUTOMATED_CASES} >= {"a4", "a3", "roll"}
    assert {case.orientation for case in AUTOMATED_CASES} == {"portrait", "landscape"}
    assert {case.scale_mode for case in AUTOMATED_CASES} == {"fit", "actual_size"}
    assert any(case.expected_min_pages >= 2 for case in AUTOMATED_CASES)
    assert {case.dpi for case in AUTOMATED_CASES} >= {96, 150, 300}
    assert {case.language for case in AUTOMATED_CASES} == {"ru", "kk", "en"}
    tablet_case = next(case for case in AUTOMATED_CASES if case.widget_kind == "tablet")
    assert tablet_case.pagination_mode == "full"
    assert tablet_case.expected_min_pages >= 4
    assert {case.page_format for case in PHYSICAL_CASES} == {"a4", "a3", "custom", "roll"}
    assert any(case.expected_min_pages >= 2 for case in PHYSICAL_CASES)


def test_checklist_stays_pending_until_physical_output_is_confirmed() -> None:
    checklist = build_checklist(
        scale_factor=1.25,
        qt_platform="windows",
        environment={"os": "Windows"},
        cases=(_result("a"), _result("b")),
        physical={"status": "not_run", "required_for_rel_03": True},
    )

    assert checklist["schema"] == CHECKLIST_SCHEMA
    assert checklist["automated"]["status"] == "passed"
    assert checklist["overall_status"] == "pending_physical_printer"


def test_checklist_passes_only_after_automated_and_physical_gates() -> None:
    checklist = build_checklist(
        scale_factor=2.0,
        qt_platform="windows",
        environment={"os": "Windows"},
        cases=tuple(_result(case.case_id) for case in AUTOMATED_CASES),
        physical={"status": "passed", "operator": "Engineer"},
    )

    assert checklist["automated"]["status"] == "passed"
    assert checklist["overall_status"] == "passed"


def test_failed_automated_case_blocks_the_checklist() -> None:
    checklist = build_checklist(
        scale_factor=1.0,
        qt_platform="offscreen",
        environment={},
        cases=(_result("ok"), _result("broken", status="failed")),
        physical={"status": "passed"},
    )

    assert checklist["automated"]["status"] == "failed"
    assert checklist["overall_status"] == "failed"


def test_physical_confirmation_requires_printer_operator_and_real_print() -> None:
    with pytest.raises(ValueError, match="--printer"):
        validate_physical_arguments(_args(confirm_physical_output=True))
    with pytest.raises(ValueError, match="--operator"):
        validate_physical_arguments(
            _args(printer="Engineering Plotter", print_test=True, confirm_physical_output=True)
        )
    with pytest.raises(ValueError, match="--print-test"):
        validate_physical_arguments(
            _args(
                printer="Engineering Plotter",
                operator="Engineer",
                confirm_physical_output=True,
            )
        )


def test_qt_environment_is_set_before_qt_import(monkeypatch) -> None:
    for key in ("QT_SCALE_FACTOR", "QT_QPA_PLATFORM"):
        monkeypatch.delenv(key, raising=False)

    configure_qt_environment(1.5, "offscreen")

    assert __import__("os").environ["QT_SCALE_FACTOR"] == "1.5"
    assert __import__("os").environ["QT_QPA_PLATFORM"] == "offscreen"
    assert (
        __import__("os").environ["QT_SCALE_FACTOR_ROUNDING_POLICY"]
        == "PassThrough"
    )


def test_effective_scale_rejects_an_ignored_hidpi_request() -> None:
    validate_effective_scale(1.25, 1.25)
    validate_effective_scale(1.25, 1.5)

    with pytest.raises(RuntimeError, match="ignored"):
        validate_effective_scale(2.0, 1.0)


def test_release_workflow_runs_and_uploads_windows_acceptance_artifacts() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "windows-acceptance:" in text
    assert "tools/windows_release_matrix.py" in text
    assert "--platform windows" in text
    assert 'foreach ($Scale in @("1.0", "1.25", "1.5", "2.0"))' in text
    assert "build/ci-artifacts/windows-acceptance" in text
    assert "release-windows-acceptance-${{ github.run_id }}" in text
    assert text.count("actions/upload-artifact@") == 3


class _FakePdfDocument:
    def __init__(self, statuses: list[str]) -> None:
        self._statuses = statuses
        self._index = 0

    def status(self):
        value = self._statuses[min(self._index, len(self._statuses) - 1)]
        self._index += 1
        return type("Status", (), {"name": value})()

    def error(self) -> str:
        return "invalid"


class _FakeApplication:
    def __init__(self) -> None:
        self.processed = 0

    def processEvents(self) -> None:
        self.processed += 1


def test_pdf_readiness_waits_for_async_qt_loading() -> None:
    document = _FakePdfDocument(["Loading", "Loading", "Ready"])
    app = _FakeApplication()

    wait_for_pdf_ready(document, app, timeout_seconds=1.0)

    assert app.processed == 2


def test_pdf_readiness_reports_qt_load_error() -> None:
    document = _FakePdfDocument(["Loading", "Error"])

    with pytest.raises(RuntimeError, match="failed to load"):
        wait_for_pdf_ready(document, _FakeApplication(), timeout_seconds=1.0)


def test_actual_size_continuation_case_is_unambiguously_multi_page() -> None:
    case = next(
        item for item in AUTOMATED_CASES
        if item.case_id == "a4-landscape-actual-size-continuation"
    )
    assert case.widget_width >= 8000
    assert case.expected_min_pages >= 2
