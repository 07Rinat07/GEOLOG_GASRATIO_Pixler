from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from math import isfinite
from typing import Iterable, Mapping

from geoworkbench.domain.acquisition import (
    AcquisitionCurveSchema,
    AcquisitionDatasetSchema,
    AcquisitionIndexSchema,
    AcquisitionSession,
)
from geoworkbench.domain.models import (
    CurveMetadata,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    new_id,
)
from geoworkbench.importers.etp12.models import (
    Etp12ChannelBatch,
    Etp12ChannelMetadata,
)
from geoworkbench.services.semantic_channels import (
    SemanticChannelBinding,
    SemanticChannelDictionary,
    default_semantic_channel_dictionary,
)
from geoworkbench.services.uom_dictionary import (
    QuantityClass,
    UomDictionary,
    default_uom_dictionary,
)
from geoworkbench.services.wits0_import_review import acquisition_schema_digest


ETP12_IMPORT_REVIEW_VERSION = 1
_NUMERIC_DATA_KINDS = {
    "byte",
    "short",
    "int",
    "integer",
    "long",
    "float",
    "double",
    "number",
    "decimal",
}


class Etp12ReviewSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Etp12ReviewIssue:
    code: str
    severity: Etp12ReviewSeverity
    message: str
    channel_uri: str | None = None


@dataclass(frozen=True, slots=True)
class Etp12DiscoveredChannel:
    channel_uri: str
    channel_id: int
    channel_name: str
    data_kind: str | None
    source_uom: str | None
    index_kind: str | None
    index_uom: str | None
    description: str | None
    observed_count: int
    valid_count: int
    null_count: int
    invalid_count: int
    numeric_min: float | None
    numeric_max: float | None
    samples: tuple[str, ...]

    @property
    def numeric(self) -> bool:
        token = (self.data_kind or "").strip().casefold()
        return not token or token in _NUMERIC_DATA_KINDS


@dataclass(frozen=True, slots=True)
class Etp12DiscoverySnapshot:
    subscription_id: str
    generation: int
    batch_count: int
    point_count: int
    channels: tuple[Etp12DiscoveredChannel, ...]
    fingerprint: str

    def channel(self, uri: str) -> Etp12DiscoveredChannel | None:
        return next((item for item in self.channels if item.channel_uri == uri), None)


@dataclass(slots=True)
class _MutableChannel:
    metadata: Etp12ChannelMetadata
    observed_count: int = 0
    valid_count: int = 0
    null_count: int = 0
    invalid_count: int = 0
    numeric_min: float | None = None
    numeric_max: float | None = None
    samples: list[str] | None = None

    def observe(self, value: object, *, max_samples: int) -> None:
        self.observed_count += 1
        if value is None:
            self.null_count += 1
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.invalid_count += 1
            rendered = str(value)
        else:
            numeric = float(value)
            if not isfinite(numeric):
                self.invalid_count += 1
                rendered = str(value)
            else:
                self.valid_count += 1
                self.numeric_min = numeric if self.numeric_min is None else min(self.numeric_min, numeric)
                self.numeric_max = numeric if self.numeric_max is None else max(self.numeric_max, numeric)
                rendered = format(numeric, ".12g")
        if self.samples is None:
            self.samples = []
        if rendered not in self.samples and len(self.samples) < max_samples:
            self.samples.append(rendered)

    def freeze(self) -> Etp12DiscoveredChannel:
        item = self.metadata
        return Etp12DiscoveredChannel(
            channel_uri=item.channel_uri,
            channel_id=item.channel_id,
            channel_name=item.channel_name,
            data_kind=item.data_kind,
            source_uom=item.uom,
            index_kind=item.index_kind,
            index_uom=item.index_uom,
            description=item.description,
            observed_count=self.observed_count,
            valid_count=self.valid_count,
            null_count=self.null_count,
            invalid_count=self.invalid_count,
            numeric_min=self.numeric_min,
            numeric_max=self.numeric_max,
            samples=tuple(self.samples or ()),
        )


