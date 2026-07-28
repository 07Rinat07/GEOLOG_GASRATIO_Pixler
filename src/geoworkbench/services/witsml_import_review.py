from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from math import isfinite

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    new_id,
)
from geoworkbench.importers.witsml import (
    WitsmlChannelSetData,
    WitsmlChannelSpec,
    WitsmlDataSeverity,
    WitsmlIndexSpec,
    parse_witsml_utc_datetime,
)
from geoworkbench.services.semantic_channels import (
    SemanticChannelBinding,
    SemanticChannelDictionary,
    default_semantic_channel_dictionary,
)
from geoworkbench.services.uom_dictionary import QuantityClass, UomDictionary, default_uom_dictionary


WITSML_IMPORT_REVIEW_VERSION = 1


class WitsmlImportSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WitsmlImportIssue:
    code: str
    severity: WitsmlImportSeverity
    message: str
    channel_key: str | None = None


@dataclass(frozen=True, slots=True)
class WitsmlChannelOverride:
    channel_key: str
    import_enabled: bool = True
    canonical_mnemonic: str | None = None
    canonical_kind: str | None = None
    quantity_class: QuantityClass | str | None = None
    canonical_uom: str | None = None

    def __post_init__(self) -> None:
        if not self.channel_key.strip():
            raise ValueError("channel_key must be non-empty")
        for name in ("canonical_mnemonic", "canonical_kind", "canonical_uom"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, value.strip() or None)
        if self.quantity_class is not None and not isinstance(self.quantity_class, QuantityClass):
            object.__setattr__(self, "quantity_class", QuantityClass(str(self.quantity_class)))


@dataclass(frozen=True, slots=True)
class WitsmlImportReviewPlan:
    dataset_id: str
    dataset_name: str
    dataset_kind: DatasetKind | str
    active_index_key: str
    index_mnemonic: str
    index_type: IndexType | str
    index_role: IndexRole | str
    index_uom: str | None
    channels: tuple[WitsmlChannelOverride, ...]
    sort_by_index: bool = False
    drop_invalid_index_rows: bool = True

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.dataset_name.strip():
            raise ValueError("dataset_id and dataset_name must be non-empty")
        if not self.active_index_key.strip() or not self.index_mnemonic.strip():
            raise ValueError("active index selection is required")
        if not isinstance(self.dataset_kind, DatasetKind):
            object.__setattr__(self, "dataset_kind", DatasetKind(str(self.dataset_kind)))
        if not isinstance(self.index_type, IndexType):
            object.__setattr__(self, "index_type", IndexType(str(self.index_type)))
        if not isinstance(self.index_role, IndexRole):
            object.__setattr__(self, "index_role", IndexRole(str(self.index_role)))
        if self.index_uom is not None:
            object.__setattr__(self, "index_uom", self.index_uom.strip() or None)
        if not all(isinstance(item, WitsmlChannelOverride) for item in self.channels):
            raise ValueError("channels must contain WitsmlChannelOverride values")
        keys = [item.channel_key for item in self.channels]
        if len(keys) != len(set(keys)):
            raise ValueError("channel overrides must be unique")


@dataclass(frozen=True, slots=True)
class WitsmlChannelReview:
    channel_key: str
    mnemonic: str
    data_type: str
    source_uom: str | None
    canonical_mnemonic: str
    canonical_kind: str
    quantity_class: QuantityClass
    canonical_uom: str | None
    import_enabled: bool
    valid_count: int
    null_count: int
    invalid_count: int
    conversion_required: bool
    issues: tuple[WitsmlImportIssue, ...]


@dataclass(frozen=True, slots=True)
class WitsmlImportReview:
    channel_set_key: str
    dataset_id: str
    dataset_name: str
    row_count: int
    import_row_count: int
    skipped_row_count: int
    active_index_key: str
    index_mnemonic: str
    index_type: IndexType
    index_role: IndexRole
    index_uom: str | None
    channels: tuple[WitsmlChannelReview, ...]
    issues: tuple[WitsmlImportIssue, ...]

    @property
    def warning_count(self) -> int:
        return sum(item.severity is WitsmlImportSeverity.WARNING for item in self.issues) + sum(
            issue.severity is WitsmlImportSeverity.WARNING
            for channel in self.channels
            for issue in channel.issues
        )

    @property
    def error_count(self) -> int:
        return sum(item.severity is WitsmlImportSeverity.ERROR for item in self.issues) + sum(
            issue.severity is WitsmlImportSeverity.ERROR
            for channel in self.channels
            for issue in channel.issues
        )


