from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from geoworkbench.calculations.pixler import (
    FormulaCategory,
    FormulaProfile,
    FormulaProfileRegistry,
    build_sourced_formula_registry,
)
from geoworkbench.domain.models import Dataset
from geoworkbench.services.las_parameter_resolver import (
    LasParameterResolver,
    concentration_scale_to_percent,
)


class Wits0DerivedChannelStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class Wits0DerivedUnavailableReason(StrEnum):
    MISSING_INPUT = "missing_input"
    AMBIGUOUS_INPUT = "ambiguous_input"
    UNSUPPORTED_UNIT = "unsupported_unit"


@dataclass(frozen=True, slots=True)
class Wits0DerivedChannelSnapshot:
    """Read-only derived-channel result for one sourced formula profile."""

    mnemonic: str
    unit: str
    profile_id: str
    profile_version: str
    category: FormulaCategory
    required_inputs: tuple[str, ...]
    provenance: str
    status: Wits0DerivedChannelStatus
    values: tuple[float, ...] = ()
    unavailable_reason: Wits0DerivedUnavailableReason | None = None
    unavailable_inputs: tuple[str, ...] = ()


class Wits0LiveDerivedChannelService:
    """Project sourced formula profiles onto a WITS Dataset without mutating it."""

    def __init__(
        self,
        *,
        registry: FormulaProfileRegistry | None = None,
        resolver: LasParameterResolver | None = None,
    ) -> None:
        self._registry = registry or build_sourced_formula_registry()
        self._resolver = resolver or LasParameterResolver()

    def snapshot(self, dataset: Dataset) -> tuple[Wits0DerivedChannelSnapshot, ...]:
        profiles = tuple(
            profile
            for profile in self._registry.available()
            if profile.category in {FormulaCategory.FLUID, FormulaCategory.PIXLER}
        )
        targets = tuple(
            dict.fromkeys(
                input_mnemonic.upper()
                for profile in profiles
                for input_mnemonic in profile.required_inputs
            )
        )
        resolution = self._resolver.resolve_dataset(dataset, targets=targets)
        output: list[Wits0DerivedChannelSnapshot] = []
        for profile in profiles:
            output.append(self._snapshot_profile(profile, resolution))
        return tuple(output)

    def _snapshot_profile(
        self,
        profile: FormulaProfile,
        resolution,  # type: ignore[no-untyped-def]
    ) -> Wits0DerivedChannelSnapshot:
        required = tuple(name.upper() for name in profile.required_inputs)
        ambiguous = tuple(name for name in required if name in resolution.ambiguities)
        if ambiguous:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.AMBIGUOUS_INPUT,
                ambiguous,
            )

        missing = tuple(name for name in required if resolution.get(name) is None)
        if missing:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.MISSING_INPUT,
                missing,
            )

        inputs: dict[str, np.ndarray] = {}
        unsupported_units: list[str] = []
        for name in required:
            match = resolution.get(name)
            assert match is not None
            scale = concentration_scale_to_percent(match.unit)
            if scale is None:
                unsupported_units.append(name)
                continue
            inputs[name] = np.asarray(match.curve.values, dtype=np.float64) * scale
        if unsupported_units:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.UNSUPPORTED_UNIT,
                tuple(unsupported_units),
            )

        values = self._registry.calculate(profile.profile_id, inputs)
        return Wits0DerivedChannelSnapshot(
            mnemonic=profile.output_mnemonic,
            unit=profile.output_unit,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            category=profile.category,
            required_inputs=required,
            provenance=self._provenance(profile),
            status=Wits0DerivedChannelStatus.AVAILABLE,
            values=tuple(float(value) for value in values),
        )

    @staticmethod
    def _unavailable(
        profile: FormulaProfile,
        reason: Wits0DerivedUnavailableReason,
        inputs: tuple[str, ...],
    ) -> Wits0DerivedChannelSnapshot:
        return Wits0DerivedChannelSnapshot(
            mnemonic=profile.output_mnemonic,
            unit=profile.output_unit,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            category=profile.category,
            required_inputs=tuple(name.upper() for name in profile.required_inputs),
            provenance=Wits0LiveDerivedChannelService._provenance(profile),
            status=Wits0DerivedChannelStatus.UNAVAILABLE,
            unavailable_reason=reason,
            unavailable_inputs=inputs,
        )

    @staticmethod
    def _provenance(profile: FormulaProfile) -> str:
        return f"formula:{profile.profile_id}:{profile.version}"


__all__ = [
    "Wits0DerivedChannelSnapshot",
    "Wits0DerivedChannelStatus",
    "Wits0DerivedUnavailableReason",
    "Wits0LiveDerivedChannelService",
]