class Etp12DiscoveryAccumulator:
    """Collect metadata and immutable sample statistics using channel URI identity.

    Numeric channel ids are session-local and may change after reconnect.  The
    discovery surface and all reviewed mappings are therefore keyed by URI.
    """

    def __init__(self, subscription_id: str = "", *, max_samples_per_channel: int = 5) -> None:
        if max_samples_per_channel < 1:
            raise ValueError("max_samples_per_channel must be positive")
        self.subscription_id = subscription_id.strip()
        self.max_samples_per_channel = max_samples_per_channel
        self.generation = 0
        self._channels: dict[str, _MutableChannel] = {}
        self._id_to_uri: dict[int, str] = {}
        self._batch_count = 0
        self._point_count = 0

    def reset(self) -> None:
        self.generation = 0
        self._channels.clear()
        self._id_to_uri.clear()
        self._batch_count = 0
        self._point_count = 0

    def update_metadata(
        self,
        metadata: Mapping[str, Etp12ChannelMetadata] | Iterable[Etp12ChannelMetadata],
        *,
        generation: int | None = None,
        subscription_id: str | None = None,
    ) -> None:
        values = metadata.values() if isinstance(metadata, Mapping) else metadata
        if subscription_id is not None:
            self.subscription_id = subscription_id.strip()
        if generation is not None:
            self.generation = max(self.generation, int(generation))
        for item in values:
            if not isinstance(item, Etp12ChannelMetadata):
                raise TypeError("metadata must contain Etp12ChannelMetadata")
            uri = item.channel_uri.strip()
            if not uri:
                raise ValueError("ETP channel metadata requires channel_uri")
            previous = self._channels.get(uri)
            if previous is None:
                self._channels[uri] = _MutableChannel(item)
            else:
                previous.metadata = item
            self._id_to_uri[item.channel_id] = uri

    def observe(self, batch: Etp12ChannelBatch) -> None:
        if self.subscription_id and batch.subscription_id != self.subscription_id:
            return
        if not self.subscription_id:
            self.subscription_id = batch.subscription_id
        self.generation = max(self.generation, batch.generation)
        for channel_id, mapped_uri in batch.channel_uris.items():
            self._id_to_uri[int(channel_id)] = str(mapped_uri)
        self._batch_count += 1
        self._point_count += len(batch.points)
        for point in batch.points:
            channel_uri = batch.channel_uris.get(point.channel_id) or self._id_to_uri.get(
                point.channel_id
            )
            if channel_uri is None:
                continue
            channel = self._channels.get(channel_uri)
            if channel is None:
                channel = _MutableChannel(
                    Etp12ChannelMetadata(
                        channel_id=point.channel_id,
                        channel_uri=channel_uri,
                        channel_name=channel_uri.rsplit("/", 1)[-1],
                        data_kind=None,
                        uom=None,
                        index_kind=None,
                        start_index=None,
                        end_index=None,
                    )
                )
                self._channels[channel_uri] = channel
            channel.observe(point.value, max_samples=self.max_samples_per_channel)

    def snapshot(self) -> Etp12DiscoverySnapshot:
        channels = tuple(self._channels[key].freeze() for key in sorted(self._channels))
        payload = {
            "version": ETP12_IMPORT_REVIEW_VERSION,
            "subscriptionId": self.subscription_id,
            "channels": [
                {
                    "uri": item.channel_uri,
                    "name": item.channel_name,
                    "dataKind": item.data_kind,
                    "uom": item.source_uom,
                    "indexKind": item.index_kind,
                    "indexUom": item.index_uom,
                }
                for item in channels
            ],
        }
        fingerprint = sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return Etp12DiscoverySnapshot(
            subscription_id=self.subscription_id,
            generation=self.generation,
            batch_count=self._batch_count,
            point_count=self._point_count,
            channels=channels,
            fingerprint=fingerprint,
        )


@dataclass(frozen=True, slots=True)
class Etp12ChannelOverride:
    channel_uri: str
    curve_id: str
    import_enabled: bool = True
    canonical_mnemonic: str | None = None
    canonical_kind: str | None = None
    quantity_class: QuantityClass | str | None = None
    source_uom: str | None = None
    canonical_uom: str | None = None

    def __post_init__(self) -> None:
        if not self.channel_uri.strip() or not self.curve_id.strip():
            raise ValueError("channel_uri and curve_id are required")
        if self.quantity_class is not None and not isinstance(self.quantity_class, QuantityClass):
            object.__setattr__(self, "quantity_class", QuantityClass(str(self.quantity_class)))
        for name in ("canonical_mnemonic", "canonical_kind", "source_uom", "canonical_uom"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, value.strip() or None)


