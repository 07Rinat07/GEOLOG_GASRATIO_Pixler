import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.curve_transfer import (
    CurveTransferMapping,
    analyze_curve_transfer,
    build_transferred_curves,
)


def dataset(dataset_id: str, depth: list[float]) -> Dataset:
    return Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GIS,
        DepthDomain.MD,
        np.asarray(depth, dtype=np.float64),
    )


def add_curve(target: Dataset, curve_id: str, mnemonic: str, values: list[float]) -> None:
    target.curves[curve_id] = CurveData(
        CurveMetadata(curve_id, mnemonic, mnemonic, "API", None, target.dataset_id),
        np.asarray(values, dtype=np.float64),
    )


def test_transfer_analysis_reports_exact_mapping_and_mnemonic_conflicts() -> None:
    source = dataset("source", [100.0, 101.0])
    target = dataset("target", [100.0, 101.0])
    add_curve(source, "gr-source", "GR", [10.0, 20.0])
    add_curve(source, "rop-source", "ROP", [5.0, 6.0])
    add_curve(target, "gr-target", "GR", [11.0, 21.0])

    analysis = analyze_curve_transfer(source, target)

    assert analysis.mapping is CurveTransferMapping.EXACT
    assert [candidate.mnemonic for candidate in analysis.transferable] == ["ROP"]
    assert analysis.candidates[0].conflict == "Мнемоника занята кривой приёмника"
    with pytest.raises(ValueError, match="Конфликт мнемоник: GR"):
        build_transferred_curves(source, target, ("gr-source",), analysis=analysis)


def test_linear_transfer_does_not_bridge_source_gaps() -> None:
    source = dataset("source", [100.0, 101.0, 103.0, 104.0])
    target = dataset("target", [100.0, 100.5, 101.0, 102.0, 103.0, 104.0])
    add_curve(source, "gr", "GR", [10.0, 20.0, np.nan, 50.0])
    analysis = analyze_curve_transfer(source, target)

    curves = build_transferred_curves(source, target, ("gr",), analysis=analysis)

    assert analysis.mapping is CurveTransferMapping.LINEAR
    assert len(curves) == 1
    np.testing.assert_allclose(
        curves[0].values,
        [10.0, 15.0, 20.0, np.nan, np.nan, 50.0],
        equal_nan=True,
    )
    assert curves[0].metadata.source_dataset_id == "target"
    assert curves[0].metadata.provenance == "transfer:source:gr"


def test_transfer_rejects_extrapolation_and_descending_index() -> None:
    source = dataset("source", [100.0, 101.0])
    with pytest.raises(ValueError, match="внутри диапазона"):
        analyze_curve_transfer(source, dataset("target", [99.0, 100.0]))
    with pytest.raises(ValueError, match="возрастающий индекс"):
        analyze_curve_transfer(dataset("descending", [101.0, 100.0]), source)


def test_transfer_rejects_incompatible_depth_units() -> None:
    source = dataset("source", [100.0, 101.0])
    target = dataset("target", [100.0, 101.0])
    target.active_index.unit = "ft"

    with pytest.raises(ValueError, match="Единицы глубинных индексов"):
        analyze_curve_transfer(source, target)
