from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasReference,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.drilling_input_plan import (
    DepthValueSection,
    DrillingInputPlan,
    DrillingInputResolver,
    InputSourceMode,
    ParameterSource,
    build_section_values,
)
from geoworkbench.services.las_parameter_resolver import ParameterResolutionError


def _dataset(depth: np.ndarray | None = None) -> Dataset:
    return Dataset(
        "dataset",
        "Геология_plus_Технология",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray(depth if depth is not None else [1000.0, 1001.0], dtype=np.float64),
    )


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    description: str,
    unit: str,
    values: np.ndarray | list[float],
) -> None:
    curve_id = f"curve-{len(dataset.curves)}"
    dataset.curves[curve_id] = CurveData(
        CurveMetadata(
            curve_id,
            mnemonic,
            mnemonic,
            unit,
            description,
            dataset.dataset_id,
        ),
        np.asarray(values, dtype=np.float64),
    )


def test_identical_technology_duplicate_is_collapsed() -> None:
    dataset = _dataset()
    _add_curve(dataset, "VENDOR_ROP", "Rate of penetration", "m/h", [12.0, 13.0])
    _add_curve(
        dataset,
        "VENDOR_ROP_TEHNOLOGIYA",
        "Rate of penetration",
        "m/h",
        [12.0, 13.0],
    )

    match = DrillingInputResolver().resolve_dataset(dataset, targets=("ROP",)).require("ROP")

    assert match.source_mnemonic == "VENDOR_ROP"
    assert match.matched_by == "equivalent_duplicate"
    assert "VENDOR_ROP_TEHNOLOGIYA" in " ".join(match.evidence)


def test_different_duplicate_channels_remain_ambiguous() -> None:
    dataset = _dataset()
    _add_curve(dataset, "VENDOR_ROP", "Rate of penetration", "m/h", [12.0, 13.0])
    _add_curve(
        dataset,
        "VENDOR_ROP_TEHNOLOGIYA",
        "Rate of penetration",
        "m/h",
        [12.0, 18.0],
    )

    resolution = DrillingInputResolver().resolve_dataset(dataset, targets=("ROP",))

    with pytest.raises(ParameterResolutionError, match="неоднозначно"):
        resolution.require("ROP")


def test_bit_sections_are_converted_and_aligned_by_depth() -> None:
    depth = np.array([0.0, 100.0, 149.9, 150.0, 200.0])
    sections = (
        DepthValueSection(0.0, 150.0, 215.9, "mm", "первая секция"),
        DepthValueSection(150.0, 200.0, 6.125, "in", "вторая секция"),
    )

    result = build_section_values(depth, sections, target_unit="in")

    np.testing.assert_allclose(result[:3], 8.5, rtol=0.0, atol=1.0e-10)
    np.testing.assert_allclose(result[3:], 6.125, rtol=0.0, atol=1.0e-10)


def test_bit_sections_reject_gaps() -> None:
    depth = np.array([0.0, 100.0, 150.0, 200.0])
    sections = (
        DepthValueSection(0.0, 100.0, 215.9, "mm"),
        DepthValueSection(150.0, 200.0, 155.6, "mm"),
    )

    with pytest.raises(ValueError, match="не покрывает"):
        build_section_values(depth, sections, target_unit="in")


def test_manual_sections_feed_normalized_gas_and_dexp() -> None:
    depth = np.arange(1000.0, 1030.0, dtype=np.float64)
    dataset = _dataset(depth)
    base = np.linspace(1.0, 3.0, depth.size)
    for mnemonic, scale in (
        ("C1", 1.0),
        ("C2", 0.2),
        ("C3", 0.1),
        ("C4", 0.05),
        ("C5", 0.02),
    ):
        _add_curve(dataset, mnemonic, mnemonic, "%", base * scale)

    session = ProjectSession()
    session.add_dataset(dataset)
    controller = InterpretationCalculationController(session)
    controller.set_drilling_input_plan(
        DrillingInputPlan(
            rop=ParameterSource(InputSourceMode.CONSTANT, value=30.0, unit="m/h"),
            flow=ParameterSource(InputSourceMode.CONSTANT, value=1000.0, unit="L/min"),
            rpm=ParameterSource(InputSourceMode.CONSTANT, value=120.0, unit="1/min"),
            wob=ParameterSource(InputSourceMode.CONSTANT, value=10.0, unit="t"),
            bit=ParameterSource(InputSourceMode.SECTIONS),
            bit_sections=(
                DepthValueSection(1000.0, 1015.0, 215.9, "mm"),
                DepthValueSection(1015.0, 1029.0, 155.6, "mm"),
            ),
        )
    )

    result = controller.calculate_standard_curves(
        normalized_gas_reference=NormalizedGasReference(),
    )

    assert dataset.curve_by_mnemonic("TG_NORM_CALC") is not None
    assert dataset.curve_by_mnemonic("DEXP") is not None
    assert "TG_NORM_CALC" in result.track_curves["normalized_gas"]
    assert "DEXP" in result.track_curves["dexp"]