@dataclass(frozen=True, slots=True)
class Etp12ImportReviewPlan:
    discovery_fingerprint: str
    dataset_id: str
    dataset_name: str
    dataset_kind: DatasetKind | str
    index_id: str
    index_mnemonic: str
    index_type: IndexType | str
    index_role: IndexRole | str
    index_source_uom: str | None
    index_canonical_uom: str | None
    timezone: str | None
    channels: tuple[Etp12ChannelOverride, ...]

    def __post_init__(self) -> None:
        if not self.discovery_fingerprint or len(self.discovery_fingerprint) != 64:
            raise ValueError("discovery_fingerprint must be a SHA-256 digest")
        for value, name in (
            (self.dataset_id, "dataset_id"),
            (self.dataset_name, "dataset_name"),
            (self.index_id, "index_id"),
            (self.index_mnemonic, "index_mnemonic"),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.dataset_kind, DatasetKind):
            object.__setattr__(self, "dataset_kind", DatasetKind(str(self.dataset_kind)))
        if not isinstance(self.index_type, IndexType):
            object.__setattr__(self, "index_type", IndexType(str(self.index_type)))
        if not isinstance(self.index_role, IndexRole):
            object.__setattr__(self, "index_role", IndexRole(str(self.index_role)))
        if len({item.channel_uri for item in self.channels}) != len(self.channels):
            raise ValueError("channel overrides must be unique")
        if len({item.curve_id for item in self.channels}) != len(self.channels):
            raise ValueError("curve ids must be unique")


@dataclass(frozen=True, slots=True)
class Etp12ChannelReview:
    channel_uri: str
    channel_name: str
    data_kind: str | None
    import_enabled: bool
    canonical_mnemonic: str
    canonical_kind: str
    quantity_class: QuantityClass
    source_uom: str | None
    canonical_uom: str | None
    conversion_required: bool
    observed_count: int
    valid_count: int
    null_count: int
    invalid_count: int
    samples: tuple[str, ...]
    issues: tuple[Etp12ReviewIssue, ...]


@dataclass(frozen=True, slots=True)
class Etp12ImportReview:
    discovery_fingerprint: str
    subscription_id: str
    index_type: IndexType
    index_role: IndexRole
    index_source_uom: str | None
    index_canonical_uom: str | None
    channels: tuple[Etp12ChannelReview, ...]
    issues: tuple[Etp12ReviewIssue, ...]
    schema_preview: AcquisitionDatasetSchema | None

    @property
    def error_count(self) -> int:
        return sum(item.severity is Etp12ReviewSeverity.ERROR for item in self.issues) + sum(
            issue.severity is Etp12ReviewSeverity.ERROR
            for channel in self.channels
            for issue in channel.issues
        )

    @property
    def warning_count(self) -> int:
        return sum(item.severity is Etp12ReviewSeverity.WARNING for item in self.issues) + sum(
            issue.severity is Etp12ReviewSeverity.WARNING
            for channel in self.channels
            for issue in channel.issues
        )


@dataclass(frozen=True, slots=True)
class Etp12ImportReviewCommit:
    review: Etp12ImportReview
    schema: AcquisitionDatasetSchema
    plan: Etp12ImportReviewPlan
    schema_digest: str

    def __post_init__(self) -> None:
        if self.review.schema_preview != self.schema:
            raise ValueError("Committed schema must equal reviewed schema preview")
        if acquisition_schema_digest(self.schema) != self.schema_digest:
            raise ValueError("schema_digest does not match committed schema")


class Etp12ImportReviewValidationError(ValueError):
    def __init__(self, review: Etp12ImportReview) -> None:
        self.review = review
        messages = [item.message for item in review.issues if item.severity is Etp12ReviewSeverity.ERROR]
        messages.extend(
            issue.message
            for channel in review.channels
            for issue in channel.issues
            if issue.severity is Etp12ReviewSeverity.ERROR
        )
        super().__init__("; ".join(messages) or "ETP Import Review contains blocking errors")


