from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

import numpy as np

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
from geoworkbench.services.dexp_gap_repair import repair_dexp_short_gaps
from geoworkbench.services.drilling_input_plan import (
    DrillingInputPlan,
    DrillingInputResolver,
)
from geoworkbench.services.drilling_mode import (
    DrillingModeResolution,
    classify_drilling_modes,
    resolve_bit_rpm_curve,
)
from geoworkbench.services.las_parameter_resolver import (
    DatasetParameterResolution,
    ParameterResolutionError,
    resolve_gas_ratio_inputs,
)


class NormalizedGasCalculationMode(StrEnum):
    """Controls whether local normalized gas is calculated alongside source data."""

    COMPARE = "compare"
    SERVER = "server"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class _ModeAwareDexpInputs:
    resolution: DatasetParameterResolution
    rop: Array
    surface_rpm: Array
    wob: Array
    bit: Array
    flow: Array | None
    modes: DrillingModeResolution


@dataclass
class InterpretationCalculationController(_LegacyInterpretationCalculationController):
    """Preserve source curves and use one explicit drilling-input plan for all methods."""

    resolver: DrillingInputResolver = field(default_factory=DrillingInputResolver)
    normalized_gas_mode: NormalizedGasCalculationMode = NormalizedGasCalculationMode.COMPARE
    _active_normalized_gas_mode: NormalizedGasCalculationMode = field(
        default=NormalizedGasCalculationMode.COMPARE,
        init=False,
        repr=False,
    )
    _active_drilling_mode_resolution: DrillingModeResolution | None = field(
        default=None,
        init=False,
        repr=False,
    )

    @property
    def drilling_input_plan(self) -> DrillingInputPlan:
        return self.resolver.plan

    def set_drilling_input_plan(self, plan: DrillingInputPlan) -> None:
        self.resolver.set_plan(plan)

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
        dataset = self._require_dataset()
        mode_issues: list[InterpretationCalculationIssue] = []
        mode_inputs = self._resolve_mode_aware_dexp_inputs(dataset, mode_issues)

        previous_mode = self._active_normalized_gas_mode
        previous_drilling = self._active_drilling_mode_resolution
        self._active_normalized_gas_mode = mode
        self._active_drilling_mode_resolution = (
            mode_inputs.modes if mode_inputs is not None else None
        )
        try:
            result = _LegacyInterpretationCalculationController.calculate_standard_curves(
                self,
                normal_mud_density_ppg=normal_mud_density_ppg,
                normalized_gas_reference=reference,
            )
            created = list(result.created)
            updated = list(result.updated)
            skipped = list(result.skipped)
            issues = [*result.issues, *mode_issues]
            if mode_inputs is not None:
                self._install_drilling_mode_audit_curves(
                    dataset,
                    mode_inputs.modes,
                    created=created,
                    updated=updated,
                    skipped=skipped,
                    issues=issues,
                )
                self._recalculate_mode_aware_dexp(
                    dataset,
                    mode_inputs,
                    normal_mud_density_ppg=normal_mud_density_ppg,
                    created=created,
                    updated=updated,
                    skipped=skipped,
                    issues=issues,
                )
        finally:
            self._active_normalized_gas_mode = previous_mode
            self._active_drilling_mode_resolution = previous_drilling

        tracks = dict(result.track_curves)
        tracks["normalized_gas"] = self._normalized_track_curves(dataset, mode)
        if created or updated:
            self.session.dirty = True
        return InterpretationCalculationResult(
            tuple(dict.fromkeys(created)),
            tuple(dict.fromkeys(updated)),
            tuple(dict.fromkeys(skipped)),
            tuple(self._deduplicate_issues(issues)),
            tracks,
        )

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

    def _resolve_mode_aware_dexp_inputs(
        self,
        dataset: Dataset,
        issues: list[InterpretationCalculationIssue],
    ) -> _ModeAwareDexpInputs | None:
        try:
            resolution = self.resolver.resolve_dataset(
                dataset,
                targets=(
                    "ROP",
                    "RPM",
                    "WOB",
                    "BIT",
                    "FLOW_IN",
                    "FLOW_OUT",
                    "MW_IN",
                    "MW_OUT",
                ),
            )
        except (ParameterResolutionError, RuntimeError, ValueError) as exc:
            issues.append(InterpretationCalculationIssue("drilling-mode-inputs", str(exc)))
            return None

        rop = self._converted_input(resolution, ("ROP",), "ft/h", issues)
        surface_rpm = self._converted_input(resolution, ("RPM",), "1/min", issues)
        wob = self._converted_input(resolution, ("WOB",), "lbf", issues)
        bit = self._converted_input(resolution, ("BIT",), "in", issues)
        flow = self._converted_input(
            resolution,
            ("FLOW_IN", "FLOW_OUT"),
            "gpm",
            issues,
        )
        if rop is None or surface_rpm is None or wob is None or bit is None:
            return None

        bit_rpm, bit_rpm_mnemonic = resolve_bit_rpm_curve(dataset, uom=self.uom)
        modes = classify_drilling_modes(
            rop,
            surface_rpm,
            wob,
            flow=flow,
            bit_rpm=bit_rpm,
        )
        modes = replace(modes, bit_rpm_mnemonic=bit_rpm_mnemonic)
        low_surface = (
            np.isfinite(rop)
            & (rop > 0.0)
            & np.isfinite(wob)
            & (wob > 0.0)
            & np.isfinite(surface_rpm)
            & (surface_rpm >= 0.0)
            & (surface_rpm <= 5.0)
        )
        if flow is None and np.any(low_surface):
            issues.append(
                InterpretationCalculationIssue(
                    "drilling-mode-flow-missing",
                    "Низкий поверхностный RPM обнаружен, но FLOW отсутствует: "
                    "слайдирование нельзя надёжно отличить от остановки или соединения.",
                )
            )
        return _ModeAwareDexpInputs(
            resolution=resolution,
            rop=rop,
            surface_rpm=surface_rpm,
            wob=wob,
            bit=bit,
            flow=flow,
            modes=modes,
        )

    def _install_drilling_mode_audit_curves(
        self,
        dataset: Dataset,
        modes: DrillingModeResolution,
        *,
        created: list[str],
        updated: list[str],
        skipped: list[str],
        issues: list[InterpretationCalculationIssue],
    ) -> None:
        self._install_curve(
            dataset,
            "DRILL_MODE",
            modes.mode_codes.astype(np.float64),
            unit="code",
            description=(
                "Режим бурения: 0=не определён, 1=роторное бурение, "
                "2=слайдирование, 3=бурение не выполняется"
            ),
            provenance="calculation:drilling-mode:1.0",
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
        )
        if np.any(np.isfinite(modes.effective_rpm)):
            source = modes.bit_rpm_mnemonic or "surface RPM only"
            self._install_curve(
                dataset,
                "BIT_RPM_EFFECTIVE",
                modes.effective_rpm,
                unit="1/min",
                description=(
                    "Эффективные обороты долота для DEXP: поверхностный RPM в роторном "
                    f"режиме и фактический забойный RPM ({source}) при слайдировании"
                ),
                provenance=f"calculation:mode-aware-bit-rpm:1.0;bit_rpm_source={source}",
                created=created,
                updated=updated,
                skipped=skipped,
                issues=issues,
            )

    def _recalculate_mode_aware_dexp(
        self,
        dataset: Dataset,
        inputs: _ModeAwareDexpInputs,
        *,
        normal_mud_density_ppg: float | None,
        created: list[str],
        updated: list[str],
        skipped: list[str],
        issues: list[InterpretationCalculationIssue],
    ) -> None:
        existing = dataset.curve_by_mnemonic("DEXP")
        if existing is not None and not existing.metadata.provenance.startswith("calculation:"):
            return

        passport = self.registry.passport("dexp.jorden_shirley")
        try:
            values = self.registry.calculate(
                passport.profile_id,
                {
                    "ROP_FPH": inputs.rop,
                    "RPM": inputs.modes.effective_rpm,
                    "WOB_LBF": inputs.wob,
                    "BIT_IN": inputs.bit,
                },
            )
        except (KeyError, ValueError, FloatingPointError) as exc:
            skipped.append(passport.output_mnemonic)
            issues.append(
                InterpretationCalculationIssue(
                    "formula-error",
                    f"{passport.output_mnemonic} не рассчитан: {exc}",
                )
            )
            return

        source = inputs.modes.bit_rpm_mnemonic or "missing"
        provenance = (
            f"calculation:{passport.profile_id}:{passport.version};rpm=mode-aware;"
            f"rotary_points={inputs.modes.rotary_points};"
            f"slide_points={inputs.modes.slide_points};"
            f"slide_with_bit_rpm={inputs.modes.slide_points_with_bit_rpm};"
            f"bit_rpm_source={source};mode_boundaries=preserved"
        )
        self._install_curve(
            dataset,
            passport.output_mnemonic,
            values,
            unit=passport.output_unit,
            description=(
                f"{passport.display_name} — RPM выбран по режиму ROTARY/SLIDE; "
                "границы режимов сохранены"
            ),
            provenance=provenance,
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
        )

        missing_slide = inputs.modes.slide_points_without_bit_rpm
        if missing_slide:
            issues.append(
                InterpretationCalculationIssue(
                    "dexp-slide-bit-rpm-missing",
                    f"DEXP оставлен с разрывами в {missing_slide} точках слайдирования: "
                    "поверхностный RPM не является оборотами долота, а кривая "
                    "забойного/моторного RPM не найдена.",
                )
            )

        if normal_mud_density_ppg is None:
            return
        dexp_curve = dataset.curve_by_mnemonic("DEXP")
        actual_density = self._converted_input(
            inputs.resolution,
            ("MW_IN", "MW_OUT"),
            "ppg",
            issues,
        )
        if dexp_curve is None or actual_density is None:
            return

        corrected = self.registry.passport("dexp.rehm_mcclendon_corrected")
        try:
            corrected_values = self.registry.calculate(
                corrected.profile_id,
                {
                    "DEXP": np.asarray(dexp_curve.values, dtype=np.float64),
                    "RHO_N_PPG": np.full(
                        dataset.depth.shape,
                        float(normal_mud_density_ppg),
                        dtype=np.float64,
                    ),
                    "RHO_A_PPG": actual_density,
                },
            )
        except (KeyError, ValueError, FloatingPointError) as exc:
            skipped.append(corrected.output_mnemonic)
            issues.append(
                InterpretationCalculationIssue(
                    "formula-error",
                    f"{corrected.output_mnemonic} не рассчитан: {exc}",
                )
            )
            return
        self._install_curve(
            dataset,
            corrected.output_mnemonic,
            corrected_values,
            unit=corrected.output_unit,
            description=(
                f"{corrected.display_name} — рассчитана из режимно-корректной DEXP"
            ),
            provenance=(
                f"calculation:{corrected.profile_id}:{corrected.version};"
                "source_dexp=mode-aware;mode_boundaries=preserved"
            ),
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
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
        _LegacyInterpretationCalculationController._calculate_profile(
            self,
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
        installed_values = values
        installed_provenance = provenance

        if (
            mnemonic in {"DEXP", "DEXPC"}
            and provenance.startswith("calculation:")
        ):
            modes = self._active_drilling_mode_resolution
            repair = repair_dexp_short_gaps(
                dataset.depth,
                values,
                depth_unit=dataset.active_index.unit or "",
                segment_labels=modes.mode_codes if modes is not None else None,
                repairable_mask=modes.repairable_mask if modes is not None else None,
            )
            installed_values = repair.values
            if repair.repaired_points:
                installed_provenance = (
                    f"{provenance};gap_repair=linear-short-internal-same-mode;"
                    f"points={repair.repaired_points};gaps={repair.repaired_gaps}"
                )
                target_description = (
                    f"{description} — короткие внутренние разрывы восстановлены "
                    "только внутри одного режима бурения"
                )

        if mnemonic == "TG_NORM" and provenance.startswith("calculation:"):
            target_mnemonic = "TG_NORM_CALC"
            target_description = f"{description} — local program calculation"
        _LegacyInterpretationCalculationController._install_curve(
            self,
            dataset,
            target_mnemonic,
            installed_values,
            unit=unit,
            description=target_description,
            provenance=installed_provenance,
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
