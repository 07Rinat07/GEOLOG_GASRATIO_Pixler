"""INTERP-PETRO-01: reproducible physical equations, explicit assumptions."""

from dataclasses import FrozenInstanceError
from math import inf, nan, sqrt

import pytest

from geoworkbench.services.petrophysical_reference_models import (
    PetrophysicalQuality,
    archie_water_saturation,
    density_porosity,
    gamma_ray_index,
)


def test_igr_uses_local_calibration_and_keeps_raw_fraction() -> None:
    result = gamma_ray_index(
        gamma_api=65.0, clean_reference_api=25.0, shale_reference_api=125.0,
    )
    assert result.method_id == "igr-linear-1"
    assert result.value == pytest.approx(0.4)
    assert result.unit == "v/v"
    assert result.quality is PetrophysicalQuality.VALID
    assert result.usable_as_fraction
    assert dict(result.parameters)["clean_reference_api"] == 25.0


@pytest.mark.parametrize(("gr", "expected"), ((5.0, -0.2), (145.0, 1.2)))
def test_igr_keeps_outside_reference_measurements_without_clipping(gr, expected) -> None:
    result = gamma_ray_index(
        gamma_api=gr, clean_reference_api=25.0, shale_reference_api=125.0,
    )
    assert result.value == pytest.approx(expected)
    assert result.quality is PetrophysicalQuality.OUTSIDE_REFERENCE_RANGE
    assert not result.usable_as_fraction


@pytest.mark.parametrize(
    ("gamma", "clean", "shale"),
    ((nan, 25.0, 125.0), (inf, 25.0, 125.0), (65.0, 125.0, 25.0),
     (65.0, 25.0, 25.0), (65.0, nan, 125.0), (65.0, 25.0, inf)),
)
def test_igr_rejects_unknown_or_invalid_endpoints(gamma, clean, shale) -> None:
    with pytest.raises(ValueError):
        gamma_ray_index(
            gamma_api=gamma, clean_reference_api=clean, shale_reference_api=shale,
        )


def test_density_porosity_is_raw_and_matrix_is_explicit() -> None:
    result = density_porosity(
        bulk_density_g_cm3=2.42, matrix_density_g_cm3=2.71,
        fluid_density_g_cm3=1.0,
    )
    assert result.method_id == "density-porosity-1"
    assert result.value == pytest.approx((2.71 - 2.42) / (2.71 - 1.0))
    assert result.quality is PetrophysicalQuality.VALID
    assert dict(result.parameters)["matrix_density_g_cm3"] == 2.71
    assert result.usable_as_fraction


def test_dense_rock_retains_negative_unusable_density_porosity() -> None:
    result = density_porosity(
        bulk_density_g_cm3=2.9, matrix_density_g_cm3=2.71,
        fluid_density_g_cm3=1.0,
    )
    assert result.value < 0.0
    assert result.quality is PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE
    assert not result.usable_as_fraction


@pytest.mark.parametrize(("bulk", "matrix", "fluid"), (
    (nan, 2.71, 1.0), (2.4, inf, 1.0), (2.4, 2.71, 0.0),
    (2.4, 1.0, 1.0), (2.4, 1.0, 2.0), (0.0, 2.71, 1.0),
))
def test_density_porosity_rejects_invalid_inputs(bulk, matrix, fluid) -> None:
    with pytest.raises(ValueError):
        density_porosity(
            bulk_density_g_cm3=bulk, matrix_density_g_cm3=matrix,
            fluid_density_g_cm3=fluid,
        )


def _archie(**changes: float):
    params = {
        "porosity_fraction": 0.2,
        "true_resistivity_ohm_m": 10.0,
        "formation_water_resistivity_ohm_m": 0.1,
        "tortuosity_factor": 1.0,
        "cementation_exponent": 2.0,
        "saturation_exponent": 2.0,
    }
    params.update(changes)
    return archie_water_saturation(**params)


def test_archie_matches_published_equation_with_explicit_coefficients() -> None:
    result = _archie()
    assert result.method_id == "archie-water-saturation-1"
    assert result.value == pytest.approx(sqrt(0.1 / (0.2**2 * 10.0)))
    assert result.value == pytest.approx(0.5)
    assert result.quality is PetrophysicalQuality.VALID
    assert result.usable_as_fraction
    assert len(result.parameters) == 6


def test_archie_keeps_unphysical_sw_above_one_visible() -> None:
    result = _archie(
        porosity_fraction=0.1,
        true_resistivity_ohm_m=2.0,
        formation_water_resistivity_ohm_m=0.2,
    )
    assert result.value > 1.0
    assert result.quality is PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE
    assert not result.usable_as_fraction


@pytest.mark.parametrize(("parameter", "value"), (
    ("porosity_fraction", 0.0), ("porosity_fraction", 1.2),
    ("true_resistivity_ohm_m", -1.0), ("formation_water_resistivity_ohm_m", nan),
    ("formation_water_resistivity_ohm_m", 0.0), ("tortuosity_factor", 0.0),
    ("cementation_exponent", inf), ("saturation_exponent", 0.0),
))
def test_archie_rejects_missing_or_nonphysical_parameters(parameter, value) -> None:
    with pytest.raises(ValueError):
        _archie(**{parameter: value})


def test_no_default_coefficients_and_immutable_result() -> None:
    with pytest.raises(TypeError):
        archie_water_saturation(
            porosity_fraction=0.2,
            true_resistivity_ohm_m=10.0,
            formation_water_resistivity_ohm_m=0.1,
        )
    result = _archie()
    with pytest.raises(FrozenInstanceError):
        result.value = 0.01  # type: ignore[misc]


def test_non_numeric_and_boolean_inputs_fail_closed() -> None:
    with pytest.raises(ValueError):
        gamma_ray_index(
            gamma_api=True, clean_reference_api=25.0,
            shale_reference_api=125.0,
        )
    with pytest.raises(ValueError):
        density_porosity(
            bulk_density_g_cm3=2.45,
            matrix_density_g_cm3=2.71,
            fluid_density_g_cm3=float("nan"),
        )
