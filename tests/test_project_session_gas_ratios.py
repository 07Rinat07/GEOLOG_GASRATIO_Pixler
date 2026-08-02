from __future__ import annotations

from dataclasses import replace

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession


def _sparse(depth: np.ndarray, first: float, second: float, last: float) -> np.ndarray:
    values = np.full(depth.shape, np.nan)
    values[[0, 3, len(depth) - 1]] = (first, second, last)
    return values


def _gas_dataset(depth: np.ndarray) -> Dataset:
    dataset = Dataset(
        dataset_id="gas-dataset",
        name="Gas dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=depth,
    )
    for mnemonic, values in {
        "C1": _sparse(depth, 80.0, 70.0, 60.0),
        "C2": _sparse(depth, 10.0, 10.0, 10.0),
        "C3": _sparse(depth, 5.0, 5.0, 5.0),
        "IC4": _sparse(depth, 1.0, 1.0, 1.0),
        "NC4": _sparse(depth, 2.0, 2.0, 2.0),
        "IC5": _sparse(depth, 1.0, 1.0, 1.0),
        "NC5": _sparse(depth, 1.0, 1.0, 1.0),
    }.items():
        dataset.upsert_curve(
            mnemonic,
            values,
            unit="% abs",
            description=f"Source {mnemonic}",
            provenance="source:test",
        )
    return dataset


def test_project_session_conditions_components_before_deriving_ratios() -> None:
    depth = np.arange(0.0, 21.0)
    dataset = _gas_dataset(depth)
    source_c1 = dataset.curve_by_mnemonic("C1")
    assert source_c1 is not None
    original_c1 = source_c1.values.copy()

    session = ProjectSession()
    session.add_dataset(dataset)
    session.dirty = False

    created = session.calculate_basic_gas_ratios()

    assert "TG_CALC" in created
    assert "PIXLER_C1_C2" in created
    np.testing.assert_array_equal(source_c1.values, original_c1)

    total = dataset.curve_by_mnemonic("TG_CALC")
    pixler = dataset.curve_by_mnemonic("PIXLER_C1_C2")
    assert total is not None
    assert pixler is not None
    assert np.isfinite(total.values[1])
    assert np.isfinite(pixler.values[2])
    assert np.isnan(total.values[10])
    assert np.isnan(pixler.values[10])
    assert total.metadata.provenance == "calculation:conditioned-gas-ratio:2.0"
    assert session.dirty


def test_project_session_recalculation_updates_curve_and_metadata() -> None:
    depth = np.arange(0.0, 21.0)
    dataset = _gas_dataset(depth)
    session = ProjectSession()
    session.add_dataset(dataset)

    session.calculate_basic_gas_ratios()
    total = dataset.curve_by_mnemonic("TG_CALC")
    assert total is not None
    first_curve_id = total.metadata.curve_id
    first_version = total.version
    total.metadata = replace(
        total.metadata,
        unit="legacy-unit",
        description="Legacy basic ratio",
        provenance="calculation:basic-gas-ratio:1.0",
    )

    session.calculate_basic_gas_ratios()
    updated = dataset.curve_by_mnemonic("TG_CALC")
    assert updated is not None
    assert updated.metadata.curve_id == first_curve_id
    assert updated.version == first_version + 1
    assert updated.metadata.unit == "%abs"
    assert updated.metadata.description != "Legacy basic ratio"
    assert updated.metadata.provenance == "calculation:conditioned-gas-ratio:2.0"