class Etp12ImportReviewController:
    def __init__(
        self,
        dictionary: SemanticChannelDictionary | None = None,
        uoms: UomDictionary | None = None,
    ) -> None:
        self.dictionary = dictionary or default_semantic_channel_dictionary()
        self.uoms = uoms or default_uom_dictionary()

    def initial_plan(self, snapshot: Etp12DiscoverySnapshot) -> Etp12ImportReviewPlan:
        if not snapshot.channels:
            raise ValueError("ETP discovery snapshot has no channels")
        index_type, index_role, source_index_uom, canonical_index_uom, mnemonic, timezone = (
            _index_contract(snapshot.channels)
        )
        overrides: list[Etp12ChannelOverride] = []
        for channel in snapshot.channels:
            binding = self.dictionary.resolve(
                channel.channel_name,
                description=channel.description or channel.channel_uri,
                unit=channel.source_uom or "",
                source_mnemonic=channel.channel_name,
            )
            source_uom = _canonical_or_source(self.uoms, channel.source_uom)
            canonical_uom = binding.canonical_uom or source_uom
            if self.uoms.conversion(source_uom, canonical_uom) is None:
                canonical_uom = source_uom
            overrides.append(
                Etp12ChannelOverride(
                    channel_uri=channel.channel_uri,
                    curve_id=new_id(),
                    import_enabled=channel.numeric,
                    canonical_mnemonic=binding.canonical_mnemonic,
                    canonical_kind=binding.canonical_kind,
                    quantity_class=binding.quantity_class,
                    source_uom=source_uom,
                    canonical_uom=canonical_uom,
                )
            )
        return Etp12ImportReviewPlan(
            discovery_fingerprint=snapshot.fingerprint,
            dataset_id=new_id(),
            dataset_name="ETP 1.2 Channel Stream",
            dataset_kind=DatasetKind.GTI,
            index_id=new_id(),
            index_mnemonic=mnemonic,
            index_type=index_type,
            index_role=index_role,
            index_source_uom=source_index_uom,
            index_canonical_uom=canonical_index_uom,
            timezone=timezone,
            channels=tuple(overrides),
        )

    def preview(
        self,
        snapshot: Etp12DiscoverySnapshot,
        plan: Etp12ImportReviewPlan,
    ) -> Etp12ImportReview:
        issues: list[Etp12ReviewIssue] = []
        dataset_kind = _dataset_kind(plan.dataset_kind)
        index_type = _index_type(plan.index_type)
        index_role = _index_role(plan.index_role)
        if plan.discovery_fingerprint != snapshot.fingerprint:
            issues.append(
                Etp12ReviewIssue(
                    "stale-discovery",
                    Etp12ReviewSeverity.ERROR,
                    "ETP channel metadata changed after this review plan was created",
                )
            )
        override_by_uri = {item.channel_uri: item for item in plan.channels}
        if set(override_by_uri) != {item.channel_uri for item in snapshot.channels}:
            issues.append(
                Etp12ReviewIssue(
                    "channel-set-mismatch",
                    Etp12ReviewSeverity.ERROR,
                    "Review plan does not cover exactly the discovered ETP channels",
                )
            )
        if index_type is IndexType.DATETIME and (plan.timezone or "").upper() != "UTC":
            issues.append(
                Etp12ReviewIssue(
                    "missing-utc-timezone",
                    Etp12ReviewSeverity.ERROR,
                    "ETP datetime index must be normalized to UTC",
                )
            )
        if index_type is not IndexType.DATETIME:
            if not _conversion_supported(self.uoms, plan.index_source_uom, plan.index_canonical_uom):
                issues.append(
                    Etp12ReviewIssue(
                        "index-uom-conversion",
                        Etp12ReviewSeverity.ERROR,
                        f"Unsupported index UOM conversion: {plan.index_source_uom} -> {plan.index_canonical_uom}",
                    )
                )
        rows: list[Etp12ChannelReview] = []
        enabled_mnemonics: dict[str, int] = {}
        enabled_count = 0
        for channel in snapshot.channels:
            override = override_by_uri.get(channel.channel_uri)
            if override is None:
                continue
            channel_issues: list[Etp12ReviewIssue] = []
            canonical_mnemonic = (override.canonical_mnemonic or channel.channel_name).strip().upper()
            automatic = self.dictionary.resolve(
                channel.channel_name,
                description=channel.description or channel.channel_uri,
                unit=override.source_uom or "",
                source_mnemonic=channel.channel_name,
                canonical_mnemonic=canonical_mnemonic,
            )
            quantity = _quantity_class(
                override.quantity_class,
                fallback=automatic.quantity_class,
            )
            canonical_kind = (override.canonical_kind or automatic.canonical_kind).strip().casefold()
            source_uom = override.source_uom
            canonical_uom = override.canonical_uom
            conversion = self.uoms.conversion(source_uom, canonical_uom)
            conversion_supported = _conversion_supported(self.uoms, source_uom, canonical_uom)
            if override.import_enabled:
                enabled_count += 1
                enabled_mnemonics[canonical_mnemonic] = enabled_mnemonics.get(canonical_mnemonic, 0) + 1
                if not channel.numeric:
                    channel_issues.append(
                        Etp12ReviewIssue(
                            "non-numeric-channel",
                            Etp12ReviewSeverity.ERROR,
                            "Acquisition Dataset supports scalar numeric ETP channels only",
                            channel.channel_uri,
                        )
                    )
                if not conversion_supported:
                    channel_issues.append(
                        Etp12ReviewIssue(
                            "uom-conversion-required",
                            Etp12ReviewSeverity.ERROR,
                            f"Unsupported UOM conversion: {source_uom} -> {canonical_uom}",
                            channel.channel_uri,
                        )
                    )
                elif (
                    quantity is not QuantityClass.UNKNOWN
                    and conversion is not None
                    and conversion.quantity_class is not quantity
                ):
                    channel_issues.append(
                        Etp12ReviewIssue(
                            "quantity-uom-conflict",
                            Etp12ReviewSeverity.ERROR,
                            f"Quantity class {quantity.value} conflicts with UOM {canonical_uom}",
                            channel.channel_uri,
                        )
                    )
                if channel.valid_count == 0 and channel.observed_count:
                    channel_issues.append(
                        Etp12ReviewIssue(
                            "no-valid-values",
                            Etp12ReviewSeverity.WARNING,
                            "Observed ETP channel has no valid numeric values",
                            channel.channel_uri,
                        )
                    )
            rows.append(
                Etp12ChannelReview(
                    channel_uri=channel.channel_uri,
                    channel_name=channel.channel_name,
                    data_kind=channel.data_kind,
                    import_enabled=override.import_enabled,
                    canonical_mnemonic=canonical_mnemonic,
                    canonical_kind=canonical_kind,
                    quantity_class=quantity,
                    source_uom=source_uom,
                    canonical_uom=canonical_uom,
                    conversion_required=(
                        conversion is not None and (conversion.scale != 1.0 or conversion.offset != 0.0)
                    ),
                    observed_count=channel.observed_count,
                    valid_count=channel.valid_count,
                    null_count=channel.null_count,
                    invalid_count=channel.invalid_count,
                    samples=channel.samples,
                    issues=tuple(channel_issues),
                )
            )
        if enabled_count == 0:
            issues.append(
                Etp12ReviewIssue(
                    "no-enabled-channels",
                    Etp12ReviewSeverity.ERROR,
                    "At least one scalar numeric ETP channel must be enabled",
                )
            )
        duplicates = sorted(key for key, count in enabled_mnemonics.items() if count > 1)
        if duplicates:
            issues.append(
                Etp12ReviewIssue(
                    "duplicate-canonical-mnemonic",
                    Etp12ReviewSeverity.ERROR,
                    "Enabled channels have duplicate canonical mnemonics: " + ", ".join(duplicates),
                )
            )
        schema = None
        if not _has_errors(issues, rows):
            schema = self._build_schema(
                snapshot,
                plan,
                rows,
                dataset_kind=dataset_kind,
                index_type=index_type,
                index_role=index_role,
            )
        return Etp12ImportReview(
            discovery_fingerprint=snapshot.fingerprint,
            subscription_id=snapshot.subscription_id,
            index_type=index_type,
            index_role=index_role,
            index_source_uom=plan.index_source_uom,
            index_canonical_uom=plan.index_canonical_uom,
            channels=tuple(rows),
            issues=tuple(issues),
            schema_preview=schema,
        )

    def commit(
        self,
        snapshot: Etp12DiscoverySnapshot,
        plan: Etp12ImportReviewPlan,
    ) -> Etp12ImportReviewCommit:
        review = self.preview(snapshot, plan)
        if review.error_count or review.schema_preview is None:
            raise Etp12ImportReviewValidationError(review)
        schema = review.schema_preview
        return Etp12ImportReviewCommit(
            review=review,
            schema=schema,
            plan=plan,
            schema_digest=acquisition_schema_digest(schema),
        )

    def _build_schema(
        self,
        snapshot: Etp12DiscoverySnapshot,
        plan: Etp12ImportReviewPlan,
        rows: list[Etp12ChannelReview],
        *,
        dataset_kind: DatasetKind,
        index_type: IndexType,
        index_role: IndexRole,
    ) -> AcquisitionDatasetSchema:
        index = AcquisitionIndexSchema(
            index_id=plan.index_id,
            mnemonic=plan.index_mnemonic,
            index_type=index_type,
            role=index_role,
            unit=plan.index_canonical_uom,
            confidence=1.0,
            evidence=("ETP ChannelMetadata index", f"subscription={snapshot.subscription_id}"),
            datetime_format="unix-ns" if index_type is IndexType.DATETIME else None,
            timezone=plan.timezone if index_type is IndexType.DATETIME else None,
        )
        depth_domain = {
            IndexType.MD: DepthDomain.MD,
            IndexType.TVD: DepthDomain.TVD,
            IndexType.TVDSS: DepthDomain.TVDSS,
            IndexType.DATETIME: DepthDomain.TIME,
            IndexType.RELATIVE_TIME: DepthDomain.TIME,
        }.get(index_type, DepthDomain.TIME)
        override_by_uri = {item.channel_uri: item for item in plan.channels}
        discovered_by_uri = {item.channel_uri: item for item in snapshot.channels}
        curves: list[AcquisitionCurveSchema] = []
        for row in rows:
            if not row.import_enabled:
                continue
            override = override_by_uri[row.channel_uri]
            discovered = discovered_by_uri[row.channel_uri]
            automatic = self.dictionary.resolve(
                discovered.channel_name,
                description=discovered.description or discovered.channel_uri,
                unit=row.source_uom or "",
                source_mnemonic=discovered.channel_name,
                canonical_mnemonic=row.canonical_mnemonic,
            )
            binding = SemanticChannelBinding(
                canonical_kind=row.canonical_kind,
                canonical_mnemonic=row.canonical_mnemonic,
                quantity_class=row.quantity_class,
                canonical_uom=row.canonical_uom,
                source_uom=row.source_uom,
                aliases=automatic.aliases,
                sensor_id=automatic.sensor_id,
                source=automatic.source,
                family=automatic.family,
                category=automatic.category,
                source_mnemonic=discovered.channel_name,
                confidence=automatic.confidence,
                matched_by=automatic.matched_by + "+etp12-review",
                evidence=(*automatic.evidence, f"ETP URI={row.channel_uri}"),
            )
            metadata = CurveMetadata(
                curve_id=override.curve_id,
                original_mnemonic=discovered.channel_name,
                canonical_mnemonic=row.canonical_mnemonic,
                unit=row.canonical_uom,
                description=discovered.description or discovered.channel_uri,
                source_dataset_id=plan.dataset_id,
                provenance=f"etp12:{row.channel_uri}",
                semantic=binding,
            )
            curves.append(AcquisitionCurveSchema(metadata))
        return AcquisitionDatasetSchema(
            dataset_id=plan.dataset_id,
            name=plan.dataset_name.strip(),
            kind=dataset_kind,
            depth_domain=depth_domain,
            indexes=(index,),
            active_index_id=index.index_id,
            curves=tuple(curves),
        )



