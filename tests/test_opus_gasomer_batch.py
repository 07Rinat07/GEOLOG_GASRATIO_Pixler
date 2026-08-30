from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.gas_ratio import calculate_opus_screening
from geoworkbench.calculations.opus_gasomer import (
    OPUS_GASOMER_INDICATORS,
    OpusGasomerValueState,
    calculate_opus_gasomer_batch,
    calculate_opus_gasomer_row,
)


def _control_inputs(scale: float = 1.0) -> dict[str, np.ndarray]:
    return {
        "C1": np.array([3.0, 3.3]) * scale,
        "C2": np.array([2.0, 1.8]) * scale,
        "C3": np.array([1.0, 0.9]) * scale,
        "C4": np.array([1.0, 0.7]) * scale,
        "C5": np.array([1.0, 0.4]) * scale,
        "TOTAL_GAS": np.array([9.0, 8.0]) * scale,
    }


def _lod(scale: float = 1.0) -> dict[str, float]:
    return {
        "C1": 0.01 * scale,
        "C2": 0.01 * scale,
        "C3": 0.01 * scale,
        "C4": 0.01 * scale,
        "C5": 0.01 * scale,
        "TOTAL_GAS": 0.01 * scale,
    }


def test_ppm_and_percent_batches_are_numerically_identical() -> None:
    percent = calculate_opus_gasomer_batch(
        _control_inputs(),
        units="%vol",
        lod=_lod(),
    )
    ppm = calculate_opus_gasomer_batch(
        _control_inputs(10_000.0),
        units="ppm",
        lod=_lod(10_000.0),
    )

    assert not percent.warnings
    assert not ppm.warnings
    for name in ("C1", "C2", "C3", "C4", "C5"):
        np.testing.assert_allclose(
            percent.normalized_percent[name],
            ppm.normalized_percent[name],
            rtol=0.0,
            atol=1e-13,
        )
        np.testing.assert_array_equal(percent.input_states[name], ppm.input_states[name])
    for name in OPUS_GASOMER_INDICATORS:
        np.testing.assert_allclose(
            percent.indicators[name].values,
            ppm.indicators[name].values,
            rtol=2e-15,
            equal_nan=True,
        )
        np.testing.assert_array_equal(
            percent.indicators[name].class_codes,
            ppm.indicators[name].class_codes,
        )
    np.testing.assert_array_equal(percent.row_votes, ppm.row_votes)
    np.testing.assert_array_equal(percent.row_class_codes, ppm.row_class_codes)


def test_batch_reproduces_scalar_primary_workbook_control() -> None:
    inputs = {name: values[:1] for name, values in _control_inputs().items()}
    batch = calculate_opus_gasomer_batch(inputs, lod=_lod())
    scalar = calculate_opus_gasomer_row(3.0, 2.0, 1.0, 1.0, 1.0, 9.0)

    np.testing.assert_allclose(
        [batch.normalized_percent[name][0] for name in ("C1", "C2", "C3", "C4", "C5")],
        scalar.normalized_percent,
        rtol=0.0,
        atol=1e-13,
    )
    np.testing.assert_allclose(
        [batch.indicators[name].values[0] for name in OPUS_GASOMER_INDICATORS],
        scalar.indicator_values,
        rtol=2e-15,
    )
    assert tuple(int(value) for value in batch.row_votes[0]) == scalar.indicator_votes
    assert int(batch.row_class_codes[0]) == scalar.class_code


def test_independent_total_gas_is_never_replaced_by_component_sum() -> None:
    inputs = {name: values[:1] for name, values in _control_inputs().items()}
    independent = calculate_opus_gasomer_batch(inputs, lod=_lod())
    component_sum = sum(inputs[name] for name in ("C1", "C2", "C3", "C4", "C5"))
    substituted = calculate_opus_gasomer_batch(
        {**inputs, "TOTAL_GAS": component_sum},
        lod=_lod(),
    )

    assert independent.normalized_percent["C1"][0] == pytest.approx(100.0 / 3.0)
    assert substituted.normalized_percent["C1"][0] == pytest.approx(37.5)
    assert independent.indicators["OPUS_GM_3"].values[0] != pytest.approx(
        substituted.indicators["OPUS_GM_3"].values[0]
    )


