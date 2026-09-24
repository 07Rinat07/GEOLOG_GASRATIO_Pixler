from __future__ import annotations

from dataclasses import dataclass
import re

from geoworkbench.calculations.gas_conditioning import GasConditioningPolicy


_PROFILE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class GasRatioCalculationProfile:
    """Versioned immutable contract for conditioned gas-ratio calculations."""

    profile_id: str
    display_name: str
    version: str
    conditioning_policy: GasConditioningPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.conditioning_policy, GasConditioningPolicy):
            raise ValueError("conditioning_policy должен быть GasConditioningPolicy")
        if not _PROFILE_ID_PATTERN.fullmatch(self.profile_id):
            raise ValueError(f"Некорректный profile_id: {self.profile_id!r}")
        if not self.display_name.strip() or self.display_name != self.display_name.strip():
            raise ValueError("display_name должен быть непустой нормализованной строкой")
        if not self.version.strip() or self.version != self.version.strip():
            raise ValueError("version должна быть непустой нормализованной строкой")

    @property
    def provenance(self) -> str:
        return f"calculation:{self.profile_id}:{self.version}"

    @property
    def profile_key(self) -> str:
        return f"{self.profile_id}@{self.version}"

    @property
    def conditioning_key(self) -> str:
        policy = self.conditioning_policy
        return f"{policy.policy_id}@{policy.version}"


_DEFAULT_GAS_RATIO_PROFILE = GasRatioCalculationProfile(
    profile_id="conditioned-gas-ratio",
    display_name="Conditioned gas ratio",
    version="2.0",
    conditioning_policy=GasConditioningPolicy(
        policy_id="bounded-gap-continuity",
        version="1.0",
    ),
)


def available_gas_ratio_profiles() -> tuple[GasRatioCalculationProfile, ...]:
    """Return the immutable built-in gas-ratio calculation profile catalog."""

    return (_DEFAULT_GAS_RATIO_PROFILE,)


def default_gas_ratio_profile() -> GasRatioCalculationProfile:
    return _DEFAULT_GAS_RATIO_PROFILE


def resolve_gas_ratio_profile(
    profile_id: str,
    *,
    version: str | None = None,
) -> GasRatioCalculationProfile:
    normalized_id = profile_id.strip()
    normalized_version = version.strip() if version is not None else None
    for profile in available_gas_ratio_profiles():
        if profile.profile_id != normalized_id:
            continue
        if normalized_version is None or profile.version == normalized_version:
            return profile
    suffix = f"@{normalized_version}" if normalized_version else ""
    raise KeyError(f"Неизвестный профиль расчёта: {normalized_id}{suffix}")


__all__ = [
    "GasRatioCalculationProfile",
    "available_gas_ratio_profiles",
    "default_gas_ratio_profile",
    "resolve_gas_ratio_profile",
]
