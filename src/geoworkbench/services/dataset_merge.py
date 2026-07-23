from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    IndexRole,
    new_id,
)
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis


class MergeOverlapPolicy(StrEnum):
    """How values from the new LAS are applied on an overlapping depth interval."""

    PRESERVE_EXISTING = "preserve_existing"
    PREFER_SOURCE = "prefer_source"
    KEEP_BOTH = "keep_both"


@dataclass(frozen=True, slots=True)
class DatasetMergeAnalysis:
    source_dataset_id: str
    target_dataset_id: str
    source_sample_count: int
    target_sample_count: int
    merged_sample_count: int
    overlap_sample_count: int
    mnemonic_conflicts: tuple[str, ...]
    metadata_conflicts: tuple[str, ...] = ()
    overlap_value_conflict_count: int = 0
    merged_curve_count: int = 0
    source_only_curve_count: int = 0
    target_only_curve_count: int = 0

    @property
    def can_merge(self) -> bool:
        # Shared mnemonics are no longer a blocker. They are merged according to
        # the selected overlap policy, while incompatible curves are preserved
        # under a unique source suffix.
        return True


def analyze_dataset_merge(source: Dataset, target: Dataset) -> DatasetMergeAnalysis:
    source = _ascending_merge_view(source, "Источник")
    target = _ascending_merge_view(target, "Приёмник")
    _validate_pair(source, target)
    merged_depth = _union_depth(source.depth, target.depth)
    overlap = source.depth.size + target.depth.size - merged_depth.size
    source_by_name = _curves_by_semantic_name(source)
    target_by_name = _curves_by_semantic_name(target)
    shared = tuple(sorted(set(source_by_name) & set(target_by_name), key=str.casefold))
    metadata_conflicts: list[str] = []
    value_conflicts = 0
    for name in shared:
        source_curve = source_by_name[name][0]
        target_curve = target_by_name[name][0]
        if not _metadata_compatible(source_curve, target_curve):
            metadata_conflicts.append(
                f"{target_curve.metadata.original_mnemonic}: "
                f"{target_curve.metadata.unit or '—'} / {source_curve.metadata.unit or '—'}"
            )
            continue
        value_conflicts += _count_overlap_value_conflicts(
            source,
            source_curve,
            target,
            target_curve,
            merged_depth,
        )
    return DatasetMergeAnalysis(
        source.dataset_id,
        target.dataset_id,
        int(source.depth.size),
        int(target.depth.size),
        int(merged_depth.size),
        int(overlap),
        tuple(target_by_name[name][0].metadata.original_mnemonic for name in shared),
        tuple(metadata_conflicts),
        value_conflicts,
        merged_curve_count=sum(
            1
            for name in shared
            if _metadata_compatible(source_by_name[name][0], target_by_name[name][0])
        ),
        source_only_curve_count=len(set(source_by_name) - set(target_by_name)),
        target_only_curve_count=len(set(target_by_name) - set(source_by_name)),
    )