def test_qc_states_are_kept_per_indicator_dependency() -> None:
    inputs = {
        "C1": np.array([0.30, 0.30, 0.30, 0.30, -0.30]),
        "C2": np.array([0.20, 0.20, 0.00, 0.20, 0.20]),
        "C3": np.array([0.10, 0.10, 0.10, 0.10, 0.10]),
        "C4": np.array([0.08, 0.08, 0.08, 0.005, 0.08]),
        "C5": np.array([0.04, np.nan, 0.04, 0.04, 0.04]),
        "TOTAL_GAS": np.ones(5),
    }
    lod = {name: 0.01 for name in inputs}
    result = calculate_opus_gasomer_batch(inputs, lod=lod)
    available = int(OpusGasomerValueState.AVAILABLE)
    missing = int(OpusGasomerValueState.MISSING)
    zero = int(OpusGasomerValueState.MEASURED_ZERO)
    below_lod = int(OpusGasomerValueState.BELOW_LOD)
    invalid = int(OpusGasomerValueState.INVALID)

    assert result.input_states["C5"].tolist() == [available, missing, available, available, available]
    assert result.input_states["C2"][2] == zero
    assert result.input_states["C4"][3] == below_lod
    assert result.input_states["C1"][4] == invalid
    assert result.indicators["OPUS_GM_1"].states.tolist() == [
        available,
        available,
        zero,
        available,
        invalid,
    ]
    assert result.indicators["OPUS_GM_2"].states.tolist() == [
        available,
        available,
        zero,
        below_lod,
        invalid,
    ]
    assert result.indicators["OPUS_GM_4"].states.tolist() == [
        available,
        missing,
        zero,
        below_lod,
        invalid,
    ]
    assert np.isnan(result.indicators["OPUS_GM_4"].values[1:]).all()
    assert result.valid_vote_counts.tolist() == [5, 3, 0, 2, 0]
    assert result.row_class_codes[2:].tolist() == [7, 7, 7]


@pytest.mark.parametrize(
    ("total_gas", "expected_state"),
    (
        (np.nan, OpusGasomerValueState.MISSING),
        (0.0, OpusGasomerValueState.MEASURED_ZERO),
        (0.005, OpusGasomerValueState.BELOW_LOD),
    ),
)
def test_unusable_total_gas_blocks_every_indicator_with_exact_state(
    total_gas: float,
    expected_state: OpusGasomerValueState,
) -> None:
    inputs = {name: values[:1] for name, values in _control_inputs().items()}
    inputs["TOTAL_GAS"] = np.array([total_gas])
    lod = _lod()
    result = calculate_opus_gasomer_batch(inputs, lod=lod)

    assert result.input_states["TOTAL_GAS"][0] == int(expected_state)
    assert all(
        indicator.states[0] == int(expected_state)
        for indicator in result.indicators.values()
    )
    assert np.isnan(
        np.array([indicator.values[0] for indicator in result.indicators.values()])
    ).all()
    assert int(result.row_class_codes[0]) == 7


def test_value_exactly_at_lod_is_available() -> None:
    inputs = {name: values[:1] for name, values in _control_inputs().items()}
    inputs["C5"] = np.array([0.01])
    result = calculate_opus_gasomer_batch(inputs, lod=_lod())

    assert result.input_states["C5"][0] == int(OpusGasomerValueState.AVAILABLE)
    assert result.indicators["OPUS_GM_5"].available_mask[0]


def test_missing_lod_is_warning_not_a_hidden_threshold() -> None:
    result = calculate_opus_gasomer_batch(_control_inputs())

    assert len(result.warnings) == 6
    assert "LOD metadata missing: TOTAL_GAS" in result.warnings
    assert np.isfinite(result.indicators["OPUS_GM_5"].values).all()


def test_source_arrays_are_not_mutated() -> None:
    inputs = _control_inputs()
    originals = {name: values.copy() for name, values in inputs.items()}

    calculate_opus_gasomer_batch(inputs, lod=_lod())

    for name, original in originals.items():
        np.testing.assert_array_equal(inputs[name], original)


def test_invalid_shape_missing_channel_and_unknown_unit_are_rejected() -> None:
    with pytest.raises(KeyError, match="TOTAL_GAS"):
        calculate_opus_gasomer_batch({k: v for k, v in _control_inputs().items() if k != "TOTAL_GAS"})
    with pytest.raises(ValueError, match="одинаковую длину"):
        calculate_opus_gasomer_batch({**_control_inputs(), "C5": np.array([1.0])})
    with pytest.raises(ValueError, match="Неподдерживаемая единица"):
        calculate_opus_gasomer_batch(_control_inputs(), units="mg/m3")


def test_historical_opus_profile_remains_numerically_unchanged() -> None:
    historical = calculate_opus_screening(
        np.array([98.315]),
        np.array([1.186]),
        np.array([0.206]),
        np.array([0.172]),
        np.array([0.120]),
    )

    np.testing.assert_allclose(historical["OPUS3"].values, [60.18], rtol=2e-4)
    assert "OPUS_GM_5" not in historical