@dataclass(frozen=True, slots=True)
class WitsmlImportCommit:
    dataset: Dataset
    review: WitsmlImportReview
    dataset_digest: str
    source_sha256: str
    data_sha256: str


class WitsmlImportValidationError(ValueError):
    def __init__(self, review: WitsmlImportReview) -> None:
        self.review = review
        messages = [item.message for item in review.issues if item.severity is WitsmlImportSeverity.ERROR]
        messages.extend(
            item.message
            for channel in review.channels
            for item in channel.issues
            if item.severity is WitsmlImportSeverity.ERROR
        )
        super().__init__("; ".join(messages) or "WITSML Import Review has blocking errors")


class WitsmlImportReviewController:
    """Immutable preview/commit boundary for WITSML ChannelSet bulk data."""

    def __init__(
        self,
        dictionary: SemanticChannelDictionary | None = None,
        uoms: UomDictionary | None = None,
    ) -> None:
        self.dictionary = dictionary or default_semantic_channel_dictionary()
        self.uoms = uoms or default_uom_dictionary()

    def initial_plan(self, channel_set: WitsmlChannelSetData) -> WitsmlImportReviewPlan:
        if not channel_set.indexes:
            raise ValueError("ChannelSet has no indexes")
        index = channel_set.indexes[0]
        index_type, index_role = _index_contract(index)
        index_uom = None if index_type is IndexType.DATETIME else _canonical_or_source(self.uoms, index.uom)
        channel_overrides: list[WitsmlChannelOverride] = []
        for channel in channel_set.channels:
            binding = self.dictionary.resolve(
                channel.mnemonic,
                description=" ".join(filter(None, (channel.title, channel.description, channel.channel_class))),
                unit=channel.uom or "",
            )
            source_uom = _canonical_or_source(self.uoms, channel.uom)
            target_uom = binding.canonical_uom or source_uom
            # Some legacy sensor-catalog entries use a customary display unit whose
            # quantity classification is not safely convertible (for example WOB in
            # tonnes versus a WITSML force channel in kN). Preserve the source unit
            # rather than silently relabel or guess a gravity-based conversion.
            if self.uoms.conversion(channel.uom, target_uom) is None:
                target_uom = source_uom
            channel_overrides.append(
                WitsmlChannelOverride(
                    channel_key=channel.key,
                    import_enabled=channel.is_scalar_numeric,
                    canonical_mnemonic=binding.canonical_mnemonic,
                    canonical_kind=binding.canonical_kind,
                    quantity_class=binding.quantity_class,
                    canonical_uom=target_uom,
                )
            )
        return WitsmlImportReviewPlan(
            dataset_id=new_id(),
            dataset_name=channel_set.title,
            dataset_kind=DatasetKind.GTI,
            active_index_key=index.key,
            index_mnemonic=index.mnemonic,
            index_type=index_type,
            index_role=index_role,
            index_uom=index_uom,
            channels=tuple(channel_overrides),
            sort_by_index=(index.direction or "").casefold() == "decreasing",
        )

    def plan_for_index(
        self,
        channel_set: WitsmlChannelSetData,
        plan: WitsmlImportReviewPlan,
        index_key: str,
    ) -> WitsmlImportReviewPlan:
        index = _index_by_key(channel_set, index_key)
        index_type, index_role = _index_contract(index)
        return WitsmlImportReviewPlan(
            dataset_id=plan.dataset_id,
            dataset_name=plan.dataset_name,
            dataset_kind=plan.dataset_kind,
            active_index_key=index.key,
            index_mnemonic=index.mnemonic,
            index_type=index_type,
            index_role=index_role,
            index_uom=None if index_type is IndexType.DATETIME else _canonical_or_source(self.uoms, index.uom),
            channels=plan.channels,
            sort_by_index=(index.direction or "").casefold() == "decreasing",
            drop_invalid_index_rows=plan.drop_invalid_index_rows,
        )

    def preview(
        self,
        channel_set: WitsmlChannelSetData,
        plan: WitsmlImportReviewPlan,
    ) -> WitsmlImportReview:
        index = _index_by_key(channel_set, plan.active_index_key)
        override_by_key = {item.channel_key: item for item in plan.channels}
        unknown = set(override_by_key).difference(item.key for item in channel_set.channels)
        if unknown:
            raise ValueError(f"Unknown WITSML channel overrides: {sorted(unknown)}")

        issues: list[WitsmlImportIssue] = []
        for issue in channel_set.issues:
            severity = {
                WitsmlDataSeverity.INFO: WitsmlImportSeverity.INFO,
                WitsmlDataSeverity.WARNING: WitsmlImportSeverity.WARNING,
                WitsmlDataSeverity.ERROR: WitsmlImportSeverity.WARNING,
            }[issue.severity]
            issues.append(WitsmlImportIssue(f"source:{issue.code}", severity, issue.message, issue.channel_key))

        index_values, valid_mask = _index_values(channel_set, index)
        invalid_count = int(np.size(valid_mask) - np.count_nonzero(valid_mask))
        if invalid_count:
            severity = WitsmlImportSeverity.WARNING if plan.drop_invalid_index_rows else WitsmlImportSeverity.ERROR
            issues.append(
                WitsmlImportIssue(
                    "invalid-index-rows",
                    severity,
                    f"{invalid_count} rows have no valid value for index {index.mnemonic}",
                )
            )
        imported_index = index_values[valid_mask] if plan.drop_invalid_index_rows else index_values
        if imported_index.size == 0:
            issues.append(WitsmlImportIssue("empty-index", WitsmlImportSeverity.ERROR, "No rows remain for import"))
        if plan.index_role is not _index_contract(index)[1]:
            issues.append(WitsmlImportIssue("index-role-conflict", WitsmlImportSeverity.ERROR, "Selected index role conflicts with WITSML metadata"))
        if plan.index_type is not _index_contract(index)[0]:
            issues.append(WitsmlImportIssue("index-type-conflict", WitsmlImportSeverity.ERROR, "Selected index type conflicts with WITSML metadata"))
        if plan.index_type is not IndexType.DATETIME:
            conversion = self.uoms.conversion(index.uom, plan.index_uom)
            if conversion is None:
                issues.append(
                    WitsmlImportIssue(
                        "index-uom-conversion",
                        WitsmlImportSeverity.ERROR,
                        f"Unsupported index UOM conversion: {index.uom or '<empty>'} -> {plan.index_uom or '<empty>'}",
                    )
                )
        if imported_index.size and _has_duplicates(imported_index):
            issues.append(WitsmlImportIssue("duplicate-index", WitsmlImportSeverity.WARNING, "Selected index contains duplicate values"))
        if imported_index.size and _requires_sort(imported_index) and not plan.sort_by_index:
            issues.append(WitsmlImportIssue("unsorted-index", WitsmlImportSeverity.WARNING, "Selected index is not monotonic; enable sorting for predictable display"))

        channel_reviews: list[WitsmlChannelReview] = []
        canonical_mnemonics: dict[str, str] = {}
        canonical_kinds: dict[str, str] = {}
        for channel in channel_set.channels:
            override = override_by_key.get(channel.key) or WitsmlChannelOverride(channel.key, import_enabled=False)
            binding = self.dictionary.resolve(
                channel.mnemonic,
                description=" ".join(filter(None, (channel.title, channel.description, channel.channel_class))),
                unit=channel.uom or "",
                canonical_mnemonic=override.canonical_mnemonic,
            )
            canonical_mnemonic = (override.canonical_mnemonic or binding.canonical_mnemonic).strip().upper()
            canonical_kind = (override.canonical_kind or binding.canonical_kind).strip().casefold()
            quantity = override.quantity_class or binding.quantity_class
            target_uom = override.canonical_uom or binding.canonical_uom or _canonical_or_source(self.uoms, channel.uom)
            values = [row.channel_values[channel.position] for row in channel_set.rows]
            valid_count = sum(_finite_number(value) for value in values)
            null_count = sum(value is None for value in values)
            invalid_value_count = len(values) - valid_count - null_count
            channel_issues: list[WitsmlImportIssue] = []
            conversion_required = _canonical_or_source(self.uoms, channel.uom) != _canonical_or_source(self.uoms, target_uom)

            if override.import_enabled and not channel.is_scalar_numeric:
                channel_issues.append(
                    WitsmlImportIssue(
                        "unsupported-channel-type",
                        WitsmlImportSeverity.ERROR,
                        f"Channel {channel.mnemonic} uses unsupported type {channel.data_type} or point metadata",
                        channel.key,
                    )
                )
            if override.import_enabled and valid_count == 0:
                channel_issues.append(
                    WitsmlImportIssue(
                        "all-null-channel",
                        WitsmlImportSeverity.WARNING,
                        f"Channel {channel.mnemonic} has no finite scalar values",
                        channel.key,
                    )
                )
            if override.import_enabled and invalid_value_count:
                channel_issues.append(
                    WitsmlImportIssue(
                        "invalid-channel-values",
                        WitsmlImportSeverity.WARNING,
                        f"Channel {channel.mnemonic} has {invalid_value_count} invalid values; they will become NULL",
                        channel.key,
                    )
                )
            if override.import_enabled:
                conversion = self.uoms.conversion(channel.uom, target_uom)
                if conversion is None:
                    channel_issues.append(
                        WitsmlImportIssue(
                            "channel-uom-conversion",
                            WitsmlImportSeverity.ERROR,
                            f"Unsupported UOM conversion for {channel.mnemonic}: {channel.uom or '<empty>'} -> {target_uom or '<empty>'}",
                            channel.key,
                        )
                    )
                source_resolution = self.uoms.resolve(channel.uom)
                target_resolution = self.uoms.resolve(target_uom)
                if quantity is not QuantityClass.UNKNOWN and target_resolution.recognized and target_resolution.quantity_class is not quantity:
                    channel_issues.append(
                        WitsmlImportIssue(
                            "quantity-uom-conflict",
                            WitsmlImportSeverity.ERROR,
                            f"Canonical UOM {target_uom} conflicts with quantity {quantity.value}",
                            channel.key,
                        )
                    )
                if channel.uom and not source_resolution.recognized:
                    channel_issues.append(
                        WitsmlImportIssue(
                            "unknown-source-uom",
                            WitsmlImportSeverity.WARNING,
                            f"Source UOM is not recognized: {channel.uom}",
                            channel.key,
                        )
                    )
                previous = canonical_mnemonics.get(canonical_mnemonic)
                if previous is not None:
                    channel_issues.append(
                        WitsmlImportIssue(
                            "duplicate-canonical-mnemonic",
                            WitsmlImportSeverity.ERROR,
                            f"Canonical mnemonic {canonical_mnemonic} is also used by {previous}",
                            channel.key,
                        )
                    )
                else:
                    canonical_mnemonics[canonical_mnemonic] = channel.mnemonic
                previous_kind = canonical_kinds.get(canonical_kind)
                if previous_kind is not None:
                    channel_issues.append(
                        WitsmlImportIssue(
                            "duplicate-canonical-kind",
                            WitsmlImportSeverity.ERROR,
                            f"Canonical kind {canonical_kind} is also used by {previous_kind}",
                            channel.key,
                        )
                    )
                else:
                    canonical_kinds[canonical_kind] = channel.mnemonic

            channel_reviews.append(
                WitsmlChannelReview(
                    channel_key=channel.key,
                    mnemonic=channel.mnemonic,
                    data_type=channel.data_type,
                    source_uom=channel.uom,
                    canonical_mnemonic=canonical_mnemonic,
                    canonical_kind=canonical_kind,
                    quantity_class=quantity,
                    canonical_uom=target_uom,
                    import_enabled=override.import_enabled,
                    valid_count=valid_count,
                    null_count=null_count,
                    invalid_count=invalid_value_count,
                    conversion_required=conversion_required,
                    issues=tuple(channel_issues),
                )
            )

        if not any(item.import_enabled for item in channel_reviews):
            issues.append(WitsmlImportIssue("no-channels", WitsmlImportSeverity.ERROR, "Select at least one numeric channel"))
        return WitsmlImportReview(
            channel_set_key=channel_set.key,
            dataset_id=plan.dataset_id,
            dataset_name=plan.dataset_name,
            row_count=len(channel_set.rows),
            import_row_count=int(np.count_nonzero(valid_mask)) if plan.drop_invalid_index_rows else len(channel_set.rows),
            skipped_row_count=invalid_count if plan.drop_invalid_index_rows else 0,
            active_index_key=index.key,
            index_mnemonic=plan.index_mnemonic,
            index_type=plan.index_type,
            index_role=plan.index_role,
            index_uom=plan.index_uom,
            channels=tuple(channel_reviews),
            issues=tuple(issues),
        )

    def commit(
        self,
        channel_set: WitsmlChannelSetData,
        plan: WitsmlImportReviewPlan,
    ) -> WitsmlImportCommit:
        review = self.preview(channel_set, plan)
        if review.error_count:
            raise WitsmlImportValidationError(review)
        index = _index_by_key(channel_set, plan.active_index_key)
        raw_index, valid_mask = _index_values(channel_set, index)
        mask = valid_mask if plan.drop_invalid_index_rows else np.ones(len(channel_set.rows), dtype=bool)
        index_values = raw_index[mask]
        if plan.index_type is IndexType.DATETIME:
            typed_index = np.array(index_values, dtype="datetime64[ns]")
            index_unit = None
            timezone_name = "UTC"
            datetime_format = "ISO8601"
        else:
            typed_index = self.uoms.convert_array(index_values.astype(np.float64), index.uom, plan.index_uom)
            index_unit = _canonical_or_source(self.uoms, plan.index_uom)
            timezone_name = None
            datetime_format = None
        order = np.arange(len(typed_index))
        if plan.sort_by_index and len(typed_index):
            order = np.argsort(typed_index, kind="stable")
            typed_index = typed_index[order]

        index_id = f"{plan.dataset_id}:witsml:{index.position}"
        dataset_index = DatasetIndex(
            index_id=index_id,
            mnemonic=plan.index_mnemonic,
            index_type=plan.index_type,
            role=plan.index_role,
            unit=index_unit,
            values=typed_index,
            confidence=1.0,
            evidence=(
                f"witsml-channel-set={channel_set.key}",
                f"witsml-index={index.key}",
                f"direction={index.direction or 'unspecified'}",
            ),
            datetime_format=datetime_format,
            timezone=timezone_name,
        )
        depth_domain = _depth_domain(plan.index_type)
        depth = typed_index.astype(np.float64) if plan.index_role is IndexRole.DEPTH else np.arange(len(typed_index), dtype=np.float64)
        dataset = Dataset(
            dataset_id=plan.dataset_id,
            name=plan.dataset_name,
            kind=plan.dataset_kind,
            depth_domain=depth_domain,
            depth=depth,
            source_path=channel_set.source,
            indexes={index_id: dataset_index},
            active_index_id=index_id,
        )
        dataset.headers.update(
            {
                "WELL": channel_set.wellbore_title or "",
                "WELLBORE_UUID": channel_set.wellbore_uuid or "",
                "WITSML_CHANNEL_SET": channel_set.title,
            }
        )
        dataset.parameters.update(
            {
                "WITSML_IMPORT_REVIEW_VERSION": str(WITSML_IMPORT_REVIEW_VERSION),
                "WITSML_SCHEMA_VERSION": channel_set.schema_version or "",
                "WITSML_SOURCE_FILE": channel_set.source_name,
                "WITSML_SOURCE_SHA256": channel_set.source_sha256,
                "WITSML_DATA_SHA256": channel_set.data_sha256,
                "WITSML_CHANNEL_SET_UUID": channel_set.uuid or "",
                "WITSML_CHANNEL_SET_KEY": channel_set.key,
                "WITSML_INDEX_KEY": index.key,
                "WITSML_DATA_LAYOUT": "[[indexes],[channels]]",
                "WITSML_TRANSPORT": (
                    "SOAP" if (channel_set.schema_version or "").startswith("1.4.1") else "OFFLINE"
                ),
                "WITSML_API_VERSION": (
                    "1.4.1.1" if (channel_set.schema_version or "").startswith("1.4.1") else ""
                ),
                "WITSML_ROWS_SOURCE": str(len(channel_set.rows)),
                "WITSML_ROWS_IMPORTED": str(review.import_row_count),
                "WITSML_ROWS_SKIPPED": str(review.skipped_row_count),
            }
        )

        override_by_key = {item.channel_key: item for item in plan.channels}
        review_by_key = {item.channel_key: item for item in review.channels}
        for channel in channel_set.channels:
            override = override_by_key[channel.key]
            if not override.import_enabled:
                continue
            channel_review = review_by_key[channel.key]
            values = np.array(
                [
                    float(value) if _finite_number(value) else np.nan
                    for value in (row.channel_values[channel.position] for row in channel_set.rows)
                ],
                dtype=np.float64,
            )[mask]
            values = self.uoms.convert_array(values, channel.uom, channel_review.canonical_uom)
            values = values[order]
            semantic = _semantic_binding(
                self.dictionary,
                channel,
                channel_review,
            )
            curve_id = channel.uuid or f"{plan.dataset_id}:witsml-channel:{channel.position}"
            metadata = CurveMetadata(
                curve_id=curve_id,
                original_mnemonic=channel.mnemonic,
                canonical_mnemonic=channel_review.canonical_mnemonic,
                unit=_canonical_or_source(self.uoms, channel_review.canonical_uom),
                description=channel.description or channel.title,
                source_dataset_id=plan.dataset_id,
                provenance=(
                    f"witsml:{channel_set.key};channel={channel.key};"
                    f"source-uom={channel.uom or ''};data-sha256={channel_set.data_sha256}"
                ),
                semantic=semantic,
            )
            dataset.curves[curve_id] = CurveData(metadata, values)
        dataset._validate_indexes()
        dataset_digest = _dataset_digest(dataset)
        dataset.parameters["WITSML_DATASET_DIGEST"] = dataset_digest
        return WitsmlImportCommit(
            dataset=dataset,
            review=review,
            dataset_digest=dataset_digest,
            source_sha256=channel_set.source_sha256,
            data_sha256=channel_set.data_sha256,
        )


