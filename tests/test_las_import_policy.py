from pathlib import Path

import pytest

from geoworkbench.data.las_import_policy import LasImportMode, evaluate_las_import
from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
    LasSourceSnapshot,
)
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection


def make_report(*issues: LasImportIssue) -> LasImportReport:
    return LasImportReport(
        LasSourceSnapshot(
            Path("source.las"), 1, "0" * 64, "utf-8", "lf", (), "2.0", "NO", -999.25
        ),
        DepthAxisReport(DepthDirection.ASCENDING, 1.0, 2.0, 1.0, True, 0, 0, 0),
        issues,
    )


def test_all_modes_accept_clean_report() -> None:
    report = make_report()

    for mode in LasImportMode:
        decision = evaluate_las_import(report, mode)
        assert decision.accepted
        assert not decision.requires_confirmation


def test_strict_blocks_warning_while_compatible_accepts_it() -> None:
    warning = LasImportIssue("descending", LasIssueSeverity.WARNING, "Descending")
    report = make_report(warning)

    strict = evaluate_las_import(report, LasImportMode.STRICT)
    compatible = evaluate_las_import(report, LasImportMode.COMPATIBLE)

    assert not strict.accepted
    assert strict.blocking_issues == (warning,)
    assert compatible.accepted
    assert compatible.review_issues == (warning,)
    assert not compatible.requires_confirmation


def test_manual_requires_confirmation_for_warning() -> None:
    warning = LasImportIssue("missing-null", LasIssueSeverity.WARNING, "Missing NULL")

    decision = evaluate_las_import(make_report(warning), LasImportMode.MANUAL)

    assert decision.accepted
    assert decision.requires_confirmation
    assert decision.review_issues == (warning,)


@pytest.mark.parametrize("mode", list(LasImportMode))
def test_errors_block_every_mode(mode: LasImportMode) -> None:
    error = LasImportIssue("broken", LasIssueSeverity.ERROR, "Broken")

    decision = evaluate_las_import(make_report(error), mode)

    assert not decision.accepted
    assert decision.blocking_issues == (error,)


def test_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="режим"):
        evaluate_las_import(make_report(), "unknown")  # type: ignore[arg-type]