def restore_etp12_import_review_commit(
    session: AcquisitionSession,
    snapshot: Etp12DiscoverySnapshot,
    *,
    controller: Etp12ImportReviewController | None = None,
) -> Etp12ImportReviewCommit:
    """Rebuild a reviewed runtime contract from a persisted ETP schema.

    Channel ids are intentionally ignored: a reconnect or application restart may
    assign new numeric ids while channel URIs and the immutable dataset schema stay
    stable.
    """

    schema = session.dataset_schema
    discovered = {item.channel_uri: item for item in snapshot.channels}
    overrides: list[Etp12ChannelOverride] = []
    for curve in schema.curves:
        provenance = curve.metadata.provenance
        if not provenance.startswith("etp12:"):
            raise ValueError("AcquisitionSession is not an ETP 1.2 session")
        uri = provenance.removeprefix("etp12:")
        channel = discovered.get(uri)
        if channel is None:
            raise ValueError(f"Persisted ETP channel is absent from current metadata: {uri}")
        semantic = curve.metadata.semantic
        overrides.append(
            Etp12ChannelOverride(
                channel_uri=uri,
                curve_id=curve.metadata.curve_id,
                import_enabled=True,
                canonical_mnemonic=curve.metadata.canonical_mnemonic
                or curve.metadata.original_mnemonic,
                canonical_kind=(semantic.canonical_kind if semantic is not None else None),
                quantity_class=(semantic.quantity_class if semantic is not None else None),
                source_uom=(semantic.source_uom if semantic is not None else channel.source_uom),
                canonical_uom=curve.metadata.unit,
            )
        )
    index = next(item for item in schema.indexes if item.index_id == schema.active_index_id)
    index_source_uom = next(
        (item.index_uom for item in snapshot.channels if item.index_uom),
        "us" if index.index_type is IndexType.DATETIME else index.unit,
    )
    plan = Etp12ImportReviewPlan(
        discovery_fingerprint=snapshot.fingerprint,
        dataset_id=schema.dataset_id,
        dataset_name=schema.name,
        dataset_kind=schema.kind,
        index_id=index.index_id,
        index_mnemonic=index.mnemonic,
        index_type=index.index_type,
        index_role=index.role,
        index_source_uom=index_source_uom,
        index_canonical_uom=index.unit,
        timezone=index.timezone,
        channels=tuple(overrides),
    )
    review_controller = controller or Etp12ImportReviewController()
    preview = review_controller.preview(snapshot, plan)
    if preview.error_count:
        raise Etp12ImportReviewValidationError(preview)
    review = replace(preview, schema_preview=schema)
    return Etp12ImportReviewCommit(
        review=review,
        schema=schema,
        plan=plan,
        schema_digest=acquisition_schema_digest(schema),
    )