def _index_by_key(channel_set: WitsmlChannelSetData, key: str) -> WitsmlIndexSpec:
    for item in channel_set.indexes:
        if item.key == key:
            return item
    raise ValueError(f"Unknown WITSML index: {key}")


def _index_contract(index: WitsmlIndexSpec) -> tuple[IndexType, IndexRole]:
    token = f"{index.index_type} {index.mnemonic}".casefold()
    if index.is_time:
        return IndexType.DATETIME, IndexRole.TIME
    if "tvdss" in token or "subsea" in token:
        return IndexType.TVDSS, IndexRole.DEPTH
    if "tvd" in token or "vertical" in token:
        return IndexType.TVD, IndexRole.DEPTH
    if index.is_depth:
        return IndexType.MD, IndexRole.DEPTH
    return IndexType.GENERIC, IndexRole.GENERIC


def _index_values(
    channel_set: WitsmlChannelSetData,
    index: WitsmlIndexSpec,
) -> tuple[np.ndarray, np.ndarray]:
    raw = [row.index_values[index.position] for row in channel_set.rows]
    if index.is_time:
        values: list[np.datetime64] = []
        valid: list[bool] = []
        for value in raw:
            try:
                parsed = parse_witsml_utc_datetime(str(value)) if value is not None else None
            except ValueError:
                parsed = None
            if parsed is None:
                values.append(np.datetime64("NaT", "ns"))
                valid.append(False)
            else:
                values.append(np.datetime64(parsed.replace(tzinfo=None), "ns"))
                valid.append(True)
        return np.array(values, dtype="datetime64[ns]"), np.array(valid, dtype=bool)
    values = np.array([float(value) if _finite_number(value) else np.nan for value in raw], dtype=np.float64)
    return values, np.isfinite(values)


