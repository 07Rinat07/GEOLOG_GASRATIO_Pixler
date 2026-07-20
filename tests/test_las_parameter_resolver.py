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
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.las_parameter_resolver import (
    LasParameterResolver,
    ParameterResolutionError,
    concentration_scale_to_percent,
    infer_canonical_mnemonic,
    resolve_gas_ratio_inputs,
)


def _dataset(*curves: tuple[str, str, str, list[float]]) -> Dataset:
    dataset = Dataset(
        "dataset",
        "Vendor LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    for index, (mnemonic, description, unit, values) in enumerate(curves):
        curve_id = f"curve-{index}"
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                mnemonic,
                mnemonic.upper(),
                unit or None,
                description or None,
                dataset.dataset_id,
            ),
            np.asarray(values, dtype=np.float64),
        )
    return dataset


def test_resolver_ignores_curve_order_and_uses_multilingual_descriptions() -> None:
    dataset = _dataset(
        ("PROP_GAS", "Propane content", "%", [0.2, 0.3]),
        ("S800", "Содержание метана", "%", [1.0, 2.0]),
        ("ETH", "Содержание этана", "%", [0.4, 0.5]),
    )

    resolution = LasParameterResolver().resolve_dataset(dataset, targets=("C1", "C2", "C3"))

    assert resolution.require("C1").source_mnemonic == "S800"
    assert resolution.require("C2").source_mnemonic == "ETH"
    assert resolution.require("C3").source_mnemonic == "PROP_GAS"


def test_resolver_understands_cyrillic_homoglyphs_and_chemical_formulas() -> None:
    dataset = _dataset(
        ("С1", "", "%", [1.0, 1.5]),  # Cyrillic letter С, not Latin C.
        ("C2H6", "", "%", [0.2, 0.3]),
        ("C3H8", "", "%", [0.1, 0.2]),
    )

    resolution = LasParameterResolver().resolve_dataset(dataset, targets=("C1", "C2", "C3"))

    assert resolution.require("C1").canonical_mnemonic == "C1"
    assert resolution.require("C2").canonical_mnemonic == "C2"
    assert resolution.require("C3").canonical_mnemonic == "C3"


def test_gas_inputs_are_converted_to_common_percent_scale() -> None:
    dataset = _dataset(
        ("CH4", "Methane", "ppm", [10_000.0, 20_000.0]),
        ("ETHANE", "Ethane", "%", [0.5, 1.0]),
        ("PROPANE", "Propane", "fraction", [0.002, 0.003]),
    )

    inputs = resolve_gas_ratio_inputs(dataset)

    np.testing.assert_allclose(inputs["C1"], [1.0, 2.0])
    np.testing.assert_allclose(inputs["C2"], [0.5, 1.0])
    np.testing.assert_allclose(inputs["C3"], [0.2, 0.3])


def test_session_calculation_accepts_vendor_aliases() -> None:
    dataset = _dataset(
        ("METH", "Methane content", "%", [10.0, 20.0]),
        ("C2H6", "", "%", [2.0, 4.0]),
        ("PROP_GAS", "Содержание пропана", "%", [1.0, 2.0]),
    )
    session = ProjectSession()
    session.add_dataset(dataset)

    created = session.calculate_basic_gas_ratios()

    assert "C1_C2" in created
    ratio = dataset.curve_by_mnemonic("C1_C2")
    total = dataset.curve_by_mnemonic("TG_CALC")
    assert ratio is not None
    assert total is not None
    np.testing.assert_allclose(ratio.values, [5.0, 5.0])
    np.testing.assert_allclose(total.values, [13.0, 26.0])


def test_resolver_blocks_equal_confidence_duplicate_channels() -> None:
    dataset = _dataset(
        ("C1", "Methane primary", "%", [1.0, 2.0]),
        ("CH4", "Methane backup", "%", [1.1, 2.1]),
        ("C2", "Ethane", "%", [0.2, 0.3]),
        ("C3", "Propane", "%", [0.1, 0.2]),
    )

    resolution = LasParameterResolver().resolve_dataset(dataset, targets=("C1", "C2", "C3"))

    with pytest.raises(ParameterResolutionError, match="неоднозначно"):
        resolution.require("C1")


def test_user_mapping_resolves_duplicate_channel_conflict() -> None:
    dataset = _dataset(
        ("C1", "Methane primary", "%", [1.0, 2.0]),
        ("CH4", "Methane backup", "%", [1.1, 2.1]),
    )
    selected_id = "curve-1"

    resolution = LasParameterResolver().resolve_dataset(
        dataset,
        targets=("C1",),
        user_mappings={selected_id: "C1"},
    )

    assert resolution.require("C1").curve_id == selected_id
    assert resolution.require("C1").matched_by == "user_mapping"


def test_mixed_unknown_nonempty_units_are_rejected() -> None:
    dataset = _dataset(
        ("C1", "", "custom-a", [1.0, 2.0]),
        ("C2", "", "custom-b", [0.2, 0.3]),
        ("C3", "", "custom-a", [0.1, 0.2]),
    )

    with pytest.raises(ParameterResolutionError, match="несовместимые неизвестные единицы"):
        resolve_gas_ratio_inputs(dataset)


def test_import_inference_returns_none_for_unknown_curve() -> None:
    assert infer_canonical_mnemonic("CHANNEL_900", description="Vendor diagnostic") is None


def test_concentration_unit_scales() -> None:
    assert concentration_scale_to_percent("%") == 1.0
    assert concentration_scale_to_percent("ppmv") == pytest.approx(1.0e-4)
    assert concentration_scale_to_percent("ppb") == pytest.approx(1.0e-7)
    assert concentration_scale_to_percent("fraction") == 100.0
    assert concentration_scale_to_percent("m/h") is None
