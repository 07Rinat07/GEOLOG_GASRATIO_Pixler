from __future__ import annotations

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
)
from geoworkbench.services.dataset_copy import create_dataset_copy
from geoworkbench.services.dataset_merge import analyze_dataset_merge, create_merged_dataset
from geoworkbench.services.depth_axis import (
    analyze_depth_resample,
    create_ascending_depth_copy,
    create_resampled_depth_copy,
)
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.services.time_to_depth_conversion import (
    TimeToDepthPlan,
    convert_time_dataset_to_depth,
)


def _curve(
    dataset: Dataset,
    *,
    curve_id: str = "rop",
    mnemonic: str = "ROP",
    unit: str = "м/ч",
    values: list[float] | None = None,
) -> CurveData:
    binding = SemanticChannelDictionary().resolve(mnemonic, unit=unit)
    curve = CurveData(
        CurveMetadata(
            curve_id,
            mnemonic,
            binding.canonical_mnemonic,
            unit,
            mnemonic,
            dataset.dataset_id,
            semantic=binding,
        ),
        np.asarray(values or [1.0, 2.0, 3.0], dtype=np.float64),
    )
    dataset.curves[curve_id] = curve
    return curve


def test_dataset_copy_preserves_same_immutable_semantic_snapshot() -> None:
    source = Dataset(
        "source",
        "Source",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([100.0, 101.0, 102.0]),
    )
    original = _curve(source)

    copied = create_dataset_copy(source, name="Copy")
    copied_curve = copied.curve_by_mnemonic("ROP")

    assert copied_curve is not None
    assert copied_curve.metadata.semantic == original.metadata.semantic


def test_depth_reverse_and_resample_preserve_semantic_snapshot() -> None:
    source = Dataset(
        "source",
        "Source",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([102.0, 101.0, 100.0]),
    )
    original = _curve(source, values=[3.0, 2.0, 1.0])

    ascending = create_ascending_depth_copy(source)
    plan = analyze_depth_resample(ascending, 100.0, 102.0, 0.5)
    resampled = create_resampled_depth_copy(ascending, plan)

    assert ascending.curve_by_mnemonic("ROP").metadata.semantic == original.metadata.semantic
    assert resampled.curve_by_mnemonic("ROP").metadata.semantic == original.metadata.semantic


def test_dataset_merge_preserves_semantics_for_each_source_curve() -> None:
    first = Dataset(
        "first",
        "First",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([100.0, 101.0]),
    )
    second = Dataset(
        "second",
        "Second",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([101.0, 102.0]),
    )
    rop = _curve(first, values=[1.0, 2.0])
    gas = _curve(
        second,
        curve_id="c1",
        mnemonic="C1",
        unit="%",
        values=[0.1, 0.2],
    )

    merged = create_merged_dataset(first, second, analyze_dataset_merge(first, second))

    assert merged.curve_by_mnemonic("ROP").metadata.semantic == rop.metadata.semantic
    assert merged.curve_by_mnemonic("C1").metadata.semantic == gas.metadata.semantic


def test_time_to_depth_conversion_preserves_semantic_snapshot() -> None:
    dataset = Dataset(
        "time-source",
        "Time source",
        DatasetKind.USER,
        DepthDomain.TIME,
        np.asarray([0.0, 1.0, 2.0]),
        indexes={
            "time": DatasetIndex(
                "time",
                "TIME",
                IndexType.RELATIVE_TIME,
                IndexRole.TIME,
                "s",
                np.asarray([0.0, 1.0, 2.0]),
            ),
            "depth": DatasetIndex(
                "depth",
                "DEPT",
                IndexType.MD,
                IndexRole.DEPTH,
                "m",
                np.asarray([100.0, 100.1, 100.2]),
            ),
        },
        active_index_id="time",
    )
    original = _curve(dataset)

    result = convert_time_dataset_to_depth(
        dataset,
        TimeToDepthPlan(dataset.dataset_id, "depth", "time", 100.0, 100.2, 0.1),
    )

    converted = result.dataset.curve_by_mnemonic("ROP")
    assert converted is not None
    assert converted.metadata.semantic == original.metadata.semantic
