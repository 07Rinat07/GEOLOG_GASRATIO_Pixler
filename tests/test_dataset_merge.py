import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.dataset_merge import analyze_dataset_merge, create_merged_dataset


def make_dataset(dataset_id: str, depth: list[float]) -> Dataset:
    return Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray(depth, dtype=np.float64),
    )


def add_curve(dataset: Dataset, curve_id: str, mnemonic: str, values: list[float]) -> None:
    dataset.curves[curve_id] = CurveData(
        CurveMetadata(curve_id, mnemonic, mnemonic, "%", None, dataset.dataset_id),
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


def test_merge_preview_blocks_conflicting_mnemonics() -> None:
    source = make_dataset("source", [100.0, 101.0])
    target = make_dataset("target", [101.0, 102.0])
    add_curve(source, "gr-source", "GR", [10.0, 11.0])
    add_curve(target, "gr-target", "gr", [21.0, 22.0])

    analysis = analyze_dataset_merge(source, target)

    assert analysis.mnemonic_conflicts == ("gr",)
    assert not analysis.can_merge
    with pytest.raises(ValueError, match="Конфликт мнемоник"):
        create_merged_dataset(source, target, analysis)


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
