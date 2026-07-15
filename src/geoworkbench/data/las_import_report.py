from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
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