def _index_contract(
    channels: tuple[Etp12DiscoveredChannel, ...],
) -> tuple[IndexType, IndexRole, str | None, str | None, str, str | None]:
    kinds = [item.index_kind for item in channels if item.index_kind]
    kind = kinds[0].casefold() if kinds else "datetime"
    uoms = [item.index_uom for item in channels if item.index_uom]
    source_uom = uoms[0] if uoms else None
    if any(token in kind for token in ("date", "time", "timestamp")):
        # ETP timestamps are transported as integer microseconds in the v1.2 model.
        return IndexType.DATETIME, IndexRole.TIME, source_uom or "us", None, "DATETIME", "UTC"
    if "tvdss" in kind:
        canonical = _canonical_or_source(default_uom_dictionary(), source_uom or "m")
        return IndexType.TVDSS, IndexRole.DEPTH, source_uom or canonical, canonical, "TVDSS", None
    if "tvd" in kind:
        canonical = _canonical_or_source(default_uom_dictionary(), source_uom or "m")
        return IndexType.TVD, IndexRole.DEPTH, source_uom or canonical, canonical, "TVD", None
    if "depth" in kind or kind in {"md", "measureddepth"}:
        canonical = _canonical_or_source(default_uom_dictionary(), source_uom or "m")
        return IndexType.MD, IndexRole.DEPTH, source_uom or canonical, canonical, "MD", None
    canonical = _canonical_or_source(default_uom_dictionary(), source_uom)
    return IndexType.GENERIC, IndexRole.GENERIC, source_uom, canonical, "INDEX", None