def _canonical_or_source(uoms: UomDictionary, value: str | None) -> str | None:
    resolution = uoms.resolve(value)
    return resolution.canonical if resolution.recognized else ((value or "").strip() or None)


def _semantic_binding(
    dictionary: SemanticChannelDictionary,
    channel: WitsmlChannelSpec,
    review: WitsmlChannelReview,
) -> SemanticChannelBinding:
    automatic = dictionary.resolve(
        channel.mnemonic,
        description=" ".join(filter(None, (channel.title, channel.description, channel.channel_class))),
        unit=channel.uom or "",
        canonical_mnemonic=review.canonical_mnemonic,
    )
    evidence = tuple(
        dict.fromkeys(
            (
                *automatic.evidence,
                "WITSML 2.x ChannelSet Import Review",
                f"channel-key={channel.key}",
                f"source-uom={channel.uom or '<empty>'}",
                f"canonical-uom={review.canonical_uom or '<empty>'}",
            )
        )
    )
    return SemanticChannelBinding(
        canonical_kind=review.canonical_kind,
        canonical_mnemonic=review.canonical_mnemonic,
        quantity_class=review.quantity_class,
        canonical_uom=review.canonical_uom,
        source_uom=channel.uom,
        aliases=tuple(dict.fromkeys((review.canonical_mnemonic, channel.mnemonic, *automatic.aliases))),
        sensor_id=automatic.sensor_id,
        source=automatic.source or "WITSML",
        family=automatic.family,
        category=review.canonical_kind.partition(".")[0] or automatic.category,
        source_mnemonic=channel.mnemonic,
        confidence=max(automatic.confidence, 0.8 if automatic.sensor_id else 0.5),
        matched_by="witsml_import_review",
        evidence=evidence,
    )


