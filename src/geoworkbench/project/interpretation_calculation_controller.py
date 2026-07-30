from __future__ import annotations

from dataclasses import replace
from enum import StrEnum

from geoworkbench.domain.models import Dataset
from geoworkbench.project.interpretation_calculation_controller_legacy import (
    DEFAULT_NORMALIZED_GAS_REFERENCE,
    Array,
    InterpretationCalculationController as _LegacyInterpretationCalculationController,
    InterpretationCalculationIssue,
    InterpretationCalculationResult,
    NormalizedGasReference,
)
from geoworkbench.services.channel_groups import NORMALIZED_GAS_MNEMONIC_ORDER
from geoworkbench.services.las_parameter_resolver import (
    ParameterResolutionError,
    resolve_gas_ratio_inputs,
)


class NormalizedGasCalculationMode(StrEnum):
    """Controls whether local normalized gas is calculated alongside source data."""

    COMPARE = "compare"
    SERVER = "server"
    LOCAL = "local"


class InterpretationCalculationController(_LegacyInterpretationCalculationController):
    """Preserve source normalized gas and store the local result independently."""

    normalized_gas_mode: NormalizedGasCalculationMode = NormalizedGasCalculationMode.COMPARE
    _active_normalized_gas_mode: NormalizedGasCalculationMode = (
        NormalizedGasCalculationMode.COMPARE
    )

    def calculate_standard_curves(
        self,
        *,
        normal_mud_density_ppg: float | None = None,
        normalized_gas_reference: NormalizedGasReference
        | None = DEFAULT_NORMALIZED_GAS_REFERENCE,
        normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
    ) -> InterpretationCalculationResult:
        mode = self._normalized_gas_mode(normalized_gas_mode)
        reference = (
            None
            if mode is NormalizedGasCalculationMode.SERVER
            else normalized_gas_reference
        )
        previous = self._active_normalized_gas_mode
        self._active_normalized_gas_mode = mode
        try:
            result = super().calculate_standard_curves(
                normal_mud_density_ppg=normal_mud_density_ppg,
                normalized_gas_reference=reference,
            )
        finally:
            self._active_normalized_gas_mode = previous
        dataset = self._require_dataset()
        tracks = dict(result.track_curves)
        tracks["normalized_gas"] = self._normalized_track_curves(dataset, mode)
        return replace(result, track_curves=tracks)

    def calculate_normalized_gas(
        self,
        *,
        normalized_gas_reference: NormalizedGasReference = DEFAULT_NORMALIZED_GAS_REFERENCE,
        normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
    ) -> InterpretationCalculationResult:
        """Calculate only local normalized-gas curves for the selected source mode."""

        dataset = self._require_dataset()
        mode = self._normalized_gas_mode(normalized_gas_mode)
        if mode is NormalizedGasCalculationMode.SERVER:
            return self.normalized_gas_track_result(mode)

        parameters = normalized_gas_reference.parameters()
        created: list[str] = []
        updated: list[str] = []
        skipped: list[str] = []
        issues: list[InterpretationCalculationIssue] = []
        try:
            gas_inputs = resolve_gas_ratio_inputs(dataset, resolver=self.resolver)
        except (ParameterResolutionError, ValueError) as exc:
            gas_inputs = {}
            issues.append(InterpretationCalculationIssue("gas-inputs", str(exc)))

        resolution = self.resolver.resolve_dataset(
            dataset,
            targets=("ROP", "BIT", "FLOW_IN", "FLOW_OUT"),
        )
        rop = self._converted_input(resolution, ("ROP",), "ft/h", issues)
        bit = self._converted_input(resolution, ("BIT",), "in", issues)
        flow = self._converted_input(resolution, ("FLOW_IN", "FLOW_OUT"), "gpm", issues)

        if gas_inputs and rop is not None and bit is not None and flow is not None:
            previous = self._active_normalized_gas_mode
            self._active_normalized_gas_mode = mode
            try:
                self._calculate_profile(
                    dataset,
                    "gas.normalized_c1_us20140379265",
                    {
                        "C1": gas_inputs["C1"],
                        "FLOW_GPM": flow,
                        "ROP_FPH": rop,
                        "BIT_IN": bit,
                    },
                    created=created,
                    updated=updated,
                    skipped=skipped,
                    issues=issues,
                )
                self._calculate_reference_normalized_gas(
                    dataset,
                    gas_inputs,
                    rop=rop,
                    bit=bit,
                    flow=flow,
                    parameters=parameters,
                    created=created,
                    updated=updated,
                    skipped=skipped,
                    issues=issues,
                )
            finally:
                self._active_normalized_gas_mode = previous
        else:
            missing = self._missing_names(
                (
                    ("C1–C5", gas_inputs if gas_inputs else None),
                    ("ROP", rop),
                    ("BIT", bit),
                    ("FLOW", flow),
                )
            )
            issues.append(
                InterpretationCalculationIssue(
                    "normalized-gas-inputs",
                    "Нормализованный газ не рассчитан: отсутствуют или неоднозначны "
                    + ", ".join(missing),
                )
            )

        if created or updated:
            self.session.dirty = True
        return InterpretationCalculationResult(
            tuple(dict.fromkeys(created)),
            tuple(dict.fromkeys(updated)),
            tuple(dict.fromkeys(skipped)),
            tuple(self._deduplicate_issues(issues)),
            {
                "gas_ratio_pixler": (),
                "normalized_gas": self._normalized_track_curves(dataset, mode),
                "dexp": (),
            },
        )

    def normalized_gas_track_result(
        self,
        normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
    ) -> InterpretationCalculationResult:
        """Return a display-only result for normalized curves already in the dataset."""

        dataset = self._require_dataset()
        mode = self._normalized_gas_mode(normalized_gas_mode)
        curves = self._normalized_track_curves(dataset, mode)
        issues: tuple[InterpretationCalculationIssue, ...] = ()
        if not curves:
            issues = (
                InterpretationCalculationIssue(
                    "normalized-gas-missing",
                    "В выбранном режиме не найдено ни одной кривой нормализованного газа.",
                ),
            )
        return InterpretationCalculationResult(
            (),
            (),
            (),
            issues,
            {
                "gas_ratio_pixler": (),
                "normalized_gas": curves,
                "dexp": (),
            },
        )

    def _normalized_gas_mode(
        self,
        requested: NormalizedGasCalculationMode | str | None,
    ) -> NormalizedGasCalculationMode:
        value = requested if requested is not None else self.normalized_gas_mode
        try:
            return NormalizedGasCalculationMode(str(value))
        except ValueError as exc:
            raise ValueError(f"Неизвестный режим нормализованного газа: {value}") from exc

    @staticmethod
    def _normalized_track_curves(
        dataset: Dataset,
        mode: NormalizedGasCalculationMode,
    ) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for mnemonic in NORMALIZED_GAS_MNEMONIC_ORDER:
            curve = dataset.curve_by_mnemonic(mnemonic)
            if curve is None or curve.metadata.curve_id in seen:
                continue
            local = curve.metadata.provenance.startswith("calculation:")
            if mode is NormalizedGasCalculationMode.SERVER and local:
                continue
            if mode is NormalizedGasCalculationMode.LOCAL and not local:
                continue
            result.append(curve.metadata.original_mnemonic)
            seen.add(curve.metadata.curve_id)
        return tuple(result)

    def _calculate_profile(
        self,
        dataset: Dataset,
        profile_id: str,
        inputs: dict[str, Array | None],
        *,
        parameters: dict[str, float] | None = None,
        created: list[str],
        updated: list[str],
        skipped: list[str],
        issues: list[InterpretationCalculationIssue],
    ) -> None:
        if (
            self._active_normalized_gas_mode is NormalizedGasCalculationMode.SERVER
            and profile_id.startswith("gas.normalized_")
        ):
            skipped.append(self.registry.passport(profile_id).output_mnemonic)
            return
        super()._calculate_profile(
            dataset,
            profile_id,
            inputs,
            parameters=parameters,
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
        )

    def _install_curve(
        self,
        dataset: Dataset,
        mnemonic: str,
        values: Array,
        *,
        unit: str,
        description: str,
        provenance: str,
        created: list[str],
        updated: list[str],
        skipped: list[str],
        issues: list[InterpretationCalculationIssue],
    ) -> None:
        target_mnemonic = mnemonic
        target_description = description
        if mnemonic == "TG_NORM" and provenance.startswith("calculation:"):
            target_mnemonic = "TG_NORM_CALC"
            target_description = f"{description} — local program calculation"
        super()._install_curve(
            dataset,
            target_mnemonic,
            values,
            unit=unit,
            description=target_description,
            provenance=provenance,
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
        )


__all__ = [
    "DEFAULT_NORMALIZED_GAS_REFERENCE",
    "InterpretationCalculationController",
    "InterpretationCalculationIssue",
    "InterpretationCalculationResult",
    "NormalizedGasCalculationMode",
    "NormalizedGasReference",
]
