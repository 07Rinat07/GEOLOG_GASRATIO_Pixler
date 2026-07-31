from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from numpy.typing import NDArray

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios
from geoworkbench.calculations.pixler import (
    FormulaProfileRegistry,
    build_all_sourced_formula_registry,
)
from geoworkbench.domain.models import CalculationState, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.channel_groups import (
    DEXP_MNEMONIC_ORDER,
    GAS_RATIO_PIXLER_MNEMONIC_ORDER,
    NORMALIZED_GAS_MNEMONIC_ORDER,
    available_mnemonics,
)
from geoworkbench.services.las_parameter_resolver import (
    DatasetParameterResolution,
    LasParameterResolver,
    ParameterResolutionError,
    resolve_gas_ratio_inputs,
)
from geoworkbench.services.uom_dictionary import UomDictionary, default_uom_dictionary


Array = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class InterpretationCalculationIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class NormalizedGasReference:
    """Explicit field reference used by the C1-C5 normalization profiles."""

    rop_ref_fph: float = 50.0
    bit_ref_in: float = 10.0
    flow_ref_gpm: float = 500.0
    gas_system_efficiency: float = 1.0

    def parameters(self) -> dict[str, float]:
        values = {
            "ROP_REF_FPH": float(self.rop_ref_fph),
            "BIT_REF_IN": float(self.bit_ref_in),
            "FLOW_REF_GPM": float(self.flow_ref_gpm),
            "GAS_SYSTEM_EFFICIENCY": float(self.gas_system_efficiency),
        }
        if not all(np.isfinite(value) and value > 0.0 for value in values.values()):
            raise ValueError(
                "Эталонные ROP, диаметр долота, расход и эффективность должны быть больше нуля"
            )
        if self.gas_system_efficiency > 1.0:
            raise ValueError("Эффективность газовой системы должна быть не больше 1")
        return values


DEFAULT_NORMALIZED_GAS_REFERENCE = NormalizedGasReference()


@dataclass(frozen=True, slots=True)
class InterpretationCalculationResult:
    created: tuple[str, ...]
    updated: tuple[str, ...]
    skipped: tuple[str, ...]
    issues: tuple[InterpretationCalculationIssue, ...]
    track_curves: dict[str, tuple[str, ...]]

    @property
    def changed(self) -> tuple[str, ...]:
        return (*self.created, *self.updated)


