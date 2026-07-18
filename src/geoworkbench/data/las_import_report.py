from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from pathlib import Path

from geoworkbench.services.depth_axis import DepthAxisReport


class LasIssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class LasImportIssue:
    code: str
    severity: LasIssueSeverity
    message: str


@dataclass(frozen=True, slots=True)
class LasSourceSnapshot:
    """Immutable provenance metadata for the exact source file read from disk."""

    path: Path
    size_bytes: int
    sha256: str
    encoding: str
    newline_style: str
    section_names: tuple[str, ...]
    las_version: str | None
    wrap: str | None
    null_value: float | None


@dataclass(frozen=True, slots=True)
class LasImportReport:
    source: LasSourceSnapshot
    depth_axis: DepthAxisReport
    issues: tuple[LasImportIssue, ...]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity is LasIssueSeverity.ERROR for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity is LasIssueSeverity.WARNING for issue in self.issues)

    def messages(self, *, minimum: LasIssueSeverity = LasIssueSeverity.WARNING) -> tuple[str, ...]:
        ranks = {
            LasIssueSeverity.INFO: 0,
            LasIssueSeverity.WARNING: 1,
            LasIssueSeverity.ERROR: 2,
        }
        return tuple(
            issue.message for issue in self.issues if ranks[issue.severity] >= ranks[minimum]
        )


def validate_import_report(report: LasImportReport) -> None:
    source = report.source
    if isinstance(source.size_bytes, bool) or not isinstance(source.size_bytes, int):
        raise ValueError("Размер source provenance должен быть целым числом")
    if source.size_bytes < 0:
        raise ValueError("Размер source provenance не может быть отрицательным")
    if len(source.sha256) != 64 or any(
        character not in "0123456789abcdef" for character in source.sha256
    ):
        raise ValueError("SHA-256 import report имеет неверный формат")
    if not source.encoding:
        raise ValueError("Кодировка source provenance не задана")
    if source.newline_style not in {"lf", "crlf", "cr", "mixed", "none"}:
        raise ValueError("Стиль строк source provenance не поддерживается")
    if not all(isinstance(name, str) and name for name in source.section_names):
        raise ValueError("Имена секций source provenance должны быть непустыми строками")
    for header_value in (source.las_version, source.wrap):
        if header_value is not None and not isinstance(header_value, str):
            raise ValueError("Версия и WRAP source provenance должны быть строками")
    null_value = source.null_value
    if null_value is not None and not isfinite(null_value):
        raise ValueError("NULL source provenance должен быть конечным")

    depth = report.depth_axis
    for depth_value in (depth.start, depth.stop, depth.nominal_step):
        if depth_value is not None and not isfinite(depth_value):
            raise ValueError("Числовые поля depth provenance должны быть конечными")
    for count in (depth.duplicate_count, depth.missing_count, depth.gap_count):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("Счётчики depth provenance должны быть неотрицательными целыми")
    if not isinstance(depth.is_uniform, bool):
        raise ValueError("is_uniform depth provenance должен быть логическим")
    for issue in report.issues:
        if not issue.code or not issue.message:
            raise ValueError("Import issue должен содержать code и message")
        if not isinstance(issue.severity, LasIssueSeverity):
            raise ValueError("Import issue содержит неизвестный severity")
