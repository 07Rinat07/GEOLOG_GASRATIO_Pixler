from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
)


class LasImportMode(StrEnum):
    STRICT = "strict"
    COMPATIBLE = "compatible"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class LasImportDecision:
    mode: LasImportMode
    accepted: bool
    requires_confirmation: bool
    blocking_issues: tuple[LasImportIssue, ...]
    review_issues: tuple[LasImportIssue, ...]


def evaluate_las_import(report: LasImportReport, mode: LasImportMode) -> LasImportDecision:
    if not isinstance(mode, LasImportMode):
        raise ValueError("Неизвестный режим LAS-импорта")
    errors = tuple(issue for issue in report.issues if issue.severity is LasIssueSeverity.ERROR)
    warnings = tuple(issue for issue in report.issues if issue.severity is LasIssueSeverity.WARNING)
    if mode is LasImportMode.STRICT:
        blocking = errors + warnings
        return LasImportDecision(mode, not blocking, False, blocking, ())
    if mode is LasImportMode.MANUAL:
        return LasImportDecision(mode, not errors, bool(warnings), errors, warnings)
    return LasImportDecision(mode, not errors, False, errors, warnings)