def _canonical_or_source(uoms: UomDictionary, value: str | None) -> str | None:
    if not value:
        return None
    resolution = uoms.resolve(value)
    return resolution.canonical if resolution.recognized else value.strip()



def _conversion_supported(uoms: UomDictionary, source: str | None, target: str | None) -> bool:
    left = (source or "").strip().casefold()
    right = (target or "").strip().casefold()
    return left == right or uoms.conversion(source, target) is not None


def _dataset_kind(value: DatasetKind | str) -> DatasetKind:
    return value if isinstance(value, DatasetKind) else DatasetKind(str(value))


def _index_type(value: IndexType | str) -> IndexType:
    return value if isinstance(value, IndexType) else IndexType(str(value))


def _index_role(value: IndexRole | str) -> IndexRole:
    return value if isinstance(value, IndexRole) else IndexRole(str(value))


def _quantity_class(
    value: QuantityClass | str | None,
    *,
    fallback: QuantityClass,
) -> QuantityClass:
    if value is None:
        return fallback
    return value if isinstance(value, QuantityClass) else QuantityClass(str(value))


def _has_errors(issues: Iterable[Etp12ReviewIssue], rows: Iterable[Etp12ChannelReview]) -> bool:
    return any(item.severity is Etp12ReviewSeverity.ERROR for item in issues) or any(
        issue.severity is Etp12ReviewSeverity.ERROR for row in rows for issue in row.issues
    )
