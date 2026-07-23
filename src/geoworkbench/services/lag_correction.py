from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from typing import Any

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.lag_correction import (
    AnnularVolumeFlowLagParameters,
    ConstantTimeLagParameters,
    ControlPointLagParameters,
    LagCorrectionAxisMode,
    LagCorrectionMethod,
    LagCorrectionParameters,
    LagCorrectionProfile,
    LagCorrectionRevision,
    LagCorrectionTarget,
    LAG_CORRECTION_FORMULA_ID,
    LAG_CORRECTION_FORMULA_VERSION,
    PumpStrokeLagParameters,
    lag_seconds,
)
from geoworkbench.domain.models import (
    CalculationState,
    CurveData,
    Dataset,
    DatasetIndex,
    DatasetKind,
    IndexRole,
    IndexType,
    TimeDepthAggregationPolicy,
    Well,
)
from geoworkbench.services.acquisition import (
    AcquisitionController,
    canonical_curve_metadata,
)
from geoworkbench.services.uom_dictionary import QuantityClass, default_uom_dictionary


class LagCorrectionError(RuntimeError):
    """Base error for versioned lag/depth correction operations."""


class LagCorrectionConflictError(LagCorrectionError):
    """Raised when a profile, revision, source, or materialized projection diverges."""


@dataclass(frozen=True, slots=True)
class LagCorrectionPreview:
    profile_id: str
    revision: int
    source_dataset_id: str
    output_dataset_id: str
    source_index_id: str
    corrected_index_id: str
    source_depth: NDArray[np.float64]
    corrected_depth: NDArray[np.float64]
    lag_seconds: NDArray[np.float64]

    def __post_init__(self) -> None:
        source = _readonly_float_array(self.source_depth, "source_depth")
        corrected = _readonly_float_array(self.corrected_depth, "corrected_depth")
        delays = _readonly_float_array(self.lag_seconds, "lag_seconds")
        if source.shape != corrected.shape or source.shape != delays.shape:
            raise ValueError("Массивы lag correction preview должны иметь одинаковую форму")
        object.__setattr__(self, "source_depth", source)
        object.__setattr__(self, "corrected_depth", corrected)
        object.__setattr__(self, "lag_seconds", delays)

    @property
    def row_count(self) -> int:
        return int(self.source_depth.size)

    @property
    def valid_count(self) -> int:
        return int(np.count_nonzero(np.isfinite(self.corrected_depth)))

    @property
    def invalid_count(self) -> int:
        return self.row_count - self.valid_count


@dataclass(frozen=True, slots=True)
class LagCorrectionAxisSelection:
    profile_id: str
    revision: int
    mode: LagCorrectionAxisMode
    dataset: Dataset
    index_id: str


@dataclass(frozen=True, slots=True)
class LagCorrectionCreateRequest:
    profile_id: str
    name: str
    target: LagCorrectionTarget
    source_dataset_id: str
    source_time_index_id: str | None
    source_depth_index_id: str
    target_curve_ids: tuple[str, ...]
    method: LagCorrectionMethod
    parameters: LagCorrectionParameters
    aggregation_policy: TimeDepthAggregationPolicy
    output_dataset_id: str
    output_source_index_id: str
    output_index_id: str
    created_at: str
    created_by: str
    comment: str = ""


