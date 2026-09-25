from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from geoworkbench.calculations.pixler import (
    FormulaCategory,
    FormulaProfile,
    FormulaProfileRegistry,
    build_all_sourced_formula_registry,
)
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset
from geoworkbench.services.las_parameter_resolver import (
    DatasetParameterResolution,
    LasParameterResolver,
    concentration_scale_to_percent,
)
from geoworkbench.services.uom_dictionary import (
    UomDictionary,
    default_uom_dictionary,
)


class Wits0DerivedChannelStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class Wits0DerivedUnavailableReason(StrEnum):
    MISSING_INPUT = "missing_input"
    AMBIGUOUS_INPUT = "ambiguous_input"
    UNSUPPORTED_UNIT = "unsupported_unit"
    NO_VALID_SAMPLES = "no_valid_samples"


@dataclass(frozen=True, slots=True)
class Wits0DerivedChannelSnapshot:
    """Read-only derived-channel result for one sourced formula profile."""

    mnemonic: str
    unit: str
    profile_id: str
    profile_version: str
    category: FormulaCategory
    required_inputs: tuple[str, ...]
    description: str
    provenance: str
    status: Wits0DerivedChannelStatus
    values: tuple[float, ...] = ()
    unavailable_reason: Wits0DerivedUnavailableReason | None = None
    unavailable_inputs: tuple[str, ...] = ()
    input_conversions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _InputBinding:
    source_mnemonic: str
    target_unit: str | None = None
    concentration_percent: bool = False


_GAS_COMPONENTS = frozenset({"C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5"})
_ENGINEERING_INPUTS: dict[str, _InputBinding] = {
    "ROP_FPH": _InputBinding("ROP", "ft/h"),
    "RPM": _InputBinding("RPM", "1/min"),
    "WOB_LBF": _InputBinding("WOB", "lbf"),
    "BIT_IN": _InputBinding("BIT", "in"),
}
_SUPPORTED_D_EXPONENT_PROFILE_IDS = frozenset({"dexp.jorden_shirley"})


