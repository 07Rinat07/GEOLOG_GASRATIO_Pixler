from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.drilling_mode import (
    DrillingModeCode,
    classify_drilling_modes,
    resolve_bit_rpm_curve,
)


def _add_curve(dataset: Dataset, mnemonic: str, values: np.ndarray, unit: str) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            curve_id=mnemonic,
            original_mnemonic=mnemonic,
            canonical_mnemonic=mnemonic,
            unit=unit,
            description=mnemonic,
            source_dataset_id=dataset.dataset_id,
        ),
        np.asarray(values, dtype=np.float64),
    )


def test_classify_drilling_modes_uses_downhole_rpm_only_during_slide() -> None:
    rop = np.array([50.0, 50.0, 0.0, 50.0])
    surface_rpm = np.array([100.0, 0.0, 0.0, np.nan])
    wob = np.full(4, 40_000.0)
    flow = np.full(4, 500.0)
    bit_rpm = np.array([np.nan, 150.0, 150.0, 150.0])

    result = classify_drilling_modes(
        rop,
        surface_rpm,
        wob,
        flow=flow,
        bit_rpm=bit_rpm,
    )

    np.testing.assert_array_equal(
        result.mode_codes,
        [
            DrillingModeCode.ROTARY,
            DrillingModeCode.SLIDE,
            DrillingModeCode.NOT_DRILLING,
            DrillingModeCode.UNKNOWN,
        ],
    )
    np.testing.assert_allclose(result.effective_rpm[:2], [100.0, 150.0])
    assert np.isnan(result.effective_rpm[2])
    assert np.isnan(result.effective_rpm[3])
    assert result.slide_points == 1
    assert result.slide_points_with_bit_rpm == 1
    assert result.slide_points_without_bit_rpm == 0


def test_classify_drilling_modes_does_not_guess_slide_without_flow() -> None:
    result = classify_drilling_modes(
        np.array([50.0]),
        np.array([0.0]),
        np.array([40_000.0]),
    )

    assert result.mode_codes[0] == DrillingModeCode.UNKNOWN
    assert result.slide_points == 0
    assert np.isnan(result.effective_rpm[0])
    assert not result.repairable_mask[0]


def test_resolve_bit_rpm_curve_does_not_reuse_surface_rpm() -> None:
    depth = np.arange(4.0)
    dataset = Dataset(
        "mode-rpm",
        "Mode RPM",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    _add_curve(dataset, "RPM", np.full(4, 100.0), "rpm")
    _add_curve(dataset, "MOTOR_RPM", np.full(4, 160.0), "rpm")

    values, mnemonic = resolve_bit_rpm_curve(dataset)

    assert mnemonic == "MOTOR_RPM"
    assert values is not None
    np.testing.assert_allclose(values, 160.0)