def _depth_domain(index_type: IndexType) -> DepthDomain:
    return {
        IndexType.TVD: DepthDomain.TVD,
        IndexType.TVDSS: DepthDomain.TVDSS,
        IndexType.DATETIME: DepthDomain.TIME,
        IndexType.RELATIVE_TIME: DepthDomain.TIME,
    }.get(index_type, DepthDomain.MD)


def _finite_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and isfinite(float(value))


def _has_duplicates(values: np.ndarray) -> bool:
    if values.size < 2:
        return False
    return len(np.unique(values)) != len(values)


def _requires_sort(values: np.ndarray) -> bool:
    if values.size < 2:
        return False
    return bool(np.any(values[1:] < values[:-1]))


def _dataset_digest(dataset: Dataset) -> str:
    digest = sha256()
    metadata = {
        "datasetId": dataset.dataset_id,
        "name": dataset.name,
        "kind": dataset.kind.value,
        "depthDomain": dataset.depth_domain.value,
        "activeIndexId": dataset.active_index_id,
        "indexes": [
            {
                "id": item.index_id,
                "mnemonic": item.mnemonic,
                "type": item.index_type.value,
                "role": item.role.value,
                "unit": item.unit,
                "timezone": item.timezone,
            }
            for item in dataset.indexes.values()
        ],
        "curves": [
            {
                "id": item.metadata.curve_id,
                "original": item.metadata.original_mnemonic,
                "canonical": item.metadata.canonical_mnemonic,
                "unit": item.metadata.unit,
            }
            for item in dataset.curves.values()
        ],
    }
    digest.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    for item in dataset.indexes.values():
        digest.update(np.asarray(item.values).tobytes(order="C"))
    for item in dataset.curves.values():
        digest.update(np.asarray(item.values, dtype=np.float64).tobytes(order="C"))
    return digest.hexdigest()
