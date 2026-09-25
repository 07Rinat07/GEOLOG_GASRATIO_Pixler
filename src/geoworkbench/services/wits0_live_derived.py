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
from geoworkbench.services.drilling_mode import (
    classify_drilling_modes,
    resolve_bit_rpm_curve,
)
from geoworkbench.services.las_parameter_resolver import (
    DatasetParameterResolution,
    LasParameterResolver,
    ParameterMatch,
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
    MISSING_CONFIGURATION = "missing_configuration"
    AMBIGUOUS_INPUT = "ambiguous_input"
    UNSUPPORTED_UNIT = "unsupported_unit"
    NO_VALID_SAMPLES = "no_valid_samples"


@dataclass(frozen=True, slots=True)
class Wits0DexpCorrectionConfig:
    """Explicit operator/configuration input required for corrected DEXP."""

    normal_mud_density: float
    unit: str

    def __post_init__(self) -> None:
        value = float(self.normal_mud_density)
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError("normal_mud_density must be a finite positive value")
        if not self.unit.strip():
            raise ValueError("normal mud density unit must be non-empty")


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
    source_record_numbers: tuple[int, ...] = ()


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
_BASE_DEXP_PROFILE_ID = "dexp.jorden_shirley"
_CORRECTED_DEXP_PROFILE_ID = "dexp.rehm_mcclendon_corrected"
_SUPPORTED_D_EXPONENT_PROFILE_IDS = frozenset(
    {_BASE_DEXP_PROFILE_ID, _CORRECTED_DEXP_PROFILE_ID}
)
_ACTUAL_MUD_DENSITY_CANDIDATES = ("MW_IN", "MW_OUT")


class Wits0LiveDerivedChannelService:
    """Project sourced formula profiles onto a WITS Dataset without mutating it."""

    def __init__(
        self,
        *,
        registry: FormulaProfileRegistry | None = None,
        resolver: LasParameterResolver | None = None,
        uom_dictionary: UomDictionary | None = None,
        dexp_correction: Wits0DexpCorrectionConfig | None = None,
    ) -> None:
        self._registry = registry or build_all_sourced_formula_registry()
        self._resolver = resolver or LasParameterResolver()
        self._uom_dictionary = uom_dictionary or default_uom_dictionary()
        self._dexp_correction = dexp_correction

    def snapshot(self, dataset: Dataset) -> tuple[Wits0DerivedChannelSnapshot, ...]:
        profiles = tuple(
            profile
            for profile in self._registry.available()
            if self._supports_profile(profile)
        )
        direct_profiles = tuple(
            profile
            for profile in profiles
            if profile.profile_id != _CORRECTED_DEXP_PROFILE_ID
        )
        target_names = list(
            dict.fromkeys(
                self._binding(input_mnemonic).source_mnemonic
                for profile in direct_profiles
                for input_mnemonic in profile.required_inputs
            )
        )
        if any(profile.profile_id == _BASE_DEXP_PROFILE_ID for profile in direct_profiles):
            target_names.extend(("FLOW_IN", "FLOW_OUT"))
        if any(profile.profile_id == _CORRECTED_DEXP_PROFILE_ID for profile in profiles):
            target_names.extend(_ACTUAL_MUD_DENSITY_CANDIDATES)
        targets = tuple(dict.fromkeys(target_names))
        resolution = self._resolver.resolve_dataset(dataset, targets=targets)

        output = [
            self._snapshot_profile(profile, resolution, dataset=dataset)
            for profile in direct_profiles
        ]
        corrected_profile = next(
            (
                profile
                for profile in profiles
                if profile.profile_id == _CORRECTED_DEXP_PROFILE_ID
            ),
            None,
        )
        if corrected_profile is not None:
            base_dexp = next(
                (item for item in output if item.profile_id == _BASE_DEXP_PROFILE_ID),
                None,
            )
            output.append(
                self._snapshot_corrected_dexp(
                    corrected_profile,
                    resolution,
                    base_dexp=base_dexp,
                )
            )
        return tuple(output)

    def virtual_curves(self, dataset: Dataset) -> dict[str, CurveData]:
        """Materialize available derived results as ephemeral live-only curves."""

        output: dict[str, CurveData] = {}
        for snapshot in self.snapshot(dataset):
            if snapshot.status is not Wits0DerivedChannelStatus.AVAILABLE:
                continue
            curve_id = self.virtual_curve_id(snapshot)
            provenance = snapshot.provenance
            if snapshot.input_conversions:
                provenance += ";uom=" + ",".join(snapshot.input_conversions)
            if snapshot.source_record_numbers:
                provenance += ";source-records=" + ",".join(
                    f"{record_no:02d}" for record_no in snapshot.source_record_numbers
                )
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
        return f"wits-derived:{snapshot.profile_id}:{snapshot.profile_version}"

    def _snapshot_profile(
        self,
        profile: FormulaProfile,
        resolution: DatasetParameterResolution,
        *,
        dataset: Dataset,
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

        source_record_numbers = self._source_record_numbers(bindings, resolution)
        inputs: dict[str, np.ndarray] = {}
        conversions: list[str] = []
        unsupported_units: list[str] = []
        for input_name, binding in bindings.items():
            match = resolution.get(binding.source_mnemonic)
            assert match is not None
            source_unit = self._physical_source_unit(match)
            values = np.asarray(match.curve.values, dtype=np.float64)
            if binding.concentration_percent:
                scale = concentration_scale_to_percent(source_unit)
                if scale is None:
                    unsupported_units.append(input_name)
                    continue
                inputs[input_name] = values * scale
                conversions.append(
                    f"{input_name}:{source_unit or '<missing>'}->%"
                )
                continue

            target_unit = binding.target_unit
            if target_unit is None:
                inputs[input_name] = values
                conversions.append(
                    f"{input_name}:{source_unit or '<missing>'}->unchanged"
                )
                continue

            converted = self._convert_engineering_match(
                input_name,
                match,
                target_unit,
            )
            if converted is None:
                unsupported_units.append(input_name)
                continue
            converted_values, conversion_label = converted
            inputs[input_name] = converted_values
            conversions.append(conversion_label)

        if unsupported_units:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.UNSUPPORTED_UNIT,
                tuple(unsupported_units),
                input_conversions=tuple(conversions),
            )

        if profile.profile_id in _SUPPORTED_D_EXPONENT_PROFILE_IDS:
            self._apply_mode_aware_rpm(
                dataset,
                resolution,
                inputs,
                conversions,
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
            source_record_numbers=source_record_numbers,
        )

    @staticmethod
    def _source_record_numbers(
        bindings: dict[str, _InputBinding],
        resolution: DatasetParameterResolution,
    ) -> tuple[int, ...]:
        records: set[int] = set()
        for binding in bindings.values():
            match = resolution.get(binding.source_mnemonic)
            if match is None:
                continue
            record_no = Wits0LiveDerivedChannelService._record_no_from_provenance(
                match.curve.metadata.provenance
            )
            if record_no is not None:
                records.add(record_no)
        return tuple(sorted(records))

    @staticmethod
    def _record_no_from_provenance(provenance: str) -> int | None:
        if not provenance.startswith("wits0:"):
            return None
        source_id = provenance.removeprefix("wits0:").split(";", 1)[0]
        if len(source_id) < 2 or not source_id[:2].isdigit():
            return None
        return int(source_id[:2])

    def _snapshot_corrected_dexp(
        self,
        profile: FormulaProfile,
        resolution: DatasetParameterResolution,
        *,
        base_dexp: Wits0DerivedChannelSnapshot | None,
    ) -> Wits0DerivedChannelSnapshot:
        if self._dexp_correction is None:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.MISSING_CONFIGURATION,
                ("RHO_N_PPG",),
            )
        if (
            base_dexp is None
            or base_dexp.status is not Wits0DerivedChannelStatus.AVAILABLE
        ):
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.MISSING_INPUT,
                ("DEXP",),
            )

        actual_match: ParameterMatch | None = None
        ambiguous_actual = False
        for canonical in _ACTUAL_MUD_DENSITY_CANDIDATES:
            if canonical in resolution.ambiguities:
                ambiguous_actual = True
                continue
            candidate = resolution.get(canonical)
            if candidate is not None:
                actual_match = candidate
                break
        if actual_match is None:
            return self._unavailable(
                profile,
                (
                    Wits0DerivedUnavailableReason.AMBIGUOUS_INPUT
                    if ambiguous_actual
                    else Wits0DerivedUnavailableReason.MISSING_INPUT
                ),
                ("RHO_A_PPG",),
            )

        actual_unit = self._physical_source_unit(actual_match)
        actual_conversion = self._uom_dictionary.conversion(actual_unit, "ppg")
        normal_conversion = self._uom_dictionary.conversion(
            self._dexp_correction.unit,
            "ppg",
        )
        unsupported: list[str] = []
        if actual_conversion is None:
            unsupported.append("RHO_A_PPG")
        if normal_conversion is None:
            unsupported.append("RHO_N_PPG")
        if unsupported:
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.UNSUPPORTED_UNIT,
                tuple(unsupported),
            )

        dexp_values = np.asarray(base_dexp.values, dtype=np.float64)
        actual_ppg = actual_conversion.convert_array(actual_match.curve.values)
        normal_ppg_value = normal_conversion.convert_scalar(
            self._dexp_correction.normal_mud_density
        )
        normal_ppg = np.full(dexp_values.shape, normal_ppg_value, dtype=np.float64)
        conversions = (
            f"DEXP:{base_dexp.profile_id}@{base_dexp.profile_version}",
            f"RHO_A_PPG:{actual_conversion.source_uom}->ppg",
            f"RHO_N_PPG:{normal_conversion.source_uom}->ppg(explicit)",
        )
        values = self._registry.calculate(
            profile.profile_id,
            {
                "DEXP": dexp_values,
                "RHO_N_PPG": normal_ppg,
                "RHO_A_PPG": actual_ppg,
            },
        )
        if values.size == 0 or not np.any(np.isfinite(values)):
            return self._unavailable(
                profile,
                Wits0DerivedUnavailableReason.NO_VALID_SAMPLES,
                (),
                input_conversions=conversions,
            )

        density_record = self._record_no_from_provenance(
            actual_match.curve.metadata.provenance
        )
        source_records = set(base_dexp.source_record_numbers)
        if density_record is not None:
            source_records.add(density_record)
        return Wits0DerivedChannelSnapshot(
            mnemonic=profile.output_mnemonic,
            unit=profile.output_unit,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            category=profile.category,
            required_inputs=tuple(name.upper() for name in profile.required_inputs),
            description=profile.description,
            provenance=self._provenance(profile),
            status=Wits0DerivedChannelStatus.AVAILABLE,
            values=tuple(float(value) for value in values),
            input_conversions=conversions,
            source_record_numbers=tuple(sorted(source_records)),
        )

    def _convert_engineering_match(
        self,
        input_name: str,
        match: ParameterMatch,
        target_unit: str,
    ) -> tuple[np.ndarray, str] | None:
        source_unit = self._physical_source_unit(match)
        conversion = self._uom_dictionary.conversion(source_unit, target_unit)
        if conversion is not None:
            return (
                conversion.convert_array(match.curve.values),
                f"{input_name}:{conversion.source_uom}->{conversion.target_uom}",
            )

        if input_name == "WOB_LBF" and target_unit == "lbf":
            resolved = self._uom_dictionary.resolve(source_unit)
            if resolved.canonical in {"kg", "t"}:
                mass_scale = 1_000.0 if resolved.canonical == "t" else 1.0
                values = (
                    np.asarray(match.curve.values, dtype=np.float64)
                    * mass_scale
                    * 9.80665
                    / 4.4482216152605
                )
                return values, f"{input_name}:{resolved.canonical}->lbf(g0)"
        return None

    def _apply_mode_aware_rpm(
        self,
        dataset: Dataset,
        resolution: DatasetParameterResolution,
        inputs: dict[str, np.ndarray],
        conversions: list[str],
    ) -> None:
        flow, flow_label = self._optional_engineering_input(
            resolution,
            ("FLOW_IN", "FLOW_OUT"),
            "gpm",
        )
        bit_rpm, bit_rpm_mnemonic = resolve_bit_rpm_curve(
            dataset,
            uom=self._uom_dictionary,
        )
        modes = classify_drilling_modes(
            inputs["ROP_FPH"],
            inputs["RPM"],
            inputs["WOB_LBF"],
            flow=flow,
            bit_rpm=bit_rpm,
        )
        inputs["RPM"] = modes.effective_rpm
        if flow_label is not None:
            conversions.append(f"MODE_FLOW:{flow_label}")
        conversions.append(
            "RPM_MODE:surface+"
            + (bit_rpm_mnemonic if bit_rpm_mnemonic is not None else "no-bit-rpm")
        )

    def _optional_engineering_input(
        self,
        resolution: DatasetParameterResolution,
        candidates: tuple[str, ...],
        target_unit: str,
    ) -> tuple[np.ndarray | None, str | None]:
        for canonical in candidates:
            if canonical in resolution.ambiguities:
                continue
            match = resolution.get(canonical)
            if match is None:
                continue
            source_unit = self._physical_source_unit(match)
            conversion = self._uom_dictionary.conversion(source_unit, target_unit)
            if conversion is None:
                continue
            return (
                conversion.convert_array(match.curve.values),
                f"{conversion.source_uom}->{conversion.target_uom}",
            )
        return None, None

    @staticmethod
    def _physical_source_unit(match: ParameterMatch) -> str:
        metadata = match.curve.metadata
        semantic = metadata.semantic
        if (
            metadata.provenance.startswith("wits0:")
            and semantic is not None
            and semantic.source_uom
        ):
            return semantic.source_uom
        return match.unit

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
    "Wits0DexpCorrectionConfig",
    "Wits0DerivedChannelSnapshot",
    "Wits0DerivedChannelStatus",
    "Wits0DerivedUnavailableReason",
    "Wits0LiveDerivedChannelService",
]