class LagCorrectionController:
    """Mutation and validation boundary for immutable correction revisions.

    Every revision materializes a separate derived dataset containing both the original
    and corrected depth axes. The source acquisition dataset and journal are never changed.
    """

    def __init__(self, well: Well) -> None:
        self.well = well
        for profile in tuple(well.lag_correction_profiles.values()):
            self.verify_profile(profile.profile_id)

    def create_profile(self, request: LagCorrectionCreateRequest) -> LagCorrectionProfile:
        if not isinstance(request, LagCorrectionCreateRequest):
            raise TypeError("request должен использовать LagCorrectionCreateRequest")
        if request.profile_id in self.well.lag_correction_profiles:
            raise LagCorrectionConflictError(
                f"Lag correction профиль уже существует: {request.profile_id}"
            )
        if any(
            item.name.casefold() == request.name.strip().casefold()
            for item in self.well.lag_correction_profiles.values()
        ):
            raise LagCorrectionConflictError(
                f"Lag correction профиль с таким именем уже существует: {request.name.strip()}"
            )
        revision, output = self._build_revision(request, revision_number=1)
        profile = LagCorrectionProfile(
            profile_id=request.profile_id,
            well_id=self.well.well_id,
            name=request.name.strip(),
            target=request.target,
            source_dataset_id=request.source_dataset_id,
            revisions=(revision,),
            active_revision=1,
        )
        self.well.datasets[output.dataset_id] = output
        self.well.lag_correction_profiles[profile.profile_id] = profile
        return profile

    def add_revision(
        self,
        profile_id: str,
        request: LagCorrectionCreateRequest,
        *,
        expected_latest_revision: int,
    ) -> LagCorrectionProfile:
        profile = self._profile(profile_id)
        if request.profile_id != profile.profile_id:
            raise LagCorrectionConflictError("Revision request относится к другому профилю")
        if request.source_dataset_id != profile.source_dataset_id:
            raise LagCorrectionConflictError("Revision не может сменить source dataset")
        if request.target is not profile.target:
            raise LagCorrectionConflictError("Revision не может сменить target профиля")
        if expected_latest_revision != profile.latest_revision:
            raise LagCorrectionConflictError(
                f"Revision conflict: expected {expected_latest_revision}, "
                f"actual {profile.latest_revision}"
            )
        if request.output_dataset_id in self.well.datasets:
            raise LagCorrectionConflictError(
                f"Output dataset уже существует: {request.output_dataset_id}"
            )
        revision_number = profile.latest_revision + 1
        revision, output = self._build_revision(request, revision_number=revision_number)
        updated = replace(
            profile,
            revisions=(*profile.revisions, revision),
            active_revision=revision_number,
        )
        self.well.datasets[output.dataset_id] = output
        self.well.lag_correction_profiles[profile_id] = updated
        return updated

    def activate_revision(
        self,
        profile_id: str,
        revision: int,
        *,
        expected_active_revision: int | None = None,
    ) -> LagCorrectionProfile:
        profile = self._profile(profile_id)
        if (
            expected_active_revision is not None
            and profile.active_revision != expected_active_revision
        ):
            raise LagCorrectionConflictError(
                f"Active revision conflict: expected {expected_active_revision}, "
                f"actual {profile.active_revision}"
            )
        profile.revision_by_number(revision)
        updated = replace(profile, active_revision=revision)
        self.well.lag_correction_profiles[profile_id] = updated
        return updated

    def delete_profile(self, profile_id: str) -> None:
        profile = self._profile(profile_id)
        del self.well.lag_correction_profiles[profile_id]
        for revision in profile.revisions:
            self.well.datasets.pop(revision.output_dataset_id, None)

    def preview(
        self, profile_id: str, revision: int | None = None
    ) -> LagCorrectionPreview:
        profile = self._profile(profile_id)
        item = profile.active if revision is None else profile.revision_by_number(revision)
        dataset = self._output_dataset(item)
        return LagCorrectionPreview(
            profile_id=profile.profile_id,
            revision=item.revision,
            source_dataset_id=profile.source_dataset_id,
            output_dataset_id=item.output_dataset_id,
            source_index_id=item.output_source_index_id,
            corrected_index_id=item.output_index_id,
            source_depth=np.asarray(dataset.indexes[item.output_source_index_id].values),
            corrected_depth=np.asarray(dataset.indexes[item.output_index_id].values),
            lag_seconds=_lag_seconds_array(item, len(dataset.depth)),
        )

    def select_axis(
        self,
        profile_id: str,
        mode: LagCorrectionAxisMode,
        revision: int | None = None,
    ) -> LagCorrectionAxisSelection:
        if not isinstance(mode, LagCorrectionAxisMode):
            raise ValueError("mode должен использовать LagCorrectionAxisMode")
        profile = self._profile(profile_id)
        item = profile.active if revision is None else profile.revision_by_number(revision)
        dataset = self._output_dataset(item)
        index_id = (
            item.output_source_index_id
            if mode is LagCorrectionAxisMode.SOURCE
            else item.output_index_id
        )
        return LagCorrectionAxisSelection(
            profile.profile_id,
            item.revision,
            mode,
            dataset,
            index_id,
        )

    def verify_profile(self, profile_id: str) -> None:
        profile = self._profile(profile_id)
        if profile.well_id != self.well.well_id:
            raise LagCorrectionConflictError("Lag correction профиль относится к другой скважине")
        source = self._source_dataset(profile.source_dataset_id)
        for revision in profile.revisions:
            if revision.source_row_count > len(source.depth):
                raise LagCorrectionConflictError(
                    f"Source dataset короче revision {revision.revision}"
                )
            actual_source = lag_source_fingerprint(
                source,
                source_time_index_id=revision.source_time_index_id,
                source_depth_index_id=revision.source_depth_index_id,
                target_curve_ids=revision.target_curve_ids,
                row_count=revision.source_row_count,
            )
            if actual_source != revision.source_fingerprint:
                raise LagCorrectionConflictError(
                    f"Source prefix изменён для revision {revision.revision}"
                )
            actual = self._output_dataset(revision)
            if lag_output_fingerprint(actual, revision) != revision.output_dataset_digest:
                raise LagCorrectionConflictError(
                    f"Output dataset изменён для revision {revision.revision}"
                )
            expected = materialize_lag_corrected_dataset(
                source,
                profile_name=profile.name,
                profile_id=profile.profile_id,
                target=profile.target,
                revision=revision.revision,
                method=revision.method,
                parameters=revision.parameters,
                source_time_index_id=revision.source_time_index_id,
                source_depth_index_id=revision.source_depth_index_id,
                target_curve_ids=revision.target_curve_ids,
                aggregation_policy=revision.aggregation_policy,
                output_dataset_id=revision.output_dataset_id,
                output_source_index_id=revision.output_source_index_id,
                output_index_id=revision.output_index_id,
                row_count=revision.source_row_count,
            )
            if lag_output_fingerprint(expected, revision) != revision.output_dataset_digest:
                raise LagCorrectionConflictError(
                    f"Correction replay diverged for revision {revision.revision}"
                )

    def _build_revision(
        self,
        request: LagCorrectionCreateRequest,
        *,
        revision_number: int,
    ) -> tuple[LagCorrectionRevision, Dataset]:
        source = self._source_dataset(request.source_dataset_id)
        if request.output_dataset_id in self.well.datasets:
            raise LagCorrectionConflictError(
                f"Output dataset уже существует: {request.output_dataset_id}"
            )
        row_count = len(source.depth)
        if row_count < 1:
            raise LagCorrectionConflictError("Lag correction требует непустой source dataset")
        output = materialize_lag_corrected_dataset(
            source,
            profile_name=request.name.strip(),
            profile_id=request.profile_id,
            target=request.target,
            revision=revision_number,
            method=request.method,
            parameters=request.parameters,
            source_time_index_id=request.source_time_index_id,
            source_depth_index_id=request.source_depth_index_id,
            target_curve_ids=request.target_curve_ids,
            aggregation_policy=request.aggregation_policy,
            output_dataset_id=request.output_dataset_id,
            output_source_index_id=request.output_source_index_id,
            output_index_id=request.output_index_id,
            row_count=row_count,
        )
        source_sequence, source_audit_digest = self._acquisition_provenance(
            request.source_dataset_id
        )
        revision = LagCorrectionRevision(
            revision=revision_number,
            method=request.method,
            parameters=request.parameters,
            source_time_index_id=request.source_time_index_id,
            source_depth_index_id=request.source_depth_index_id,
            target_curve_ids=request.target_curve_ids,
            aggregation_policy=request.aggregation_policy,
            output_dataset_id=request.output_dataset_id,
            output_source_index_id=request.output_source_index_id,
            output_index_id=request.output_index_id,
            source_row_count=row_count,
            source_fingerprint=lag_source_fingerprint(
                source,
                source_time_index_id=request.source_time_index_id,
                source_depth_index_id=request.source_depth_index_id,
                target_curve_ids=request.target_curve_ids,
                row_count=row_count,
            ),
            output_dataset_digest=lag_output_fingerprint_from_ids(
                output,
                output_source_index_id=request.output_source_index_id,
                output_index_id=request.output_index_id,
                target_curve_ids=request.target_curve_ids,
            ),
            source_sequence=source_sequence,
            source_audit_digest=source_audit_digest,
            formula_id=LAG_CORRECTION_FORMULA_ID,
            formula_version=LAG_CORRECTION_FORMULA_VERSION,
            created_at=request.created_at,
            created_by=request.created_by.strip(),
            comment=request.comment,
        )
        return revision, output

    def _acquisition_provenance(self, dataset_id: str) -> tuple[int | None, str | None]:
        for session in self.well.acquisition_sessions.values():
            if session.dataset_schema.dataset_id == dataset_id:
                result = AcquisitionController(self.well, session).current_result()
                return result.sequence, result.audit_digest
        return None, None

    def _profile(self, profile_id: str) -> LagCorrectionProfile:
        try:
            return self.well.lag_correction_profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"Lag correction профиль не найден: {profile_id}") from exc

    def _source_dataset(self, dataset_id: str) -> Dataset:
        try:
            return self.well.datasets[dataset_id]
        except KeyError as exc:
            raise LagCorrectionConflictError(
                f"Source dataset lag correction не найден: {dataset_id}"
            ) from exc

    def _output_dataset(self, revision: LagCorrectionRevision) -> Dataset:
        try:
            dataset = self.well.datasets[revision.output_dataset_id]
        except KeyError as exc:
            raise LagCorrectionConflictError(
                f"Output dataset lag correction не найден: {revision.output_dataset_id}"
            ) from exc
        return dataset


