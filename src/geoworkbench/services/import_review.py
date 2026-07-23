from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    IndexRole,
    IndexType,
)
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis
from geoworkbench.services.semantic_channels import (
    SemanticChannelBinding,
    SemanticChannelDictionary,
    default_semantic_channel_dictionary,
)
from geoworkbench.services.uom_dictionary import QuantityClass


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
    index_valid_count: int = 0
    index_null_count: int = 0
    index_duplicate_count: int = 0
    index_gap_count: int = 0
    index_direction: str = "unknown"

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


@dataclass(frozen=True, slots=True)
class ImportChannelOverride:
    """One channel decision made in Import Review.

    Values are metadata decisions only. No engineering unit conversion is performed by
    Import Review: changing ``unit`` relabels the source values and is therefore recorded
    explicitly in the semantic binding evidence.
    """

    curve_id: str
    import_enabled: bool = True
    canonical_mnemonic: str | None = None
    canonical_kind: str | None = None
    quantity_class: QuantityClass | str | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        if not self.curve_id.strip():
            raise ValueError("Import Review override requires a curve ID")
        for field_name, value in (
            ("canonical_mnemonic", self.canonical_mnemonic),
            ("canonical_kind", self.canonical_kind),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string or None")
        quantity = self.quantity_class
        if quantity is not None and not isinstance(quantity, QuantityClass):
            try:
                quantity = QuantityClass(str(quantity))
            except ValueError as exc:
                raise ValueError(f"Unsupported quantity class: {self.quantity_class!r}") from exc
            object.__setattr__(self, "quantity_class", quantity)
        if self.unit is not None:
            object.__setattr__(self, "unit", self.unit.strip() or None)


@dataclass(frozen=True, slots=True)
class ImportReviewPlan:
    active_index_id: str
    index_mnemonic: str
    index_role: IndexRole | str
    index_type: IndexType | str
    index_unit: str | None
    channels: tuple[ImportChannelOverride, ...]
    null_value: float | None = None

    def __post_init__(self) -> None:
        if not self.active_index_id.strip():
            raise ValueError("Import Review requires an active index")
        if not self.index_mnemonic.strip():
            raise ValueError("Index mnemonic must not be empty")
        role = self.index_role
        if not isinstance(role, IndexRole):
            try:
                role = IndexRole(str(role))
            except ValueError as exc:
                raise ValueError(f"Unsupported index role: {self.index_role!r}") from exc
            object.__setattr__(self, "index_role", role)
        index_type = self.index_type
        if not isinstance(index_type, IndexType):
            try:
                index_type = IndexType(str(index_type))
            except ValueError as exc:
                raise ValueError(f"Unsupported index type: {self.index_type!r}") from exc
            object.__setattr__(self, "index_type", index_type)
        if self.index_unit is not None:
            object.__setattr__(self, "index_unit", self.index_unit.strip() or None)
        if self.null_value is not None:
            if isinstance(self.null_value, bool):
                raise ValueError("NULL sentinel must be a finite number")
            try:
                value = float(self.null_value)
            except (TypeError, ValueError) as exc:
                raise ValueError("NULL sentinel must be a finite number") from exc
            if not isfinite(value):
                raise ValueError("NULL sentinel must be a finite number")
            object.__setattr__(self, "null_value", value)
        if not all(isinstance(item, ImportChannelOverride) for item in self.channels):
            raise ValueError("Import Review channels must contain ImportChannelOverride values")
        ids = [item.curve_id for item in self.channels]
        if len(ids) != len(set(ids)):
            raise ValueError("Import Review contains duplicate curve overrides")


@dataclass(frozen=True, slots=True)
class ImportReviewCommit:
    dataset: Dataset
    review: DatasetImportReview


class ImportReviewValidationError(ValueError):
    def __init__(self, review: DatasetImportReview) -> None:
        self.review = review
        messages = [
            issue.message
            for issue in review.issues
            if issue.severity is ImportReviewSeverity.ERROR
        ]
        messages.extend(
            issue.message
            for channel in review.channels
            for issue in channel.issues
            if issue.severity is ImportReviewSeverity.ERROR
        )
        super().__init__("; ".join(messages) or "Import Review contains blocking errors")


class ImportReviewController:
    """Headless draft/preview/commit boundary for interactive import review.

    ``preview`` and ``commit`` always operate on a deep copy. The loader-owned dataset
    remains unchanged until the UI accepts a validated plan, and the project session is
    still untouched until the import job registers the returned copy.
    """

    def __init__(self, dictionary: SemanticChannelDictionary | None = None) -> None:
        self.dictionary = dictionary or default_semantic_channel_dictionary()

    def initial_plan(self, dataset: Dataset) -> ImportReviewPlan:
        index = dataset.active_index
        return ImportReviewPlan(
            active_index_id=index.index_id,
            index_mnemonic=index.mnemonic,
            index_role=index.role,
            index_type=index.index_type,
            index_unit=index.unit,
            channels=tuple(
                ImportChannelOverride(
                    curve_id=curve.metadata.curve_id,
                    canonical_mnemonic=(
                        curve.metadata.semantic.canonical_mnemonic
                        if curve.metadata.semantic is not None
                        else curve.metadata.canonical_mnemonic
                    ),
                    canonical_kind=(
                        curve.metadata.semantic.canonical_kind
                        if curve.metadata.semantic is not None
                        else None
                    ),
                    quantity_class=(
                        curve.metadata.semantic.quantity_class
                        if curve.metadata.semantic is not None
                        else None
                    ),
                    unit=curve.metadata.unit,
                )
                for curve in dataset.curves.values()
            ),
        )

    def preview(self, dataset: Dataset, plan: ImportReviewPlan) -> DatasetImportReview:
        candidate = self._apply(dataset, plan)
        return build_import_review(candidate, dictionary=self.dictionary)

    def commit(self, dataset: Dataset, plan: ImportReviewPlan) -> ImportReviewCommit:
        candidate = self._apply(dataset, plan)
        review = build_import_review(candidate, dictionary=self.dictionary)
        if review.error_count:
            raise ImportReviewValidationError(review)
        candidate.parameters["IMPORT_REVIEW_VERSION"] = "1"
        candidate.parameters["IMPORT_REVIEW_ACCEPTED"] = "true"
        if plan.null_value is not None:
            candidate.parameters["IMPORT_REVIEW_NULL_VALUE"] = f"{plan.null_value:g}"
        return ImportReviewCommit(candidate, review)

    def _apply(self, dataset: Dataset, plan: ImportReviewPlan) -> Dataset:
        if plan.active_index_id not in dataset.indexes:
            raise ValueError(f"Unknown active index: {plan.active_index_id}")
        override_by_id = {item.curve_id: item for item in plan.channels}
        unknown_ids = set(override_by_id).difference(dataset.curves)
        if unknown_ids:
            raise ValueError(
                "Import Review references unknown curves: " + ", ".join(sorted(unknown_ids))
            )

        candidate = deepcopy(dataset)
        self._apply_null_sentinel(candidate, plan.null_value)
        selected_index = candidate.indexes[plan.active_index_id]
        selected_index.mnemonic = plan.index_mnemonic.strip()
        selected_index.role = plan.index_role
        selected_index.index_type = plan.index_type
        selected_index.unit = plan.index_unit
        selected_index.evidence = _unique(
            (*selected_index.evidence, "manual import review index confirmation")
        )
        candidate.set_active_index(plan.active_index_id)

        for curve_id in tuple(candidate.curves):
            override = override_by_id.get(curve_id)
            if override is not None and not override.import_enabled:
                del candidate.curves[curve_id]
                continue
            curve = candidate.curves[curve_id]
            curve.metadata = self._reviewed_metadata(curve.metadata, override)
        return candidate

    def _apply_null_sentinel(self, dataset: Dataset, sentinel: float | None) -> None:
        if sentinel is None:
            return
        for index in dataset.indexes.values():
            values = np.asarray(index.values)
            if np.issubdtype(values.dtype, np.floating):
                copied = values.astype(np.float64, copy=True)
                copied[copied == sentinel] = np.nan
                index.values = copied
            elif np.issubdtype(values.dtype, np.integer):
                copied = values.astype(np.float64)
                copied[copied == sentinel] = np.nan
                index.values = copied
        for curve in dataset.curves.values():
            values = np.asarray(curve.values, dtype=np.float64).copy()
            values[values == sentinel] = np.nan
            curve.values = values

    def _reviewed_metadata(
        self,
        metadata: CurveMetadata,
        override: ImportChannelOverride | None,
    ) -> CurveMetadata:
        unit = metadata.unit if override is None else override.unit
        canonical_hint = (
            metadata.canonical_mnemonic
            if override is None or override.canonical_mnemonic is None
            else override.canonical_mnemonic
        )
        automatic = self.dictionary.resolve(
            metadata.original_mnemonic,
            description=metadata.description or "",
            unit=unit or "",
            source_mnemonic=(
                metadata.semantic.source_mnemonic
                if metadata.semantic is not None
                else metadata.original_mnemonic
            ),
            canonical_mnemonic=canonical_hint,
        )
        current = metadata.semantic or automatic
        if override is None or _override_matches(current, metadata, override):
            binding = current
        else:
            binding = _manual_binding(self.dictionary, metadata, automatic, override, unit)
        return replace(
            metadata,
            canonical_mnemonic=binding.canonical_mnemonic,
            unit=unit,
            semantic=binding,
        )


def build_import_review(
    dataset: Dataset,
    *,
    dictionary: SemanticChannelDictionary | None = None,
) -> DatasetImportReview:
    """Build a deterministic, read-only review model for a loaded dataset."""

    resolver = dictionary or default_semantic_channel_dictionary()
    active_index = dataset.active_index
    dataset_issues: list[ImportReviewIssue] = []
    index_values = np.asarray(active_index.values)
    index_valid_count, index_null_count = _valid_and_null_counts(index_values)
    if index_values.size == 0:
        dataset_issues.append(
            ImportReviewIssue("empty-index", ImportReviewSeverity.ERROR, "Index contains no rows")
        )
    if index_null_count:
        dataset_issues.append(
            ImportReviewIssue(
                "null-index-values",
                ImportReviewSeverity.ERROR,
                f"Index contains missing values: {index_null_count}",
            )
        )
    if active_index.unit is None:
        dataset_issues.append(
            ImportReviewIssue(
                "missing-index-uom",
                ImportReviewSeverity.WARNING,
                "Index unit is not specified",
            )
        )
    _append_index_contract_issues(dataset_issues, active_index.role, active_index.index_type)

    duplicate_count = 0
    gap_count = 0
    direction = DepthDirection.UNKNOWN.value
    if np.issubdtype(index_values.dtype, np.number):
        axis = analyze_depth_axis(np.asarray(index_values, dtype=np.float64))
        duplicate_count = axis.duplicate_count
        gap_count = axis.gap_count
        direction = axis.direction.value
        if duplicate_count:
            dataset_issues.append(
                ImportReviewIssue(
                    "duplicate-index-values",
                    ImportReviewSeverity.WARNING,
                    f"Index contains duplicate values: {duplicate_count}",
                )
            )
        if gap_count:
            dataset_issues.append(
                ImportReviewIssue(
                    "index-gaps",
                    ImportReviewSeverity.WARNING,
                    f"Index contains gaps: {gap_count}",
                )
            )
        if axis.direction is DepthDirection.MIXED:
            dataset_issues.append(
                ImportReviewIssue(
                    "out-of-order-index",
                    ImportReviewSeverity.ERROR,
                    "Index values are out of order",
                )
            )
        elif axis.direction is DepthDirection.DESCENDING:
            dataset_issues.append(
                ImportReviewIssue(
                    "descending-index",
                    ImportReviewSeverity.WARNING,
                    "Index values are descending",
                )
            )
        elif axis.direction is DepthDirection.CONSTANT:
            dataset_issues.append(
                ImportReviewIssue(
                    "constant-index",
                    ImportReviewSeverity.ERROR,
                    "Index contains only one repeated value",
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

    if not rows:
        dataset_issues.append(
            ImportReviewIssue(
                "no-imported-channels",
                ImportReviewSeverity.ERROR,
                "At least one data channel must be imported",
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
        index_valid_count=index_valid_count,
        index_null_count=index_null_count,
        index_duplicate_count=duplicate_count,
        index_gap_count=gap_count,
        index_direction=direction,
    )



def _override_matches(
    binding: SemanticChannelBinding,
    metadata: CurveMetadata,
    override: ImportChannelOverride,
) -> bool:
    return (
        override.import_enabled
        and (override.canonical_mnemonic or binding.canonical_mnemonic).strip().upper()
        == binding.canonical_mnemonic
        and (override.canonical_kind or binding.canonical_kind).strip().casefold()
        == binding.canonical_kind
        and (override.quantity_class or binding.quantity_class) is binding.quantity_class
        and override.unit == metadata.unit
    )

def _manual_binding(
    dictionary: SemanticChannelDictionary,
    metadata: CurveMetadata,
    automatic: SemanticChannelBinding,
    override: ImportChannelOverride,
    unit: str | None,
) -> SemanticChannelBinding:
    canonical_mnemonic = (
        override.canonical_mnemonic or automatic.canonical_mnemonic
    ).strip().upper()
    canonical_kind = (override.canonical_kind or automatic.canonical_kind).strip().casefold()
    quantity = override.quantity_class or automatic.quantity_class
    uom = dictionary.uoms.resolve(unit)
    evidence = [
        "manual import review override",
        f"automatic match={automatic.matched_by}",
    ]
    if unit != metadata.unit:
        evidence.append(
            "source UOM relabelled from "
            f"{metadata.unit or '<empty>'} to {unit or '<empty>'}"
        )
    if uom.recognized and quantity is not QuantityClass.UNKNOWN:
        if uom.quantity_class is not quantity:
            evidence.append(
                "source UOM quantity conflicts with manual quantity: "
                f"{unit} vs {quantity.value}"
            )
    elif unit:
        evidence.append(f"unrecognized source UOM: {unit}")
    manual_semantics = (
        canonical_kind != automatic.canonical_kind
        or quantity is not automatic.quantity_class
    )
    category = canonical_kind.partition(".")[0] or "manual"
    return SemanticChannelBinding(
        canonical_kind=canonical_kind,
        canonical_mnemonic=canonical_mnemonic,
        quantity_class=quantity,
        canonical_uom=(uom.canonical if uom.recognized else unit) or None,
        source_uom=unit or None,
        aliases=_unique((canonical_mnemonic, *automatic.aliases, metadata.original_mnemonic)),
        sensor_id=None if manual_semantics else automatic.sensor_id,
        source="import-review" if manual_semantics else automatic.source,
        family="manual" if manual_semantics else automatic.family,
        category=category if manual_semantics else automatic.category,
        source_mnemonic=(
            metadata.semantic.source_mnemonic
            if metadata.semantic is not None
            else metadata.original_mnemonic
        ),
        confidence=1.0,
        matched_by="manual_import_review",
        evidence=_unique(evidence),
    )


def _append_index_contract_issues(
    issues: list[ImportReviewIssue], role: IndexRole, index_type: IndexType
) -> None:
    compatible = {
        IndexRole.DEPTH: {IndexType.MD, IndexType.TVD, IndexType.TVDSS},
        IndexRole.TIME: {IndexType.RELATIVE_TIME, IndexType.DATETIME},
        IndexRole.GENERIC: {IndexType.GENERIC},
    }
    if index_type not in compatible[role]:
        issues.append(
            ImportReviewIssue(
                "index-role-type-conflict",
                ImportReviewSeverity.ERROR,
                f"Index role {role.value} is incompatible with type {index_type.value}",
            )
        )


def _valid_and_null_counts(values: np.ndarray) -> tuple[int, int]:
    if np.issubdtype(values.dtype, np.datetime64):
        valid = int(np.count_nonzero(~np.isnat(values)))
    elif np.issubdtype(values.dtype, np.number):
        valid = int(np.count_nonzero(np.isfinite(values.astype(np.float64))))
    else:
        valid = sum(bool(value is not None and str(value).strip()) for value in values.tolist())
    return valid, int(values.size - valid)


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


def _unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return tuple(result)
