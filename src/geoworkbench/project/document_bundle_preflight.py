from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Mapping, Protocol

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputSpec,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)


class DocumentBundlePreflightCategory(StrEnum):
    CONFIGURATION = "configuration"
    DATA = "data"
    DEPENDENCY = "dependency"
    TRANSLATION = "translation"


class DocumentBundlePreflightSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class DocumentBundlePreflightIssue:
    code: str
    message: str
    category: DocumentBundlePreflightCategory
    severity: DocumentBundlePreflightSeverity = DocumentBundlePreflightSeverity.ERROR
    output_id: str | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("Preflight issue code and message must not be blank")


@dataclass(frozen=True, slots=True)
class DocumentBundlePreflightReport:
    snapshot_id: str
    issues: tuple[DocumentBundlePreflightIssue, ...]
    draft_mark_required: bool = False

    @property
    def is_ready(self) -> bool:
        return not any(
            issue.severity is DocumentBundlePreflightSeverity.ERROR
            for issue in self.issues
        )

    @property
    def blocking_issues(self) -> tuple[DocumentBundlePreflightIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is DocumentBundlePreflightSeverity.ERROR
        )


class DocumentBundleOutputPreflightValidator(Protocol):
    def validate(
        self,
        snapshot: DocumentBundleSnapshotBinding,
        output: DocumentBundleOutputSpec,
    ) -> tuple[DocumentBundlePreflightIssue, ...]:
        """Validate one logical output against the same persisted snapshot."""


class DocumentBundleCrossPreflightValidator(Protocol):
    def validate(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> tuple[DocumentBundlePreflightIssue, ...]:
        """Validate cross-cutting bundle requirements such as translations."""


@dataclass(slots=True)
class DocumentBundlePreflightService:
    output_validators: Mapping[str, DocumentBundleOutputPreflightValidator]
    cross_validators: tuple[DocumentBundleCrossPreflightValidator, ...] = ()

    def evaluate(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> DocumentBundlePreflightReport:
        issues: list[DocumentBundlePreflightIssue] = []

        for output in snapshot.request.output_specs:
            validator = self.output_validators.get(output.exporter_kind)
            if validator is None:
                issues.append(
                    DocumentBundlePreflightIssue(
                        code="output.validator_missing",
                        message=(
                            "No preflight validator is registered for "
                            f"{output.exporter_kind!r}"
                        ),
                        category=DocumentBundlePreflightCategory.CONFIGURATION,
                        output_id=output.output_id,
                    )
                )
                continue
            issues.extend(validator.validate(snapshot, output))

        for cross_validator in self.cross_validators:
            issues.extend(cross_validator.validate(snapshot))

        draft_mark_required = False
        if snapshot.request.allow_drafts:
            normalized: list[DocumentBundlePreflightIssue] = []
            for issue in issues:
                if (
                    issue.category is DocumentBundlePreflightCategory.TRANSLATION
                    and issue.severity is DocumentBundlePreflightSeverity.ERROR
                ):
                    normalized.append(
                        replace(
                            issue,
                            severity=DocumentBundlePreflightSeverity.WARNING,
                        )
                    )
                    draft_mark_required = True
                else:
                    normalized.append(issue)
            issues = normalized

        return DocumentBundlePreflightReport(
            snapshot_id=snapshot.snapshot_id,
            issues=tuple(issues),
            draft_mark_required=draft_mark_required,
        )