class Wits0LiveDerivedChannelService:
    """Project sourced formula profiles onto a WITS Dataset without mutating it."""

    def __init__(
        self,
        *,
        registry: FormulaProfileRegistry | None = None,
        resolver: LasParameterResolver | None = None,
        uom_dictionary: UomDictionary | None = None,
    ) -> None:
        self._registry = registry or build_all_sourced_formula_registry()
        self._resolver = resolver or LasParameterResolver()
        self._uom_dictionary = uom_dictionary or default_uom_dictionary()

    def snapshot(self, dataset: Dataset) -> tuple[Wits0DerivedChannelSnapshot, ...]:
        profiles = tuple(
            profile
            for profile in self._registry.available()
            if self._supports_profile(profile)
        )
        targets = tuple(
            dict.fromkeys(
                self._binding(input_mnemonic).source_mnemonic
                for profile in profiles
                for input_mnemonic in profile.required_inputs
            )
        )
        resolution = self._resolver.resolve_dataset(dataset, targets=targets)
        return tuple(
            self._snapshot_profile(profile, resolution)
            for profile in profiles
        )

    def virtual_curves(self, dataset: Dataset) -> dict[str, CurveData]:
        """Materialize available results as ephemeral curves for live projection only."""

        output: dict[str, CurveData] = {}
        for snapshot in self.snapshot(dataset):
            if snapshot.status is not Wits0DerivedChannelStatus.AVAILABLE:
                continue
            curve_id = self.virtual_curve_id(snapshot)
            provenance = snapshot.provenance
            if snapshot.input_conversions:
                provenance += ";uom=" + ",".join(snapshot.input_conversions)
            output[curve_id] = CurveData(
                CurveMetadata(
                    curve_id=curve_id,
                    original_mnemonic=snapshot.mnemonic,
                    canonical_mnemonic=snapshot.mnemonic,
                    unit=snapshot.unit,
                    description=snapshot.description,
                    source_dataset_id=dataset.dataset_id,
                    provenance=provenance,
                ),
                np.asarray(snapshot.values, dtype=np.float64),
            )
        return output

    @staticmethod
    def virtual_curve_id(snapshot: Wits0DerivedChannelSnapshot) -> str:
        return (
            f"wits-derived:{snapshot.profile_id}:{snapshot.profile_version}"
        )

    def _snapshot_profile(
        self,
        profile: FormulaProfile,
        resolution: DatasetParameterResolution,
    ) -> Wits0DerivedChannelSnapshot:
        required = tuple(name.upper() for name in profile.required_inputs)
        bindings = {
            input_name: self._binding(input_name)
            for input_name in required
        }

        ambiguous = tuple(
            input_name
            for input_name, binding in bindings.items()
            if binding.source_mnemonic in resolution.ambiguities
        )
        if ambiguous:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.AMBIGUOUS_INPUT,
                ambiguous,
            )

        missing = tuple(
            input_name
            for input_name, binding in bindings.items()
            if resolution.get(binding.source_mnemonic) is None
        )
        if missing:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.MISSING_INPUT,
                missing,
            )

        inputs: dict[str, np.ndarray] = {}
        conversions: list[str] = []
        unsupported_units: list[str] = []
        for input_name, binding in bindings.items():
            match = resolution.get(binding.source_mnemonic)
            assert match is not None
            values = np.asarray(match.curve.values, dtype=np.float64)
            if binding.concentration_percent:
                scale = concentration_scale_to_percent(match.unit)
                if scale is None:
                    unsupported_units.append(input_name)
                    continue
                inputs[input_name] = values * scale
                conversions.append(
                    f"{input_name}:{match.unit or '<missing>'}->%"
                )
                continue

            target_unit = binding.target_unit
            if target_unit is None:
                inputs[input_name] = values
                conversions.append(
                    f"{input_name}:{match.unit or '<missing>'}->unchanged"
                )
                continue

            conversion = self._uom_dictionary.conversion(match.unit, target_unit)
            if conversion is None:
                unsupported_units.append(input_name)
                continue
            inputs[input_name] = conversion.convert_array(values)
            conversions.append(
                f"{input_name}:{conversion.source_uom}->{conversion.target_uom}"
            )

        if unsupported_units:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.UNSUPPORTED_UNIT,
                tuple(unsupported_units),
                input_conversions=tuple(conversions),
            )

        values = self._registry.calculate(profile.profile_id, inputs)
        if values.size == 0 or not np.any(np.isfinite(values)):
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.NO_VALID_SAMPLES,
                (),
                input_conversions=tuple(conversions),
            )

        return Wits0DerivedChannelSnapshot(
            mnemonic=profile.output_mnemonic,
            unit=profile.output_unit,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            category=profile.category,
            required_inputs=required,
            description=profile.description,
            provenance=self._provenance(profile),
            status=Wits0DerivedChannelStatus.AVAILABLE,
            values=tuple(float(value) for value in values),
            input_conversions=tuple(conversions),
        )

    @staticmethod
    def _supports_profile(profile: FormulaProfile) -> bool:
        if profile.category in {FormulaCategory.FLUID, FormulaCategory.PIXLER}:
            return True
        return profile.profile_id in _SUPPORTED_D_EXPONENT_PROFILE_IDS

    @staticmethod
    def _binding(input_name: str) -> _InputBinding:
        normalized = input_name.upper()
        if normalized in _GAS_COMPONENTS:
            return _InputBinding(
                source_mnemonic=normalized,
                target_unit="%",
                concentration_percent=True,
            )
        try:
            return _ENGINEERING_INPUTS[normalized]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported WITS derived formula input: {normalized}"
            ) from exc

    @staticmethod
    def _unavailable(
        profile: FormulaProfile,
        reason: Wits0DerivedUnavailableReason,
        inputs: tuple[str, ...],
        *,
        input_conversions: tuple[str, ...] = (),
    ) -> Wits0DerivedChannelSnapshot:
        return Wits0DerivedChannelSnapshot(
            mnemonic=profile.output_mnemonic,
            unit=profile.output_unit,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            category=profile.category,
            required_inputs=tuple(name.upper() for name in profile.required_inputs),
            description=profile.description,
            provenance=Wits0LiveDerivedChannelService._provenance(profile),
            status=Wits0DerivedChannelStatus.UNAVAILABLE,
            unavailable_reason=reason,
            unavailable_inputs=inputs,
            input_conversions=input_conversions,
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
