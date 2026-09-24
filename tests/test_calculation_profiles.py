from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from geoworkbench.calculations.calculation_profiles import (
    GasRatioCalculationProfile,
    available_gas_ratio_profiles,
    default_gas_ratio_profile,
    resolve_gas_ratio_profile,
)
from geoworkbench.calculations.gas_conditioning import GasConditioningPolicy
from geoworkbench.calculations.gas_ratio import calculate_conditioned_ratios


def _components(depth: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "C1": np.full(depth.shape, 80.0),
        "C2": np.full(depth.shape, 10.0),
        "C3": np.full(depth.shape, 5.0),
        "IC4": np.full(depth.shape, 1.0),
        "NC4": np.full(depth.shape, 2.0),
        "IC5": np.full(depth.shape, 1.0),
        "NC5": np.full(depth.shape, 1.0),
    }


def test_default_gas_ratio_profile_is_versioned_and_immutable() -> None:
    profile = default_gas_ratio_profile()

    assert profile.profile_id == "conditioned-gas-ratio"
    assert profile.version == "2.0"
    assert profile.provenance == "calculation:conditioned-gas-ratio:2.0"
    assert profile.profile_key == "conditioned-gas-ratio@2.0"
    assert profile.conditioning_policy.policy_id == "bounded-gap-continuity"
    assert profile.conditioning_policy.version == "1.0"
    assert profile.conditioning_key == "bounded-gap-continuity@1.0"
    assert available_gas_ratio_profiles() == (profile,)

    with pytest.raises(FrozenInstanceError):
        profile.version = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        profile.conditioning_policy.version = "changed"  # type: ignore[misc]


def test_gas_ratio_profile_requires_conditioning_policy_dto() -> None:
    source = default_gas_ratio_profile()

    with pytest.raises(ValueError, match="conditioning_policy"):
        GasRatioCalculationProfile(
            profile_id=source.profile_id,
            display_name=source.display_name,
            version=source.version,
            conditioning_policy=object(),  # type: ignore[arg-type]
        )


def test_gas_ratio_profile_resolver_is_version_exact() -> None:
    profile = default_gas_ratio_profile()

    assert resolve_gas_ratio_profile(profile.profile_id) is profile
    assert resolve_gas_ratio_profile(profile.profile_id, version=profile.version) is profile

    with pytest.raises(KeyError, match="Неизвестный профиль расчёта"):
        resolve_gas_ratio_profile(profile.profile_id, version="999.0")
    with pytest.raises(KeyError, match="Неизвестный профиль расчёта"):
        resolve_gas_ratio_profile("missing-profile")


@pytest.mark.parametrize(
    "changes",
    (
        {"profile_id": "Invalid ID"},
        {"display_name": ""},
        {"version": " "},
    ),
)
def test_gas_ratio_profile_rejects_invalid_identity(changes: dict[str, object]) -> None:
    source = default_gas_ratio_profile()
    values = {
        "profile_id": source.profile_id,
        "display_name": source.display_name,
        "version": source.version,
        "conditioning_policy": source.conditioning_policy,
    }
    values.update(changes)

    with pytest.raises(ValueError):
        GasRatioCalculationProfile(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    (
        {"policy_id": ""},
        {"policy_id": " bounded-gap-continuity"},
        {"version": ""},
        {"version": " 1.0"},
    ),
)
def test_conditioning_policy_rejects_invalid_version_identity(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "policy_id": "bounded-gap-continuity",
        "version": "1.0",
    }
    values.update(changes)

    with pytest.raises(ValueError):
        GasConditioningPolicy(**values)  # type: ignore[arg-type]


def test_conditioned_calculation_returns_exact_selected_profile_snapshot() -> None:
    depth = np.arange(1000.0, 1005.0)
    base = default_gas_ratio_profile()
    selected = replace(
        base,
        profile_id="conditioned-gas-ratio-audit",
        version="2.1",
        conditioning_policy=replace(
            base.conditioning_policy,
            policy_id="bounded-gap-audit",
            version="1.1",
            max_gap_steps=2.0,
        ),
    )

    result = calculate_conditioned_ratios(
        depth,
        _components(depth),
        profile=selected,
    )

    assert result.profile is selected
    assert result.profile.profile_key == "conditioned-gas-ratio-audit@2.1"
    assert result.profile.conditioning_key == "bounded-gap-audit@1.1"
    assert "TG_CALC" in result.curves


def test_conditioned_calculation_rejects_profile_and_policy_together() -> None:
    depth = np.arange(1000.0, 1005.0)

    with pytest.raises(ValueError, match="не оба"):
        calculate_conditioned_ratios(
            depth,
            _components(depth),
            profile=default_gas_ratio_profile(),
            policy=GasConditioningPolicy(),
        )


def test_low_level_policy_override_is_reflected_in_result_profile() -> None:
    depth = np.arange(1000.0, 1005.0)
    override = GasConditioningPolicy(
        max_gap_steps=2.0,
        policy_id="test-policy",
        version="9.0",
    )

    result = calculate_conditioned_ratios(
        depth,
        _components(depth),
        policy=override,
    )

    assert result.profile.conditioning_policy is override
    assert result.profile.conditioning_key == "test-policy@9.0"
