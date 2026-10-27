from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.services.wits0_live_derived import Wits0DexpCorrectionConfig


@pytest.mark.parametrize(
    "value",
    [9, 9.0, np.int64(9), np.float32(9.5), np.float64(9.5)],
)
def test_explicit_normal_mud_density_accepts_positive_real_scalars(value: object) -> None:
    config = Wits0DexpCorrectionConfig(normal_mud_density=value, unit="kg/m3")
    assert config.normal_mud_density is value
    assert config.unit == "kg/m3"


@pytest.mark.parametrize(
    "value",
    [
        True,
        np.bool_(True),
        "9.0",
        b"9",
        None,
        9 + 0j,
        np.array(9.0),
        np.array([9.0]),
        float("nan"),
        float("inf"),
        -1.0,
        0.0,
        10**1000,
    ],
)
def test_explicit_normal_mud_density_rejects_coercion_and_invalid_values(
    value: object,
) -> None:
    with pytest.raises(ValueError, match="finite positive real scalar"):
        Wits0DexpCorrectionConfig(normal_mud_density=value, unit="kg/m3")


@pytest.mark.parametrize("unit", [None, True, 9, [], {}, "", " \t"])
def test_explicit_normal_mud_density_rejects_non_text_or_blank_unit(
    unit: object,
) -> None:
    with pytest.raises(ValueError, match="unit must be a non-empty string"):
        Wits0DexpCorrectionConfig(normal_mud_density=9.0, unit=unit)


def test_explicit_normal_mud_density_preserves_unsupported_unit_for_qc() -> None:
    # Unit recognition belongs to the existing UOM/QC layer, not this scalar guard.
    config = Wits0DexpCorrectionConfig(
        normal_mud_density=9.0, unit="vendor-density"
    )
    assert config.unit == "vendor-density"
