from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from numpy.typing import NDArray

from geoworkbench.domain.models import CurveData, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import load_project


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


def _dense_gas_dataset(depth: np.ndarray) -> Dataset:
    dataset = Dataset(
        dataset_id="dense-gas-dataset",
        name="Dense gas dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=depth,
    )
    for mnemonic, value in {
        "C1": 80.0,
        "C2": 10.0,
        "C3": 5.0,
        "IC4": 1.0,
        "NC4": 2.0,
        "IC5": 1.0,
        "NC5": 1.0,
    }.items():
        dataset.upsert_curve(
            mnemonic,
            np.full(depth.shape, value, dtype=np.float64),
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

    qc = dataset.gas_conditioning_qc
    assert qc is not None
    assert qc.nominal_depth_step == 1.0
    assert qc.affected_depth_row_count == 2
    assert qc.interpolated_component_sample_count == 14
    c1_qc = qc.component("C1")
    assert c1_qc.interpolated_sample_count == 2
    assert len(c1_qc.interpolated_intervals) == 1
    assert c1_qc.interpolated_intervals[0].minimum_depth == 1.0
    assert c1_qc.interpolated_intervals[0].maximum_depth == 2.0
    assert c1_qc.interpolated_intervals[0].sample_count == 2
    assert session.dirty


def test_project_session_records_empty_qc_when_no_interpolation_was_needed() -> None:
    dataset = _dense_gas_dataset(np.arange(1000.0, 1005.0))
    session = ProjectSession()
    session.add_dataset(dataset)

    session.calculate_basic_gas_ratios()

    qc = dataset.gas_conditioning_qc
    assert qc is not None
    assert qc.affected_depth_row_count == 0
    assert qc.interpolated_component_sample_count == 0
    assert qc.components
    assert all(component.interpolated_sample_count == 0 for component in qc.components)
    assert all(component.interpolated_intervals == () for component in qc.components)


def test_project_session_failed_curve_write_preserves_previous_qc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = _gas_dataset(np.arange(0.0, 21.0))
    session = ProjectSession()
    session.add_dataset(dataset)
    session.calculate_basic_gas_ratios()
    previous_qc = dataset.gas_conditioning_qc
    assert previous_qc is not None
    session.dirty = False

    original_upsert = Dataset.upsert_curve
    call_count = 0

    def fail_on_second_upsert(
        target: Dataset,
        mnemonic: str,
        values: NDArray[np.float64],
        *,
        unit: str | None = None,
        description: str | None = None,
        provenance: str = "derived",
    ) -> CurveData:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("simulated derived-curve write failure")
        return original_upsert(
            target,
            mnemonic,
            values,
            unit=unit,
            description=description,
            provenance=provenance,
        )

    monkeypatch.setattr(Dataset, "upsert_curve", fail_on_second_upsert)

    with pytest.raises(RuntimeError, match="simulated derived-curve write failure"):
        session.calculate_basic_gas_ratios()

    assert call_count == 2
    assert dataset.gas_conditioning_qc is previous_qc
    assert not session.dirty


def test_project_session_generated_qc_survives_project_round_trip(tmp_path) -> None:
    dataset = _gas_dataset(np.arange(0.0, 21.0))
    session = ProjectSession()
    well = session.add_dataset(dataset)
    session.calculate_basic_gas_ratios()
    expected_qc = dataset.gas_conditioning_qc
    assert expected_qc is not None

    target = tmp_path / "session-gas-qc.geolog.json"
    save_project(session.project, target)
    restored = load_project(target)

    restored_dataset = restored.wells[well.well_id].datasets[dataset.dataset_id]
    assert restored_dataset.gas_conditioning_qc == expected_qc


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
