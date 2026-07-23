from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.services.semantic_channels import (
    SemanticChannelBinding,
    SemanticChannelDictionary,
    default_semantic_channel_dictionary,
)


class ImportReviewSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ImportReviewIssue:
    code: str
    severity: ImportReviewSeverity
    message: str


@dataclass(frozen=True, slots=True)
class ImportChannelReview:
    curve_id: str
    original_mnemonic: str
    canonical_mnemonic: str
    canonical_kind: str
    quantity_class: str
    source_uom: str | None
    canonical_uom: str | None
    sensor_id: str | None
    source: str | None
    confidence: float
    valid_count: int
    null_count: int
    issues: tuple[ImportReviewIssue, ...]


@dataclass(frozen=True, slots=True)
class DatasetImportReview:
    dataset_id: str
    index_mnemonic: str
    index_role: str
    index_type: str
    index_uom: str | None
    row_count: int
    channels: tuple[ImportChannelReview, ...]
    issues: tuple[ImportReviewIssue, ...]

    @property
    def warning_count(self) -> int:
        return sum(
            issue.severity is ImportReviewSeverity.WARNING
            for issue in self.issues
        ) + sum(
            issue.severity is ImportReviewSeverity.WARNING
            for channel in self.channels
            for issue in channel.issues
        )

    @property
    def error_count(self) -> int:
        return sum(
            issue.severity is ImportReviewSeverity.ERROR
            for issue in self.issues
        ) + sum(
            issue.severity is ImportReviewSeverity.ERROR
            for channel in self.channels
            for issue in channel.issues
        )


def build_import_review(
    dataset: Dataset,
    *,
    dictionary: SemanticChannelDictionary | None = None,
) -> DatasetImportReview:
    """Build a deterministic, read-only review model for a loaded dataset.

    This is the headless contract for the future Import Review screen. It deliberately
    does not mutate curve metadata: UI acceptance/overrides will be a separate command
    boundary in the next vertical slice.
    """

    resolver = dictionary or default_semantic_channel_dictionary()
    active_index = dataset.active_index
    dataset_issues: list[ImportReviewIssue] = []
    index_values = np.asarray(active_index.values)
    if index_values.size == 0:
        dataset_issues.append(
            ImportReviewIssue("empty-index", ImportReviewSeverity.ERROR, "Index contains no rows")
        )
    if active_index.unit is None:
        dataset_issues.append(
            ImportReviewIssue(
                "missing-index-uom",
                ImportReviewSeverity.WARNING,
                "Index unit is not specified",
            )
        )

    rows: list[ImportChannelReview] = []
    canonical_kinds: dict[str, int] = {}
    for curve in dataset.curves.values():
        metadata = curve.metadata
        binding = metadata.semantic or resolver.resolve(
            metadata.original_mnemonic,
            description=metadata.description or "",
            unit=metadata.unit or "",
            canonical_mnemonic=metadata.canonical_mnemonic,
        )
        values = np.asarray(curve.values, dtype=np.float64)
        valid_count = int(np.count_nonzero(np.isfinite(values)))
        issues = _channel_issues(binding, metadata.unit, valid_count, values.size)
        canonical_kinds[binding.canonical_kind] = canonical_kinds.get(binding.canonical_kind, 0) + 1
        rows.append(
            ImportChannelReview(
                curve_id=metadata.curve_id,
                original_mnemonic=metadata.original_mnemonic,
                canonical_mnemonic=binding.canonical_mnemonic,
                canonical_kind=binding.canonical_kind,
                quantity_class=binding.quantity_class.value,
                source_uom=binding.source_uom,
                canonical_uom=binding.canonical_uom,
                sensor_id=binding.sensor_id,
                source=binding.source,
                confidence=binding.confidence,
                valid_count=valid_count,
                null_count=int(values.size - valid_count),
                issues=issues,
            )
        )

    duplicates = {
        kind
        for kind, count in canonical_kinds.items()
        if count > 1 and not kind.startswith("unknown.")
    }
    if duplicates:
        dataset_issues.append(
            ImportReviewIssue(
                "duplicate-canonical-kind",
                ImportReviewSeverity.WARNING,
                "Several source channels map to the same canonical kind: "
                + ", ".join(sorted(duplicates)),
            )
        )

    return DatasetImportReview(
        dataset_id=dataset.dataset_id,
        index_mnemonic=active_index.mnemonic,
        index_role=active_index.role.value,
        index_type=active_index.index_type.value,
        index_uom=active_index.unit,
        row_count=int(index_values.size),
        channels=tuple(rows),
        issues=tuple(dataset_issues),
    )


def _channel_issues(
    binding: SemanticChannelBinding,
    source_unit: str | None,
    valid_count: int,
    total_count: int,
) -> tuple[ImportReviewIssue, ...]:
    issues: list[ImportReviewIssue] = []
    if not binding.resolved:
        issues.append(
            ImportReviewIssue(
                "unresolved-semantic-channel",
                ImportReviewSeverity.WARNING,
                "Channel is not matched to the semantic dictionary",
            )
        )
    if not source_unit:
        issues.append(
            ImportReviewIssue(
                "missing-channel-uom",
                ImportReviewSeverity.WARNING,
                "Channel unit is not specified",
            )
        )
    for evidence in binding.evidence:
        if evidence.startswith("unrecognized source UOM"):
            issues.append(
                ImportReviewIssue("unknown-channel-uom", ImportReviewSeverity.WARNING, evidence)
            )
        elif evidence.startswith("source UOM quantity conflicts"):
            issues.append(
                ImportReviewIssue("channel-uom-conflict", ImportReviewSeverity.ERROR, evidence)
            )
    if total_count == 0 or valid_count == 0:
        issues.append(
            ImportReviewIssue(
                "all-null-channel",
                ImportReviewSeverity.WARNING,
                "Channel does not contain finite values",
            )
        )
    return tuple(issues)