@dataclass(slots=True)
class InterpretationCalculationController:
    """Calculate the sourced interpretation curve suite without guessing field units."""

    session: ProjectSession
    registry: FormulaProfileRegistry = field(default_factory=build_all_sourced_formula_registry)
    resolver: LasParameterResolver = field(default_factory=LasParameterResolver)
    uom: UomDictionary = field(default_factory=default_uom_dictionary)

    def calculate_standard_curves(
        self,
        *,
        normal_mud_density_ppg: float | None = None,
        normalized_gas_reference: NormalizedGasReference
        | None = DEFAULT_NORMALIZED_GAS_REFERENCE,
    ) -> InterpretationCalculationResult:
        dataset = self._require_dataset()
        if normal_mud_density_ppg is not None and (
            not np.isfinite(normal_mud_density_ppg) or normal_mud_density_ppg <= 0.0
        ):
            raise ValueError("Нормальная плотность раствора должна быть больше нуля")
        normalized_parameters = (
            normalized_gas_reference.parameters()
            if normalized_gas_reference is not None
            else None
        )

        created: list[str] = []
        updated: list[str] = []
        skipped: list[str] = []
        issues: list[InterpretationCalculationIssue] = []

        gas_inputs = self._calculate_gas_methods(
            dataset,
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
        )
        resolution = self.resolver.resolve_dataset(
            dataset,
            targets=("ROP", "RPM", "WOB", "BIT", "FLOW_IN", "FLOW_OUT", "MW_IN", "MW_OUT"),
        )
        rop = self._converted_input(resolution, ("ROP",), "ft/h", issues)
        bit = self._converted_input(resolution, ("BIT",), "in", issues)
        flow = self._converted_input(resolution, ("FLOW_IN", "FLOW_OUT"), "gpm", issues)
        rpm = self._converted_input(resolution, ("RPM",), "1/min", issues)
        wob = self._converted_input(resolution, ("WOB",), "lbf", issues)

        if gas_inputs and rop is not None and bit is not None and flow is not None:
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
            if normalized_parameters is not None:
                self._calculate_reference_normalized_gas(
                    dataset,
                    gas_inputs,
                    rop=rop,
                    bit=bit,
                    flow=flow,
                    parameters=normalized_parameters,
                    created=created,
                    updated=updated,
                    skipped=skipped,
                    issues=issues,
                )
        else:
            missing = self._missing_names(
                (("C1", gas_inputs.get("C1") if gas_inputs else None), ("ROP", rop), ("BIT", bit), ("FLOW", flow))
            )
            issues.append(
                InterpretationCalculationIssue(
                    "normalized-gas-inputs",
                    "C1_NORM не рассчитан: отсутствуют или неоднозначны " + ", ".join(missing),
                )
            )

        if all(value is not None for value in (rop, rpm, wob, bit)):
            self._calculate_profile(
                dataset,
                "dexp.jorden_shirley",
                {
                    "ROP_FPH": rop,
                    "RPM": rpm,
                    "WOB_LBF": wob,
                    "BIT_IN": bit,
                },
                created=created,
                updated=updated,
                skipped=skipped,
                issues=issues,
            )
        else:
            missing = self._missing_names(
                (("ROP", rop), ("RPM", rpm), ("WOB", wob), ("BIT", bit))
            )
            issues.append(
                InterpretationCalculationIssue(
                    "dexp-inputs",
                    "DEXP не рассчитан: отсутствуют или неоднозначны " + ", ".join(missing),
                )
            )

        if normal_mud_density_ppg is not None:
            dexp_curve = dataset.curve_by_mnemonic("DEXP")
            actual_density = self._converted_input(
                resolution, ("MW_IN", "MW_OUT"), "ppg", issues
            )
            if dexp_curve is not None and actual_density is not None:
                self._calculate_profile(
                    dataset,
                    "dexp.rehm_mcclendon_corrected",
                    {
                        "DEXP": np.asarray(dexp_curve.values, dtype=np.float64),
                        "RHO_N_PPG": np.full(
                            dataset.depth.shape,
                            float(normal_mud_density_ppg),
                            dtype=np.float64,
                        ),
                        "RHO_A_PPG": actual_density,
                    },
                    created=created,
                    updated=updated,
                    skipped=skipped,
                    issues=issues,
                )
            else:
                issues.append(
                    InterpretationCalculationIssue(
                        "dexpc-inputs",
                        "DEXPC не рассчитан: требуется DEXP и фактическая плотность MW_IN/MW_OUT.",
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
                "gas_ratio_pixler": tuple(
                    available_mnemonics(dataset, GAS_RATIO_PIXLER_MNEMONIC_ORDER)
                ),
                "normalized_gas": tuple(
                    available_mnemonics(dataset, NORMALIZED_GAS_MNEMONIC_ORDER)
                ),
                "dexp": tuple(available_mnemonics(dataset, DEXP_MNEMONIC_ORDER)),
            },
        )

    def _calculate_gas_methods(
        self,
        dataset: Dataset,
        *,
        created: list[str],
        updated: list[str],
        skipped: list[str],
        issues: list[InterpretationCalculationIssue],
    ) -> dict[str, Array]:
        try:
            gas_inputs = resolve_gas_ratio_inputs(dataset, resolver=self.resolver)
        except (ParameterResolutionError, ValueError) as exc:
            issues.append(InterpretationCalculationIssue("gas-inputs", str(exc)))
            return {}

        for result in calculate_basic_ratios(gas_inputs).values():
            if result.mnemonic in {"C1_C2", "C1_C3"}:
                # These two outputs are installed below by the sourced Pixler
                # profiles. Avoid a transient basic curve and a second version
                # bump during one calculation command.
                continue
            self._install_curve(
                dataset,
                result.mnemonic,
                result.values,
                unit=result.unit,
                description=result.description,
                provenance="calculation:basic-gas-ratio:1.0",
                created=created,
                updated=updated,
                skipped=skipped,
                issues=issues,
            )

        formula_inputs = self._expanded_gas_inputs(gas_inputs)
        for profile_id in (
            "haworth.wetness",
            "haworth.balance",
            "haworth.character",
            "pixler.c1_c2",
            "pixler.c1_c3",
            "pixler.c1_c4",
            "pixler.c1_c5",
        ):
            passport = self.registry.passport(profile_id)
            if not all(name in formula_inputs for name in passport.required_inputs):
                skipped.append(passport.output_mnemonic)
                continue
            self._calculate_profile(
                dataset,
                profile_id,
                {name: formula_inputs[name] for name in passport.required_inputs},
                created=created,
                updated=updated,
                skipped=skipped,
                issues=issues,
            )
        if any(name not in formula_inputs for name in ("IC4", "NC4", "IC5", "NC5")):
            issues.append(
                InterpretationCalculationIssue(
                    "pixler-heavy-components",
                    "Часть Haworth/Pixler не рассчитана: нужны суммарные или раздельные C4 и C5.",
                )
            )
        return gas_inputs

    def _calculate_reference_normalized_gas(
        self,
        dataset: Dataset,
        gas_inputs: dict[str, Array],
        *,
        rop: Array,
        bit: Array,
        flow: Array,
        parameters: dict[str, float],
        created: list[str],
        updated: list[str],
        skipped: list[str],
        issues: list[InterpretationCalculationIssue],
    ) -> None:
        expanded = self._expanded_gas_inputs(gas_inputs)
        common_inputs = {
            "FLOW_GPM": flow,
            "ROP_FPH": rop,
            "BIT_IN": bit,
        }
        profile_components = (
            ("C1", "gas.normalized_c1_reference_us20150060054"),
            ("C2", "gas.normalized_c2_reference_us20150060054"),
            ("C3", "gas.normalized_c3_reference_us20150060054"),
            ("IC4", "gas.normalized_ic4_reference_us20150060054"),
            ("NC4", "gas.normalized_nc4_reference_us20150060054"),
            ("IC5", "gas.normalized_ic5_reference_us20150060054"),
            ("NC5", "gas.normalized_nc5_reference_us20150060054"),
        )
        for component, profile_id in profile_components:
            # Do not expose a fabricated zero isomer when the source LAS only
            # contains a summed C4 or C5 channel. The summed value still enters TG_NORM.
            if component not in gas_inputs and component not in {"C1", "C2", "C3"}:
                continue
            self._calculate_profile(
                dataset,
                profile_id,
                {
                    component: expanded[component],
                    **common_inputs,
                },
                parameters=parameters,
                created=created,
                updated=updated,
                skipped=skipped,
                issues=issues,
            )

        total_passport = self.registry.passport(
            "gas.normalized_total_reference_us20150060054"
        )
        self._calculate_profile(
            dataset,
            total_passport.profile_id,
            {
                name: (
                    common_inputs[name]
                    if name in common_inputs
                    else expanded[name]
                )
                for name in total_passport.required_inputs
            },
            parameters=parameters,
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
        )

    @staticmethod
    def _expanded_gas_inputs(inputs: dict[str, Array]) -> dict[str, Array]:
        expanded = dict(inputs)
        template = expanded["C1"]
        for total, iso, normal in (("C4", "IC4", "NC4"), ("C5", "IC5", "NC5")):
            if iso in expanded or normal in expanded:
                expanded.setdefault(iso, np.zeros_like(template))
                expanded.setdefault(normal, np.zeros_like(template))
            elif total in expanded:
                # Haworth and Pixler use the C4/C5 sum. Keeping a total component in
                # one slot preserves that sum without inventing an isomeric split.
                expanded[iso] = np.zeros_like(template)
                expanded[normal] = expanded[total]
        return expanded

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
        passport = self.registry.passport(profile_id)
        try:
            values = self.registry.calculate(
                profile_id,
                {name: np.asarray(value, dtype=np.float64) for name, value in inputs.items()},
                parameters,
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
        provenance = f"calculation:{profile_id}:{passport.version}"
        if parameters:
            parameter_text = ",".join(
                f"{name}={value:.8g}" for name, value in sorted(parameters.items())
            )
            provenance += f";{parameter_text}"
        self._install_curve(
            dataset,
            passport.output_mnemonic,
            values,
            unit=passport.output_unit,
            description=passport.display_name,
            provenance=provenance,
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
        existing = dataset.curve_by_mnemonic(mnemonic)
        if existing is None:
            semantic = self.resolver.resolve_dataset(dataset, targets=(mnemonic,))
            match = semantic.get(mnemonic)
            if match is not None:
                existing = match.curve
        if existing is not None and not existing.metadata.provenance.startswith("calculation:"):
            skipped.append(mnemonic)
            issues.append(
                InterpretationCalculationIssue(
                    "source-protected",
                    f"{mnemonic}: готовая кривая {existing.metadata.original_mnemonic} "
                    "из файла/сервера сохранена без перезаписи.",
                )
            )
            return
        curve = dataset.upsert_curve(
            mnemonic,
            values,
            unit=unit,
            description=description,
            provenance=provenance,
        )
        curve.metadata = replace(
            curve.metadata,
            canonical_mnemonic=mnemonic,
            unit=unit,
            description=description,
            provenance=provenance,
        )
        curve.state = CalculationState.CURRENT
        (updated if existing is not None else created).append(mnemonic)

    def _converted_input(
        self,
        resolution: DatasetParameterResolution,
        candidates: tuple[str, ...],
        target_unit: str,
        issues: list[InterpretationCalculationIssue],
    ) -> Array | None:
        for canonical in candidates:
            try:
                match = resolution.require(canonical)
            except ParameterResolutionError as exc:
                if exc.code == "ambiguous":
                    issues.append(InterpretationCalculationIssue("ambiguous-input", str(exc)))
                continue
            source_unit = match.unit
            conversion = self.uom.conversion(source_unit, target_unit)
            if (
                conversion is None
                and canonical == "WOB"
                and target_unit == "lbf"
                and self.uom.resolve(source_unit).canonical in {"kg", "t"}
            ):
                # Field LAS files often label weight-on-bit in kg or tonnes even
                # though WOB is physically a force. Convert with standard gravity,
                # but keep this convention local to the semantic WOB parameter so
                # the global UOM dictionary never treats mass and force as equal.
                mass_scale = 1_000.0 if self.uom.resolve(source_unit).canonical == "t" else 1.0
                return (
                    np.asarray(match.curve.values, dtype=np.float64)
                    * mass_scale
                    * 9.80665
                    / 4.4482216152605
                )
            if conversion is None:
                issues.append(
                    InterpretationCalculationIssue(
                        "unsupported-unit",
                        f"{match.source_mnemonic}: нельзя безопасно преобразовать "
                        f"{source_unit or 'единица не указана'} в {target_unit}.",
                    )
                )
                continue
            return conversion.convert_array(match.curve.values)
        return None

    @staticmethod
    def _missing_names(items: tuple[tuple[str, object | None], ...]) -> list[str]:
        return [name for name, value in items if value is None]

    @staticmethod
    def _deduplicate_issues(
        issues: list[InterpretationCalculationIssue],
    ) -> list[InterpretationCalculationIssue]:
        result: list[InterpretationCalculationIssue] = []
        seen: set[tuple[str, str]] = set()
        for issue in issues:
            key = (issue.code, issue.message)
            if key not in seen:
                seen.add(key)
                result.append(issue)
        return result

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset
