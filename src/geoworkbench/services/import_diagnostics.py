from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from traceback import format_exception
from typing import Mapping


class ImportDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class ImportDiagnosticStage(StrEnum):
    READ_SOURCE = "read_source"
    PARSE_SOURCE = "parse_source"
    POLICY = "policy"
    REVIEW = "review"
    REGISTER = "register"
    PRESENT = "present"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ImportDiagnostic:
    """One actionable import diagnostic independent of the Qt presentation layer."""

    source: Path
    stage: ImportDiagnosticStage
    code: str
    severity: ImportDiagnosticSeverity
    summary: str
    details: str
    suggested_action: str
    exception_type: str | None = None
    technical_details: str = ""
    context: tuple[tuple[str, str], ...] = ()

    @property
    def blocking(self) -> bool:
        return self.severity in {
            ImportDiagnosticSeverity.ERROR,
            ImportDiagnosticSeverity.FATAL,
        }


@dataclass(frozen=True, slots=True)
class ImportDiagnosticReport:
    diagnostics: tuple[ImportDiagnostic, ...]

    @property
    def error_count(self) -> int:
        return sum(item.blocking for item in self.diagnostics)

    @property
    def warning_count(self) -> int:
        return sum(
            item.severity is ImportDiagnosticSeverity.WARNING
            for item in self.diagnostics
        )

    @property
    def has_items(self) -> bool:
        return bool(self.diagnostics)

    def extend(self, *items: ImportDiagnostic) -> ImportDiagnosticReport:
        return ImportDiagnosticReport((*self.diagnostics, *items))

    def to_text(self, *, include_technical: bool = True) -> str:
        if not self.diagnostics:
            return "No import diagnostics."
        lines: list[str] = []
        for index, item in enumerate(self.diagnostics, start=1):
            lines.extend(
                (
                    f"[{index}] {item.severity.value.upper()} / {item.stage.value} / {item.code}",
                    f"Source: {item.source}",
                    f"Summary: {item.summary}",
                    f"Details: {item.details}",
                    f"Suggested action: {item.suggested_action}",
                )
            )
            if item.exception_type:
                lines.append(f"Exception: {item.exception_type}")
            for key, value in item.context:
                lines.append(f"{key}: {value}")
            if include_technical and item.technical_details:
                lines.extend(("Technical details:", item.technical_details.rstrip()))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def diagnostic_from_exception(
    source: str | Path,
    stage: ImportDiagnosticStage,
    exc: BaseException,
    *,
    context: Mapping[str, object] | None = None,
) -> ImportDiagnostic:
    """Convert a caught exception into a stable, actionable diagnostic."""

    source_path = Path(source)
    code, summary, action = _classify_exception(stage, exc)
    details = str(exc).strip() or repr(exc)
    technical = "".join(format_exception(type(exc), exc, exc.__traceback__))
    normalized_context = tuple(
        sorted((str(key), str(value)) for key, value in (context or {}).items())
    )
    return ImportDiagnostic(
        source=source_path,
        stage=stage,
        code=code,
        severity=(
            ImportDiagnosticSeverity.FATAL
            if isinstance(exc, MemoryError)
            else ImportDiagnosticSeverity.ERROR
        ),
        summary=summary,
        details=details,
        suggested_action=action,
        exception_type=type(exc).__name__,
        technical_details=technical,
        context=normalized_context,
    )


def policy_diagnostic(
    source: str | Path,
    *,
    code: str,
    message: str,
    warning: bool = False,
) -> ImportDiagnostic:
    actions = {
        "duplicate-index-values": (
            "Duplicate index rows are allowed for review. Choose an explicit duplicate "
            "policy (keep all, first or last) before resampling; the source file remains unchanged."
        ),
        "non-uniform-step": (
            "A non-uniform step is valid for display. Keep the original samples or create a "
            "separate resampled copy (for example 0.2 m); do not rewrite the source LAS."
        ),
        "index-gaps": (
            "Index gaps will be shown as missing intervals. Fill/interpolate only in a derived "
            "copy when the geological workflow explicitly requires it."
        ),
    }
    return ImportDiagnostic(
        source=Path(source),
        stage=ImportDiagnosticStage.POLICY,
        code=f"las-{code}",
        severity=(
            ImportDiagnosticSeverity.WARNING
            if warning
            else ImportDiagnosticSeverity.ERROR
        ),
        summary=message,
        details=message,
        suggested_action=actions.get(
            code,
            "Review the LAS header/index/channel mapping. Use compatible or manual mode "
            "only when the source values are trustworthy.",
        ),
    )


def presentation_diagnostic(
    source: str | Path,
    exc: BaseException,
    *,
    dataset_id: str,
    dataset_name: str,
) -> ImportDiagnostic:
    diagnostic = diagnostic_from_exception(
        source,
        ImportDiagnosticStage.PRESENT,
        exc,
        context={"dataset_id": dataset_id, "dataset_name": dataset_name},
    )
    return ImportDiagnostic(
        source=diagnostic.source,
        stage=diagnostic.stage,
        code="dataset-presentation-failed",
        severity=diagnostic.severity,
        summary=(
            "The dataset was imported, but the graphical workspace could not be rendered."
        ),
        details=diagnostic.details,
        suggested_action=(
            "The imported data remains in the project. Open the table view, rebuild the "
            "tablet form, or send the saved diagnostic report to the developer."
        ),
        exception_type=diagnostic.exception_type,
        technical_details=diagnostic.technical_details,
        context=diagnostic.context,
    )


def _classify_exception(
    stage: ImportDiagnosticStage,
    exc: BaseException,
) -> tuple[str, str, str]:
    if isinstance(exc, FileNotFoundError):
        return (
            "source-file-not-found",
            "The source file was not found.",
            "Check that the file still exists and that the path or removable drive is available.",
        )
    if isinstance(exc, PermissionError):
        return (
            "source-permission-denied",
            "The source file cannot be read because access was denied.",
            "Copy the file to a writable local folder or grant read permission, then retry.",
        )
    if isinstance(exc, UnicodeError):
        return (
            "source-encoding-error",
            "The source text encoding could not be decoded safely.",
            "Retry with manual review and select/repair the encoding; keep the original file unchanged.",
        )
    if isinstance(exc, MemoryError):
        return (
            "memory-exhausted",
            "The import exhausted available memory.",
            "Close other large projects, retry with one file, or split the source into smaller intervals.",
        )
    if stage is ImportDiagnosticStage.REVIEW:
        return (
            "import-review-failed",
            "The import review could not build or commit the selected mapping.",
            "Reset the affected channel mapping, verify index role/type and units, then retry.",
        )
    if stage is ImportDiagnosticStage.REGISTER:
        return (
            "dataset-registration-failed",
            "The parsed dataset could not be attached to the project.",
            "Save the current project, retry in a new well, and inspect duplicate IDs or project integrity.",
        )
    if stage is ImportDiagnosticStage.PRESENT:
        return (
            "dataset-presentation-failed",
            "The dataset was imported but could not be displayed.",
            "Open the table view and rebuild the graphical form; the source data is still preserved.",
        )
    if isinstance(exc, ValueError):
        return (
            "invalid-source-data",
            "The source contains values or metadata that violate the import contract.",
            "Check the LAS index, row column count, NULL sentinel, units and duplicate channel names.",
        )
    if isinstance(exc, RuntimeError):
        return (
            "import-runtime-error",
            "The import pipeline rejected the source at the current stage.",
            "Read the diagnostic details, correct the indicated source/header problem, and retry.",
        )
    return (
        "unexpected-import-error",
        "An unexpected error occurred during import.",
        "Save or copy the diagnostic report and send it with the source-file description to the developer.",
    )


def persist_import_diagnostic_report(
    report: ImportDiagnosticReport,
    directory: str | Path,
    *,
    prefix: str = "import",
) -> Path:
    """Atomically persist a diagnostic report for later support analysis."""

    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    target = root / f"{prefix}_{stamp}.txt"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(report.to_text(include_technical=True), encoding="utf-8")
    temporary.replace(target)
    return target

