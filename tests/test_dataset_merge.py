import json

import numpy as np
import pytest

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
from geoworkbench.services.dataset_merge import (
    MergeOverlapPolicy,
    analyze_dataset_merge,
    create_merged_dataset,
)


def make_dataset(dataset_id: str, depth: list[float]) -> Dataset:
    return Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray(depth, dtype=np.float64),
    )


def add_curve(
    dataset: Dataset,
    curve_id: str,
    mnemonic: str,
    values: list[float],
    *,
    unit: str = "%",
) -> None:
    dataset.curves[curve_id] = CurveData(
        CurveMetadata(curve_id, mnemonic, mnemonic, unit, None, dataset.dataset_id),
        np.asarray(values, dtype=np.float64),
    )


def test_merge_analysis_and_copy_preserve_samples_without_interpolation() -> None:
    source = make_dataset("source", [100.0, 101.0, 103.0])
    target = make_dataset("target", [101.0, 102.0, 104.0])
    add_curve(source, "gr", "GR", [10.0, 11.0, 13.0])
    add_curve(target, "rop", "ROP", [21.0, 22.0, 24.0])

    analysis = analyze_dataset_merge(source, target)
    result = create_merged_dataset(source, target, analysis)

    assert analysis.source_sample_count == 3
    assert analysis.target_sample_count == 3
    assert analysis.merged_sample_count == 5
    assert analysis.overlap_sample_count == 1
    assert analysis.can_merge
    np.testing.assert_allclose(result.depth, [100, 101, 102, 103, 104])
    np.testing.assert_allclose(
        result.curve_by_mnemonic("GR").values,
        [10, 11, np.nan, 13, np.nan],
        equal_nan=True,
    )
    np.testing.assert_allclose(
        result.curve_by_mnemonic("ROP").values,
        [np.nan, 21, 22, np.nan, 24],
        equal_nan=True,
    )
    assert result.source_path is None
    assert result.headers["STRT"] == "100"
    assert result.headers["STOP"] == "104"
    assert result.headers["STEP"] == "1"


def test_progressive_merge_preserves_old_values_and_fills_gaps_from_new_las() -> None:
    source = make_dataset("new", [100.0, 101.0, 102.0, 103.0])
    target = make_dataset("old", [100.0, 101.0, 102.0])
    target.source_path = None
    add_curve(source, "new-gr", "GR", [9.0, 11.0, 12.0, 13.0], unit="API")
    add_curve(target, "old-gr", "GR", [10.0, np.nan, 20.0], unit="API")
    target.headers["WELL"] = "Old well header"
    source.headers["WELL"] = "New conflicting header"
    source.headers["COMP"] = "New company"

    analysis = analyze_dataset_merge(source, target)
    result = create_merged_dataset(source, target, analysis)

    assert analysis.mnemonic_conflicts == ("GR",)
    assert analysis.overlap_value_conflict_count == 2
    assert analysis.can_merge
    np.testing.assert_allclose(
        result.curve_by_mnemonic("GR").values,
        [10.0, 11.0, 20.0, 13.0],
        equal_nan=True,
    )
    assert result.headers["WELL"] == "Old well header"
    assert result.headers["COMP"] == "New company"
    manifest = json.loads(result.parameters["MERGE_MANIFEST"])
    assert manifest["policy"] == "preserve_existing"
    assert manifest["header_conflicts"]["WELL"] == {
        "target": "Old well header",
        "source": "New conflicting header",
    }


def test_merge_can_prefer_new_las_on_overlap() -> None:
    source = make_dataset("new", [100.0, 101.0, 102.0])
    target = make_dataset("old", [100.0, 101.0, 102.0])
    add_curve(source, "new-gr", "GR", [1.0, 2.0, 3.0], unit="API")
    add_curve(target, "old-gr", "GR", [10.0, 20.0, 30.0], unit="API")

    result = create_merged_dataset(
        source,
        target,
        analyze_dataset_merge(source, target),
        overlap_policy=MergeOverlapPolicy.PREFER_SOURCE,
    )

    np.testing.assert_allclose(result.curve_by_mnemonic("GR").values, [1.0, 2.0, 3.0])


def test_incompatible_shared_curve_is_preserved_under_unique_mnemonic() -> None:
    source = make_dataset("New LAS", [100.0, 101.0])
    target = make_dataset("Old LAS", [100.0, 101.0])
    add_curve(source, "new-gr", "GR", [1.0, 2.0], unit="m")
    add_curve(target, "old-gr", "GR", [10.0, 20.0], unit="API")

    analysis = analyze_dataset_merge(source, target)
    result = create_merged_dataset(source, target, analysis)

    assert analysis.metadata_conflicts
    assert len(result.curves) == 2
    np.testing.assert_allclose(result.curve_by_mnemonic("GR").values, [10.0, 20.0])
    source_copy = next(
        curve for curve in result.curves.values() if curve.metadata.original_mnemonic != "GR"
    )
    assert source_copy.metadata.original_mnemonic.startswith("GR_NEWLAS")
    np.testing.assert_allclose(source_copy.values, [1.0, 2.0])


def test_merge_preserves_additional_indexes_from_both_las_files() -> None:
    source = make_dataset("source", [100.0, 102.0])
    target = make_dataset("target", [100.0, 101.0])
    target.add_index(
        DatasetIndex(
            "target-time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 1.0]),
        )
    )
    source.add_index(
        DatasetIndex(
            "source-time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 2.0]),
        )
    )

    result = create_merged_dataset(source, target, analyze_dataset_merge(source, target))

    time_index = next(index for index in result.indexes.values() if index.role is IndexRole.TIME)
    np.testing.assert_allclose(time_index.values, [0.0, 1.0, 2.0], equal_nan=True)


def test_merge_rejects_different_index_types() -> None:
    source = make_dataset("source", [100.0, 101.0])
    target = Dataset(
        "target",
        "target",
        DatasetKind.GTI,
        DepthDomain.TVD,
        np.array([100.0, 101.0]),
    )
    with pytest.raises(ValueError, match="Типы глубинных индексов"):
        analyze_dataset_merge(source, target)