def create_merged_dataset(
    source: Dataset,
    target: Dataset,
    analysis: DatasetMergeAnalysis,
    *,
    name: str | None = None,
    overlap_policy: MergeOverlapPolicy = MergeOverlapPolicy.PRESERVE_EXISTING,
) -> Dataset:
    current = analyze_dataset_merge(source, target)
    if current != analysis:
        raise ValueError("Dataset изменился после анализа сращивания")
    source = _ascending_merge_view(source, "Источник")
    target = _ascending_merge_view(target, "Приёмник")
    policy = MergeOverlapPolicy(overlap_policy)
    merged_depth = _union_depth(source.depth, target.depth)
    dataset_id = new_id()
    indexes, active_index_id = _merge_indexes(source, target, merged_depth, dataset_id, policy)
    headers, header_conflicts = _merge_mapping(target.headers, source.headers)
    parameters, parameter_conflicts = _merge_mapping(target.parameters, source.parameters)
    version_headers, version_conflicts = _merge_mapping(
        target.version_headers, source.version_headers
    )
    result = Dataset(
        dataset_id=dataset_id,
        name=name or f"{target.name} + {source.name}",
        kind=DatasetKind.DERIVED,
        depth_domain=target.depth_domain,
        depth=merged_depth,
        source_path=None,
        headers=headers,
        parameters=parameters,
        indexes=indexes,
        active_index_id=active_index_id,
        version_headers=version_headers,
    )
    _merge_curves(source, target, result, merged_depth, policy)
    merged_report = analyze_depth_axis(merged_depth)
    result.headers.update(
        {
            "STRT": f"{merged_depth[0]:.15g}",
            "STOP": f"{merged_depth[-1]:.15g}",
            "STEP": (
                f"{merged_report.nominal_step:.15g}"
                if merged_report.is_uniform and merged_report.nominal_step is not None
                else ""
            ),
        }
    )
    result.parameters["MERGE_MANIFEST"] = json.dumps(
        {
            "version": 1,
            "policy": policy.value,
            "target": _parent_manifest(target),
            "source": _parent_manifest(source),
            "shared_mnemonics": list(current.mnemonic_conflicts),
            "metadata_conflicts": list(current.metadata_conflicts),
            "overlap_value_conflict_count": current.overlap_value_conflict_count,
            "header_conflicts": header_conflicts,
            "parameter_conflicts": parameter_conflicts,
            "version_header_conflicts": version_conflicts,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return result


def _merge_curves(
    source: Dataset,
    target: Dataset,
    result: Dataset,
    merged_depth: NDArray[np.float64],
    policy: MergeOverlapPolicy,
) -> None:
    target_positions = _positions_on_union(target.depth, merged_depth)
    source_positions = _positions_on_union(source.depth, merged_depth)
    source_by_name = _curves_by_semantic_name(source)
    consumed_source_ids: set[str] = set()

    for target_curve in target.curves.values():
        target_name = _semantic_name(target_curve)
        candidates = source_by_name.get(target_name, [])
        source_curve = next(
            (curve for curve in candidates if curve.metadata.curve_id not in consumed_source_ids),
            None,
        )
        if (
            source_curve is not None
            and _metadata_compatible(source_curve, target_curve)
            and policy is not MergeOverlapPolicy.KEEP_BOTH
        ):
            values = _mapped_values(target_curve.values, target_positions, merged_depth.size)
            _apply_source_values(values, source_curve.values, source_positions, policy)
            consumed_source_ids.add(source_curve.metadata.curve_id)
            _add_curve(
                result,
                target_curve,
                values,
                provenance=(
                    f"merge:{policy.value}:target:{target.dataset_id}:"
                    f"source:{source.dataset_id}:"
                    f"{target_curve.metadata.curve_id}:{source_curve.metadata.curve_id}"
                ),
            )
        else:
            values = _mapped_values(target_curve.values, target_positions, merged_depth.size)
            _add_curve(
                result,
                target_curve,
                values,
                provenance=f"merge:target:{target.dataset_id}:{target_curve.metadata.curve_id}",
            )

    used_names = {
        curve.metadata.original_mnemonic.casefold() for curve in result.curves.values()
    }
    for source_curve in source.curves.values():
        if source_curve.metadata.curve_id in consumed_source_ids:
            continue
        values = _mapped_values(source_curve.values, source_positions, merged_depth.size)
        mnemonic = source_curve.metadata.original_mnemonic
        if mnemonic.casefold() in used_names:
            mnemonic = _unique_mnemonic(mnemonic, used_names, source.name)
        _add_curve(
            result,
            source_curve,
            values,
            original_mnemonic=mnemonic,
            provenance=f"merge:source:{source.dataset_id}:{source_curve.metadata.curve_id}",
        )
        used_names.add(mnemonic.casefold())


def _merge_indexes(
    source: Dataset,
    target: Dataset,
    merged_depth: NDArray[np.float64],
    dataset_id: str,
    policy: MergeOverlapPolicy,
) -> tuple[dict[str, DatasetIndex], str]:
    indexes: dict[str, DatasetIndex] = {}
    active_id = f"{dataset_id}:primary-index"
    target_index = target.active_index
    indexes[active_id] = DatasetIndex(
        index_id=active_id,
        mnemonic=target_index.mnemonic,
        index_type=target_index.index_type,
        role=IndexRole.DEPTH,
        unit=target_index.unit,
        values=merged_depth,
        confidence=min(target_index.confidence, source.active_index.confidence),
        evidence=(
            f"merge-target:{target.dataset_id}",
            f"merge-source:{source.dataset_id}",
        ),
    )
    target_positions = _positions_on_union(target.depth, merged_depth)
    source_positions = _positions_on_union(source.depth, merged_depth)
    source_extra = [
        index for index in source.indexes.values() if index.index_id != source.active_index_id
    ]
    consumed: set[str] = set()
    used_mnemonics = {target_index.mnemonic.casefold()}

    for target_extra in target.indexes.values():
        if target_extra.index_id == target.active_index_id:
            continue
        match = next(
            (
                item
                for item in source_extra
                if item.index_id not in consumed and _indexes_compatible(item, target_extra)
            ),
            None,
        )
        values = _mapped_index_values(target_extra.values, target_positions, merged_depth.size)
        evidence = [f"merge-target:{target.dataset_id}:{target_extra.index_id}"]
        if match is not None and policy is not MergeOverlapPolicy.KEEP_BOTH:
            _apply_source_index_values(values, match.values, source_positions, policy)
            consumed.add(match.index_id)
            evidence.append(f"merge-source:{source.dataset_id}:{match.index_id}")
        index_id = f"{dataset_id}:index:{len(indexes) + 1}"
        indexes[index_id] = DatasetIndex(
            index_id=index_id,
            mnemonic=target_extra.mnemonic,
            index_type=target_extra.index_type,
            role=target_extra.role,
            unit=target_extra.unit,
            values=values,
            confidence=target_extra.confidence,
            evidence=target_extra.evidence + tuple(evidence),
            datetime_format=target_extra.datetime_format,
            timezone=target_extra.timezone,
        )
        used_mnemonics.add(target_extra.mnemonic.casefold())

    for source_extra_index in source_extra:
        if source_extra_index.index_id in consumed:
            continue
        mnemonic = source_extra_index.mnemonic
        if mnemonic.casefold() in used_mnemonics:
            mnemonic = _unique_mnemonic(mnemonic, used_mnemonics, source.name)
        values = _mapped_index_values(
            source_extra_index.values, source_positions, merged_depth.size
        )
        index_id = f"{dataset_id}:index:{len(indexes) + 1}"
        indexes[index_id] = DatasetIndex(
            index_id=index_id,
            mnemonic=mnemonic,
            index_type=source_extra_index.index_type,
            role=source_extra_index.role,
            unit=source_extra_index.unit,
            values=values,
            confidence=source_extra_index.confidence,
            evidence=source_extra_index.evidence
            + (f"merge-source:{source.dataset_id}:{source_extra_index.index_id}",),
            datetime_format=source_extra_index.datetime_format,
            timezone=source_extra_index.timezone,
        )
        used_mnemonics.add(mnemonic.casefold())
    return indexes, active_id


def _mapped_values(
    values: NDArray[np.float64], positions: NDArray[np.int64], size: int
) -> NDArray[np.float64]:
    result = np.full(size, np.nan, dtype=np.float64)
    result[positions] = np.asarray(values, dtype=np.float64)
    return result


def _mapped_index_values(
    values: NDArray[Any], positions: NDArray[np.int64], size: int
) -> NDArray[Any]:
    raw = np.asarray(values)
    if np.issubdtype(raw.dtype, np.datetime64):
        result = np.full(size, np.datetime64("NaT"), dtype="datetime64[ns]")
        result[positions] = raw.astype("datetime64[ns]")
        return result
    result = np.full(size, np.nan, dtype=np.float64)
    result[positions] = np.asarray(raw, dtype=np.float64)
    return result


def _apply_source_values(
    destination: NDArray[np.float64],
    source_values: NDArray[np.float64],
    positions: NDArray[np.int64],
    policy: MergeOverlapPolicy,
) -> None:
    incoming = np.asarray(source_values, dtype=np.float64)
    current = destination[positions]
    finite_incoming = np.isfinite(incoming)
    if policy is MergeOverlapPolicy.PREFER_SOURCE:
        writable = finite_incoming
    else:
        writable = finite_incoming & ~np.isfinite(current)
    current[writable] = incoming[writable]
    destination[positions] = current


def _apply_source_index_values(
    destination: NDArray[Any],
    source_values: NDArray[Any],
    positions: NDArray[np.int64],
    policy: MergeOverlapPolicy,
) -> None:
    incoming = np.asarray(source_values)
    current = destination[positions]
    if np.issubdtype(incoming.dtype, np.datetime64):
        finite_incoming = ~np.isnat(incoming)
        empty_current = np.isnat(current)
    else:
        incoming = np.asarray(incoming, dtype=np.float64)
        current = np.asarray(current, dtype=np.float64)
        finite_incoming = np.isfinite(incoming)
        empty_current = ~np.isfinite(current)
    writable = finite_incoming if policy is MergeOverlapPolicy.PREFER_SOURCE else (
        finite_incoming & empty_current
    )
    current[writable] = incoming[writable]
    destination[positions] = current


def _add_curve(
    result: Dataset,
    template: CurveData,
    values: NDArray[np.float64],
    *,
    original_mnemonic: str | None = None,
    provenance: str,
) -> None:
    metadata = template.metadata
    curve_id = new_id()
    result.curves[curve_id] = CurveData(
        CurveMetadata(
            curve_id=curve_id,
            original_mnemonic=original_mnemonic or metadata.original_mnemonic,
            canonical_mnemonic=metadata.canonical_mnemonic,
            unit=metadata.unit,
            description=metadata.description,
            source_dataset_id=result.dataset_id,
            provenance=provenance,
            semantic=metadata.semantic,
        ),
        np.asarray(values, dtype=np.float64),
        version=max(1, template.version),
        state=template.state,
    )


def _ascending_merge_view(dataset: Dataset, label: str) -> Dataset:
    """Return an in-memory ascending view without changing the loaded dataset."""

    report = analyze_depth_axis(dataset.depth)
    if report.direction is DepthDirection.ASCENDING:
        if report.duplicate_count or report.missing_count:
            raise ValueError(
                f"{label} должен иметь индекс без пропусков и дубликатов"
            )
        return dataset
    if report.direction is not DepthDirection.DESCENDING:
        raise ValueError(
            f"{label} должен иметь монотонный глубинный индекс; "
            f"получено направление {report.direction.value}"
        )
    if report.duplicate_count or report.missing_count:
        raise ValueError(f"{label} должен иметь индекс без пропусков и дубликатов")

    indexes = {
        index_id: DatasetIndex(
            index_id=index.index_id,
            mnemonic=index.mnemonic,
            index_type=index.index_type,
            role=index.role,
            unit=index.unit,
            values=np.asarray(index.values[::-1]).copy(),
            confidence=index.confidence,
            evidence=index.evidence + (f"merge-reversed-in-memory:{dataset.dataset_id}",),
            datetime_format=index.datetime_format,
            timezone=index.timezone,
        )
        for index_id, index in dataset.indexes.items()
    }
    view = Dataset(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        kind=dataset.kind,
        depth_domain=dataset.depth_domain,
        depth=np.asarray(dataset.depth[::-1], dtype=np.float64).copy(),
        source_path=dataset.source_path,
        headers=dict(dataset.headers),
        parameters=dict(dataset.parameters),
        indexes=indexes,
        active_index_id=dataset.active_index_id,
        version_headers=dict(dataset.version_headers),
    )
    for curve_id, curve in dataset.curves.items():
        view.curves[curve_id] = CurveData(
            metadata=curve.metadata,
            values=np.asarray(curve.values[::-1], dtype=np.float64).copy(),
            version=curve.version,
            state=curve.state,
        )
    return view


def _validate_pair(source: Dataset, target: Dataset) -> None:
    if source.dataset_id == target.dataset_id:
        raise ValueError("Источник и приёмник должны быть разными dataset")
    for label, dataset in (("Источник", source), ("Приёмник", target)):
        if dataset.active_index.role is not IndexRole.DEPTH:
            raise ValueError(f"{label} должен использовать активный глубинный индекс")
        report = analyze_depth_axis(dataset.depth)
        if (
            report.direction is not DepthDirection.ASCENDING
            or report.duplicate_count
            or report.missing_count
        ):
            raise ValueError(
                f"{label} должен иметь возрастающий индекс без пропусков и дубликатов"
            )
    if source.active_index.index_type is not target.active_index.index_type:
        raise ValueError("Типы глубинных индексов не совпадают")
    source_unit = (source.active_index.unit or "").strip().casefold()
    target_unit = (target.active_index.unit or "").strip().casefold()
    if source_unit != target_unit:
        raise ValueError("Единицы глубинных индексов не совпадают")


def _union_depth(
    source_depth: NDArray[np.float64], target_depth: NDArray[np.float64]
) -> NDArray[np.float64]:
    values = np.concatenate((target_depth, source_depth))
    priorities = np.concatenate(
        (
            np.zeros(target_depth.size, dtype=np.int8),
            np.ones(source_depth.size, dtype=np.int8),
        )
    )
    order = np.lexsort((priorities, values))
    sorted_values = values[order]
    sorted_priorities = priorities[order]
    tolerance = _tolerance(values)
    representatives: list[float] = []
    start = 0
    while start < sorted_values.size:
        stop = start + 1
        while (
            stop < sorted_values.size
            and sorted_values[stop] - sorted_values[stop - 1] <= tolerance
        ):
            stop += 1
        group_values = sorted_values[start:stop]
        group_priorities = sorted_priorities[start:stop]
        target_positions = np.flatnonzero(group_priorities == 0)
        chosen = int(target_positions[0]) if target_positions.size else 0
        representatives.append(float(group_values[chosen]))
        start = stop
    return np.asarray(representatives, dtype=np.float64)


def _positions_on_union(
    depth: NDArray[np.float64], merged_depth: NDArray[np.float64]
) -> NDArray[np.int64]:
    right = np.searchsorted(merged_depth, depth)
    right = np.minimum(right, merged_depth.size - 1)
    left = np.maximum(right - 1, 0)
    choose_left = np.abs(merged_depth[left] - depth) <= np.abs(merged_depth[right] - depth)
    positions = np.where(choose_left, left, right).astype(np.int64)
    if np.any(np.abs(merged_depth[positions] - depth) > _tolerance(merged_depth)):
        raise RuntimeError("Не удалось сопоставить глубину с объединённой сеткой")
    return positions


def _curves_by_semantic_name(dataset: Dataset) -> dict[str, list[CurveData]]:
    result: dict[str, list[CurveData]] = {}
    for curve in dataset.curves.values():
        result.setdefault(_semantic_name(curve), []).append(curve)
    return result


def _semantic_name(curve: CurveData) -> str:
    return (
        curve.metadata.canonical_mnemonic
        or curve.metadata.original_mnemonic
    ).strip().casefold()


def _metadata_compatible(source: CurveData, target: CurveData) -> bool:
    return _normalized_unit(source.metadata.unit) == _normalized_unit(target.metadata.unit)


def _indexes_compatible(source: DatasetIndex, target: DatasetIndex) -> bool:
    return (
        source.mnemonic.strip().casefold() == target.mnemonic.strip().casefold()
        and source.index_type is target.index_type
        and source.role is target.role
        and _normalized_unit(source.unit) == _normalized_unit(target.unit)
    )


def _normalized_unit(unit: str | None) -> str:
    return (unit or "").strip().casefold().replace(" ", "")


def _count_overlap_value_conflicts(
    source_dataset: Dataset,
    source_curve: CurveData,
    target_dataset: Dataset,
    target_curve: CurveData,
    merged_depth: NDArray[np.float64],
) -> int:
    source_positions = _positions_on_union(source_dataset.depth, merged_depth)
    target_positions = _positions_on_union(target_dataset.depth, merged_depth)
    source_values = _mapped_values(source_curve.values, source_positions, merged_depth.size)
    target_values = _mapped_values(target_curve.values, target_positions, merged_depth.size)
    both = np.isfinite(source_values) & np.isfinite(target_values)
    if not np.any(both):
        return 0
    tolerance = np.maximum(
        1e-12,
        np.maximum(np.abs(source_values[both]), np.abs(target_values[both])) * 1e-9,
    )
    return int(np.count_nonzero(np.abs(source_values[both] - target_values[both]) > tolerance))


def _merge_mapping(
    target: dict[str, str], source: dict[str, str]
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    result = dict(target)
    conflicts: dict[str, dict[str, str]] = {}
    casefold_keys = {key.casefold(): key for key in result}
    for source_key, source_value in source.items():
        target_key = casefold_keys.get(source_key.casefold())
        if target_key is None:
            result[source_key] = source_value
            casefold_keys[source_key.casefold()] = source_key
        elif result[target_key] != source_value:
            conflicts[target_key] = {"target": result[target_key], "source": source_value}
    return result, conflicts


def _parent_manifest(dataset: Dataset) -> dict[str, object]:
    return {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "source_path": str(dataset.source_path or ""),
        "sample_count": int(dataset.depth.size),
        "curve_count": len(dataset.curves),
        "index_count": len(dataset.indexes),
    }


def _unique_mnemonic(base: str, used_casefold: set[str], source_name: str) -> str:
    cleaned_source = "".join(character for character in source_name.upper() if character.isalnum())
    suffix = cleaned_source[:12] or "SOURCE"
    candidate = f"{base}_{suffix}"
    number = 2
    while candidate.casefold() in used_casefold:
        candidate = f"{base}_{suffix}_{number}"
        number += 1
    return candidate


def _tolerance(values: NDArray[np.float64]) -> float:
    return float(np.finfo(np.float64).eps * max(1.0, float(np.max(np.abs(values)))) * 16)