def materialize_lag_corrected_dataset(
    source: Dataset,
    *,
    profile_name: str,
    profile_id: str,
    target: LagCorrectionTarget,
    revision: int,
    method: LagCorrectionMethod,
    parameters: LagCorrectionParameters,
    source_time_index_id: str | None,
    source_depth_index_id: str,
    target_curve_ids: tuple[str, ...],
    aggregation_policy: TimeDepthAggregationPolicy,
    output_dataset_id: str,
    output_source_index_id: str,
    output_index_id: str,
    row_count: int,
) -> Dataset:
    if not isinstance(target, LagCorrectionTarget):
        raise ValueError("target должен использовать LagCorrectionTarget")
    if not isinstance(method, LagCorrectionMethod):
        raise ValueError("method должен использовать LagCorrectionMethod")
    if not isinstance(aggregation_policy, TimeDepthAggregationPolicy):
        raise ValueError("aggregation_policy имеет неверный тип")
    if row_count < 1 or row_count > len(source.depth):
        raise LagCorrectionConflictError("row_count correction выходит за source dataset")
    try:
        depth_index = source.indexes[source_depth_index_id]
    except KeyError as exc:
        raise LagCorrectionConflictError("Source DEPTH index не найден") from exc
    if depth_index.role is not IndexRole.DEPTH:
        raise LagCorrectionConflictError("Source depth index не имеет роль DEPTH")
    source_depth = np.asarray(depth_index.values[:row_count], dtype=np.float64)
    if source_depth.shape != (row_count,):
        raise LagCorrectionConflictError("Source DEPTH index имеет неверную форму")
    for curve_id in target_curve_ids:
        curve = source.curves.get(curve_id)
        if curve is None:
            raise LagCorrectionConflictError(f"Target curve не найдена: {curve_id}")
        if len(curve.values) < row_count:
            raise LagCorrectionConflictError(f"Target curve короче source rows: {curve_id}")

    if method is LagCorrectionMethod.CONTROL_POINTS:
        if source_time_index_id is not None:
            raise LagCorrectionConflictError("Control-point correction не использует TIME index")
        assert isinstance(parameters, ControlPointLagParameters)
        corrected = _control_point_depth(parameters, row_count)
    else:
        if source_time_index_id is None:
            raise LagCorrectionConflictError("Time-based correction требует TIME index")
        try:
            time_index = source.indexes[source_time_index_id]
        except KeyError as exc:
            raise LagCorrectionConflictError("Source TIME index не найден") from exc
        if time_index.role is not IndexRole.TIME:
            raise LagCorrectionConflictError("Source time index не имеет роль TIME")
        times = _time_values_seconds(time_index, row_count)
        delay = lag_seconds(parameters)
        assert delay is not None
        corrected = _correct_depth_by_time(
            times,
            source_depth,
            delay,
            aggregation_policy,
        )
    if not np.any(np.isfinite(corrected)):
        raise LagCorrectionConflictError("Lag correction не создала ни одной валидной глубины")

    source_axis = DatasetIndex(
        index_id=output_source_index_id,
        mnemonic=f"{depth_index.mnemonic}_SOURCE",
        index_type=depth_index.index_type,
        role=IndexRole.DEPTH,
        unit=depth_index.unit,
        values=source_depth,
        confidence=depth_index.confidence,
        evidence=(*depth_index.evidence, f"lag profile {profile_id} revision {revision}: source"),
        datetime_format=depth_index.datetime_format,
        timezone=depth_index.timezone,
    )
    corrected_axis = DatasetIndex(
        index_id=output_index_id,
        mnemonic=f"{depth_index.mnemonic}_LAG_CORR",
        index_type=depth_index.index_type,
        role=IndexRole.DEPTH,
        unit=depth_index.unit,
        values=corrected,
        confidence=depth_index.confidence,
        evidence=(
            *depth_index.evidence,
            f"{LAG_CORRECTION_FORMULA_ID} v{LAG_CORRECTION_FORMULA_VERSION}",
            f"lag profile {profile_id} revision {revision}",
        ),
        datetime_format=depth_index.datetime_format,
        timezone=depth_index.timezone,
    )
    output = Dataset(
        dataset_id=output_dataset_id,
        name=f"{source.name} - {profile_name} v{revision}",
        kind=DatasetKind.DERIVED,
        depth_domain=source.depth_domain,
        depth=corrected,
        indexes={
            output_source_index_id: source_axis,
            output_index_id: corrected_axis,
        },
        active_index_id=output_index_id,
        headers={
            "LAG_PROFILE_ID": profile_id,
            "LAG_PROFILE_NAME": profile_name,
            "LAG_TARGET": target.value,
            "LAG_REVISION": str(revision),
            "LAG_SOURCE_DATASET_ID": source.dataset_id,
        },
        parameters={
            "LAG_METHOD": method.value,
            "LAG_FORMULA_ID": LAG_CORRECTION_FORMULA_ID,
            "LAG_FORMULA_VERSION": str(LAG_CORRECTION_FORMULA_VERSION),
            "LAG_PARAMETERS": json.dumps(
                _json_ready(asdict(parameters)),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    output.curves = {
        curve_id: CurveData(
            metadata=replace(source.curves[curve_id].metadata, source_dataset_id=output_dataset_id),
            values=np.asarray(source.curves[curve_id].values[:row_count], dtype=np.float64).copy(),
            version=source.curves[curve_id].version,
            state=CalculationState.CURRENT,
        )
        for curve_id in target_curve_ids
    }
    return output


def lag_output_fingerprint(
    dataset: Dataset,
    revision: LagCorrectionRevision,
) -> str:
    return lag_output_fingerprint_from_ids(
        dataset,
        output_source_index_id=revision.output_source_index_id,
        output_index_id=revision.output_index_id,
        target_curve_ids=revision.target_curve_ids,
    )


def lag_output_fingerprint_from_ids(
    dataset: Dataset,
    *,
    output_source_index_id: str,
    output_index_id: str,
    target_curve_ids: tuple[str, ...],
) -> str:
    try:
        indexes = {
            index_id: dataset.indexes[index_id]
            for index_id in (output_source_index_id, output_index_id)
        }
    except KeyError as exc:
        raise LagCorrectionConflictError("Lag output index не найден") from exc
    payload: dict[str, Any] = {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "kind": dataset.kind.value,
        "depth_domain": dataset.depth_domain.value,
        "headers": dataset.headers,
        "parameters": dataset.parameters,
        "indexes": {},
        "curves": {},
    }
    for index_id, index in indexes.items():
        payload["indexes"][index_id] = {
            "metadata": {
                "mnemonic": index.mnemonic,
                "index_type": index.index_type.value,
                "role": index.role.value,
                "unit": index.unit,
                "confidence": index.confidence,
                "evidence": index.evidence,
                "datetime_format": index.datetime_format,
                "timezone": index.timezone,
            },
            "values": _array_tokens(index.values),
        }
    for curve_id in target_curve_ids:
        try:
            curve = dataset.curves[curve_id]
        except KeyError as exc:
            raise LagCorrectionConflictError(f"Lag output curve не найдена: {curve_id}") from exc
        payload["curves"][curve_id] = {
            "metadata": _json_ready(asdict(canonical_curve_metadata(curve.metadata))),
            "version": curve.version,
            "state": curve.state.value,
            "values": _array_tokens(curve.values),
        }
    return _sha256_payload(payload)


def lag_source_fingerprint(
    source: Dataset,
    *,
    source_time_index_id: str | None,
    source_depth_index_id: str,
    target_curve_ids: tuple[str, ...],
    row_count: int,
) -> str:
    if row_count < 1 or row_count > len(source.depth):
        raise LagCorrectionConflictError("row_count fingerprint выходит за source dataset")
    index_ids = [source_depth_index_id]
    if source_time_index_id is not None:
        index_ids.append(source_time_index_id)
    payload: dict[str, Any] = {
        "dataset_id": source.dataset_id,
        "row_count": row_count,
        "indexes": {},
        "curves": {},
    }
    for index_id in index_ids:
        try:
            index = source.indexes[index_id]
        except KeyError as exc:
            raise LagCorrectionConflictError(f"Source index не найден: {index_id}") from exc
        payload["indexes"][index_id] = {
            "metadata": {
                "mnemonic": index.mnemonic,
                "index_type": index.index_type.value,
                "role": index.role.value,
                "unit": index.unit,
                "datetime_format": index.datetime_format,
                "timezone": index.timezone,
            },
            "values": _array_tokens(index.values[:row_count]),
        }
    for curve_id in target_curve_ids:
        try:
            curve = source.curves[curve_id]
        except KeyError as exc:
            raise LagCorrectionConflictError(f"Target curve не найдена: {curve_id}") from exc
        payload["curves"][curve_id] = {
            "metadata": _json_ready(asdict(canonical_curve_metadata(curve.metadata))),
            "values": _array_tokens(curve.values[:row_count]),
        }
    return _sha256_payload(payload)


def _correct_depth_by_time(
    times: NDArray[np.float64],
    depths: NDArray[np.float64],
    delay_seconds: float,
    policy: TimeDepthAggregationPolicy,
) -> NDArray[np.float64]:
    valid = np.isfinite(times) & np.isfinite(depths)
    if np.count_nonzero(valid) < 2:
        raise LagCorrectionConflictError("TIME→DEPTH source требует минимум две валидные пары")
    mapping_time, mapping_depth = _collapse_time_depth(times[valid], depths[valid], policy)
    if mapping_time.size < 2:
        raise LagCorrectionConflictError("TIME→DEPTH mapping требует минимум две уникальные точки")
    targets = times - float(delay_seconds)
    corrected = np.full(times.shape, np.nan, dtype=np.float64)
    in_range = (
        np.isfinite(targets)
        & (targets >= mapping_time[0])
        & (targets <= mapping_time[-1])
    )
    corrected[in_range] = np.interp(
        targets[in_range],
        mapping_time,
        mapping_depth,
    )
    return corrected


def _collapse_time_depth(
    times: NDArray[np.float64],
    depths: NDArray[np.float64],
    policy: TimeDepthAggregationPolicy,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    order = np.argsort(times, kind="stable")
    sorted_times = times[order]
    sorted_depths = depths[order]
    unique_times: list[float] = []
    unique_depths: list[float] = []
    start = 0
    while start < len(sorted_times):
        end = start + 1
        while end < len(sorted_times) and sorted_times[end] == sorted_times[start]:
            end += 1
        candidates = sorted_depths[start:end]
        if policy is TimeDepthAggregationPolicy.ERROR:
            if np.unique(candidates).size != 1:
                raise LagCorrectionConflictError(
                    "TIME→DEPTH mapping неоднозначен; выберите aggregation policy"
                )
            depth = float(candidates[0])
        elif policy is TimeDepthAggregationPolicy.FIRST:
            depth = float(candidates[0])
        elif policy is TimeDepthAggregationPolicy.LAST:
            depth = float(candidates[-1])
        elif policy is TimeDepthAggregationPolicy.MIN:
            depth = float(np.min(candidates))
        elif policy is TimeDepthAggregationPolicy.MAX:
            depth = float(np.max(candidates))
        elif policy is TimeDepthAggregationPolicy.MEAN:
            depth = float(np.mean(candidates))
        else:  # defensive for future enum values
            raise LagCorrectionConflictError("Неподдерживаемая aggregation policy")
        unique_times.append(float(sorted_times[start]))
        unique_depths.append(depth)
        start = end
    return np.asarray(unique_times, dtype=np.float64), np.asarray(unique_depths, dtype=np.float64)


def _control_point_depth(
    parameters: ControlPointLagParameters,
    row_count: int,
) -> NDArray[np.float64]:
    rows = np.asarray([item.row for item in parameters.points], dtype=np.float64)
    if rows[-1] >= row_count:
        raise LagCorrectionConflictError("Контрольная точка выходит за source dataset")
    depths = np.asarray([item.corrected_depth_m for item in parameters.points], dtype=np.float64)
    targets = np.arange(row_count, dtype=np.float64)
    corrected = np.full(row_count, np.nan, dtype=np.float64)
    in_range = (targets >= rows[0]) & (targets <= rows[-1])
    corrected[in_range] = np.interp(targets[in_range], rows, depths)
    return corrected


def _time_values_seconds(index: DatasetIndex, row_count: int) -> NDArray[np.float64]:
    raw = np.asarray(index.values[:row_count])
    if index.index_type is IndexType.DATETIME:
        values_ns = raw.astype("datetime64[ns]")
        valid = ~np.isnat(values_ns)
        result = np.full(values_ns.shape, np.nan, dtype=np.float64)
        if np.any(valid):
            ints = values_ns[valid].astype(np.int64)
            origin = int(ints[0])
            result[valid] = (ints - origin).astype(np.float64) / 1_000_000_000.0
        return result
    if index.index_type is not IndexType.RELATIVE_TIME:
        raise LagCorrectionConflictError(
            "Lag correction поддерживает DATETIME или RELATIVE_TIME индекс"
        )
    resolution = default_uom_dictionary().resolve(index.unit)
    if not resolution.recognized or resolution.quantity_class is not QuantityClass.TIME:
        raise LagCorrectionConflictError("Единица TIME индекса не распознана")
    factors = {"s": 1.0, "min": 60.0, "h": 3600.0}
    try:
        factor = factors[resolution.canonical]
    except KeyError as exc:
        raise LagCorrectionConflictError(
            f"TIME unit не поддерживается для correction: {resolution.canonical}"
        ) from exc
    return np.asarray(raw, dtype=np.float64) * factor


def _lag_seconds_array(
    revision: LagCorrectionRevision,
    row_count: int,
) -> NDArray[np.float64]:
    value = lag_seconds(revision.parameters)
    if value is None:
        return np.full(row_count, np.nan, dtype=np.float64)
    return np.full(row_count, value, dtype=np.float64)


def _readonly_float_array(value: Any, name: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} должен быть одномерным")
    result = array.copy()
    result.setflags(write=False)
    return result


def _sha256_payload(payload: object) -> str:
    encoded = json.dumps(
        _json_ready(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _array_tokens(values: Any) -> list[Any]:
    array = np.asarray(values)
    if np.issubdtype(array.dtype, np.datetime64):
        ints = array.astype("datetime64[ns]").astype(np.int64)
        return [None if value == np.iinfo(np.int64).min else int(value) for value in ints]
    return [_json_ready(value) for value in array.tolist()]


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float):
        if np.isnan(value):
            return "NaN"
        if np.isposinf(value):
            return "+Infinity"
        if np.isneginf(value):
            return "-Infinity"
        return value
    if hasattr(value, "value"):
        return value.value
    return value
