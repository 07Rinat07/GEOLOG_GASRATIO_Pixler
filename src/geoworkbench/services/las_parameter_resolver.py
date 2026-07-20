from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Iterable, Mapping

import numpy as np
from numpy.typing import NDArray

from geoworkbench.catalogs.sensors import (
    SensorCatalog,
    active_sensor_catalog,
    normalize_sensor_key,
    normalize_unit,
)
from geoworkbench.domain.models import CurveData, Dataset


Array = NDArray[np.float64]


class ParameterResolutionError(ValueError):
    """Raised when a required LAS parameter cannot be resolved safely.

    ``code`` and ``values`` let the Qt layer translate the error without making the
    calculation service depend on the active interface language. ``str(error)`` remains
    useful for logs, tests, and non-Qt workflows.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "generic",
        values: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.values = dict(values or {})


@dataclass(frozen=True, slots=True)
class ParameterMatch:
    """A single semantic mapping between a LAS curve and a canonical parameter."""

    canonical_mnemonic: str
    curve: CurveData
    confidence: float
    matched_by: str
    evidence: tuple[str, ...]

    @property
    def curve_id(self) -> str:
        return self.curve.metadata.curve_id

    @property
    def source_mnemonic(self) -> str:
        return self.curve.metadata.original_mnemonic

    @property
    def unit(self) -> str:
        return (self.curve.metadata.unit or "").strip()


@dataclass(frozen=True, slots=True)
class DatasetParameterResolution:
    """Immutable result of resolving all relevant curves in one dataset."""

    matches: Mapping[str, ParameterMatch]
    ambiguities: Mapping[str, tuple[ParameterMatch, ...]]
    unresolved_curve_ids: tuple[str, ...]

    def get(self, canonical_mnemonic: str) -> ParameterMatch | None:
        return self.matches.get(canonical_mnemonic.strip().upper())

    def require(self, canonical_mnemonic: str) -> ParameterMatch:
        canonical = canonical_mnemonic.strip().upper()
        ambiguous = self.ambiguities.get(canonical)
        if ambiguous:
            choices = ", ".join(
                f"{item.source_mnemonic} ({item.confidence:.0%})" for item in ambiguous
            )
            raise ParameterResolutionError(
                f"Параметр {canonical} определён неоднозначно: {choices}. "
                "Выберите правильную кривую в сопоставлении параметров.",
                code="ambiguous",
                values={"parameter": canonical, "choices": choices},
            )
        match = self.matches.get(canonical)
        if match is None:
            raise ParameterResolutionError(
                f"Не удалось определить обязательный параметр {canonical}",
                code="missing",
                values={"parameter": canonical},
            )
        return match


# The supplemental dictionary intentionally contains common mud-logging, drilling and
# petrophysical spellings that are encountered in LAS files but are not guaranteed to be
# present in one vendor catalog. The Sensor catalog remains the primary reference; these
# aliases are a controlled compatibility layer, not an unrestricted fuzzy dictionary.
_PARAMETER_ALIASES: dict[str, tuple[str, ...]] = {
    "C1": (
        "C1",
        "C-1",
        "C_1",
        "CH4",
        "CH-4",
        "METH",
        "METHANE",
        "METAN",
        "МЕТАН",
        "СОДЕРЖАНИЕ МЕТАНА",
        "СОД. МЕТАНА",
        "METHANE CONTENT",
        "GAS C1",
        "C1 GAS",
    ),
    "C2": (
        "C2",
        "C-2",
        "C_2",
        "C2H6",
        "ETH",
        "ETHANE",
        "ЭТАН",
        "СОДЕРЖАНИЕ ЭТАНА",
        "СОД. ЭТАНА",
        "ETHANE CONTENT",
        "GAS C2",
        "C2 GAS",
    ),
    "C3": (
        "C3",
        "C-3",
        "C_3",
        "C3H8",
        "PROP",
        "PROPANE",
        "ПРОПАН",
        "СОДЕРЖАНИЕ ПРОПАНА",
        "СОД. ПРОПАНА",
        "PROPANE CONTENT",
        "GAS C3",
        "C3 GAS",
    ),
    "C4": ("C4", "BUTANE", "БУТАН", "TOTAL BUTANE", "СУММАРНЫЙ БУТАН"),
    "IC4": ("IC4", "I-C4", "I C4", "ISOBUTANE", "ISO BUTANE", "ИЗОБУТАН"),
    "NC4": (
        "NC4",
        "N-C4",
        "N C4",
        "NORMAL BUTANE",
        "N-BUTANE",
        "Н-БУТАН",
        "НОРМАЛЬНЫЙ БУТАН",
    ),
    "C5": ("C5", "PENTANE", "ПЕНТАН", "TOTAL PENTANE", "СУММАРНЫЙ ПЕНТАН"),
    "IC5": ("IC5", "I-C5", "I C5", "ISOPENTANE", "ISO PENTANE", "ИЗОПЕНТАН"),
    "NC5": (
        "NC5",
        "N-C5",
        "N C5",
        "NORMAL PENTANE",
        "N-PENTANE",
        "Н-ПЕНТАН",
        "НОРМАЛЬНЫЙ ПЕНТАН",
    ),
    "TG": (
        "TG",
        "TOTAL GAS",
        "TOTAL_GAS",
        "TOTALGAS",
        "SUM GAS",
        "SUM_GAS",
        "GAS TOTAL",
        "СУММА ГАЗОВ",
        "ОБЩИЙ ГАЗ",
        "ЖАЛПЫ ГАЗ",
    ),
    "CO2": ("CO2", "CARBON DIOXIDE", "УГЛЕКИСЛЫЙ ГАЗ", "ДИОКСИД УГЛЕРОДА"),
    "H2S": ("H2S", "HYDROGEN SULFIDE", "СЕРОВОДОРОД", "КҮКІРТТІ СУТЕК"),
    "N2": ("N2", "NITROGEN", "АЗОТ"),
    "DEXP": ("DEXP", "D-EXPONENT", "D EXPONENT", "D-ЭКСПОНЕНТ", "Д-ЭКСПОНЕНТ"),
    "DMC": (
        "DMC",
        "DMK",
        "MIN_PER_M",
        "DRILLING TIME PER METRE",
        "DRILLING TIME PER METER",
        "ВРЕМЯ БУРЕНИЯ НА МЕТР",
        "ДМК",
    ),
    "CACO3": (
        "CACO3",
        "CA CO3",
        "CALCITE",
        "CALCIUM CARBONATE",
        "КАЛЬЦИТ",
        "КАРБОНАТ КАЛЬЦИЯ",
    ),
    "CAMG_CO3_2": (
        "CAMG_CO3_2",
        "CAMG(CO3)2",
        "DOLOMITE",
        "CALCIUM MAGNESIUM CARBONATE",
        "ДОЛОМИТ",
    ),
    "ROP": (
        "ROP",
        "RATE OF PENETRATION",
        "DRILL RATE",
        "DRILLING RATE",
        "СКОРОСТЬ БУРЕНИЯ",
        "МЕХАНИЧЕСКАЯ СКОРОСТЬ",
        "БҰРҒЫЛАУ ЖЫЛДАМДЫҒЫ",
    ),
    "WOB": ("WOB", "WEIGHT ON BIT", "BIT WEIGHT", "НАГРУЗКА НА ДОЛОТО"),
    "RPM": ("RPM", "ROTARY SPEED", "BIT RPM", "ОБОРОТЫ", "ЧАСТОТА ВРАЩЕНИЯ"),
    "TQ": ("TQ", "TORQUE", "ROTARY TORQUE", "МОМЕНТ", "КРУТЯЩИЙ МОМЕНТ"),
    "SPP": ("SPP", "STANDPIPE PRESSURE", "PUMP PRESSURE", "ДАВЛЕНИЕ НА СТОЯКЕ"),
    "HKLD": ("HKLD", "HOOKLOAD", "HOOK LOAD", "ВЕС НА КРЮКЕ"),
    "FLOW_IN": ("FLOW IN", "FLOW_IN", "QIN", "IN FLOW", "РАСХОД НА ВХОДЕ"),
    "FLOW_OUT": ("FLOW OUT", "FLOW_OUT", "QOUT", "OUT FLOW", "РАСХОД НА ВЫХОДЕ"),
    "MW_IN": ("MW IN", "MW_IN", "MUD WEIGHT IN", "MUD DENSITY IN", "ПЛОТНОСТЬ НА ВХОДЕ"),
    "MW_OUT": (
        "MW OUT",
        "MW_OUT",
        "MUD WEIGHT OUT",
        "MUD DENSITY OUT",
        "ПЛОТНОСТЬ НА ВЫХОДЕ",
    ),
    "TEMP_IN": ("TEMP IN", "TEMP_IN", "MUD TEMPERATURE IN", "ТЕМПЕРАТУРА НА ВХОДЕ"),
    "TEMP_OUT": (
        "TEMP OUT",
        "TEMP_OUT",
        "MUD TEMPERATURE OUT",
        "ТЕМПЕРАТУРА НА ВЫХОДЕ",
    ),
    "PIT_VOL": ("PIT VOL", "PIT_VOL", "PIT VOLUME", "TOTAL PIT VOLUME", "ОБЪЕМ ЕМКОСТЕЙ"),
    "GR": ("GR", "GAMMA RAY", "GAMMA_RAY", "ГАММА КАРОТАЖ", "ГАММА-КАРОТАЖ"),
    "SP": ("SP", "SPONTANEOUS POTENTIAL", "SELF POTENTIAL", "ПС", "САМОПРОИЗВОЛЬНЫЙ ПОТЕНЦИАЛ"),
    "CALI": ("CALI", "CALIPER", "BOREHOLE DIAMETER", "КАВЕРНОМЕР", "ДИАМЕТР СКВАЖИНЫ"),
    "RHOB": ("RHOB", "BULK DENSITY", "DENSITY", "ОБЪЕМНАЯ ПЛОТНОСТЬ"),
    "NPHI": ("NPHI", "NEUTRON POROSITY", "НЕЙТРОННАЯ ПОРИСТОСТЬ"),
    "DT": ("DT", "SONIC", "ACOUSTIC SLOWNESS", "ИНТЕРВАЛЬНОЕ ВРЕМЯ"),
}

_GAS_COMPONENTS = frozenset({"C1", "C2", "C3", "C4", "IC4", "NC4", "C5", "IC5", "NC5"})
_GAS_PARAMETERS = _GAS_COMPONENTS | {"TG", "CO2", "H2S", "N2"}

# Suffixes frequently added by acquisition systems to otherwise useful mnemonics.
_MNEMONIC_SUFFIX_RE = re.compile(r"(?:PCT|PERCENT|VOL|VOLPCT|PPM|PPMV|PPB|RAW|AVG|MEAN)$")


def _alias_index() -> dict[str, tuple[str, ...]]:
    index: dict[str, list[str]] = {}
    for canonical, aliases in _PARAMETER_ALIASES.items():
        for alias in (canonical, *aliases):
            key = normalize_sensor_key(alias)
            if key:
                index.setdefault(key, []).append(canonical)
    return {key: tuple(dict.fromkeys(values)) for key, values in index.items()}


_ALIAS_INDEX = _alias_index()


class LasParameterResolver:
    """Resolve vendor-specific LAS curves to canonical engineering parameters.

    Matching is deliberately evidence based. Exact mnemonic and user mappings have the
    highest priority; descriptions, catalog references and controlled fuzzy rules are used
    only when they are sufficiently specific. Curve order is never considered.
    """

    def __init__(self, catalog: SensorCatalog | None = None) -> None:
        self.catalog = catalog or active_sensor_catalog()

    def infer_curve(
        self,
        curve: CurveData,
        *,
        user_mapping: str | None = None,
    ) -> tuple[ParameterMatch, ...]:
        metadata = curve.metadata
        candidates: dict[str, ParameterMatch] = {}

        if user_mapping:
            canonical = user_mapping.strip().upper()
            if canonical:
                self._add_candidate(
                    candidates,
                    ParameterMatch(
                        canonical,
                        curve,
                        1.0,
                        "user_mapping",
                        ("пользовательское сопоставление",),
                    ),
                )

        mnemonic_values = tuple(
            dict.fromkeys(
                value
                for value in (
                    metadata.canonical_mnemonic or "",
                    metadata.original_mnemonic,
                )
                if value
            )
        )
        for value in mnemonic_values:
            self._match_alias_value(candidates, curve, value, is_description=False)

        description = (metadata.description or "").strip()
        if description:
            self._match_alias_value(candidates, curve, description, is_description=True)

        requested = metadata.canonical_mnemonic or metadata.original_mnemonic
        catalog_match = self.catalog.match(
            requested,
            description=description,
            unit=metadata.unit or "",
        )
        if catalog_match is None and requested != metadata.original_mnemonic:
            catalog_match = self.catalog.match(
                metadata.original_mnemonic,
                description=description,
                unit=metadata.unit or "",
            )
        if catalog_match is not None:
            definition = catalog_match.definition
            confidence = min(1.0, max(0.0, catalog_match.confidence))
            self._add_candidate(
                candidates,
                ParameterMatch(
                    definition.canonical_mnemonic.strip().upper(),
                    curve,
                    confidence,
                    f"catalog_{catalog_match.matched_by}",
                    (
                        f"Sensors: {definition.sensor_id}",
                        f"источник: {definition.source or self.catalog.catalog_name}",
                    ),
                ),
            )

        adjusted = [self._apply_unit_evidence(item) for item in candidates.values()]
        return tuple(
            sorted(
                adjusted,
                key=lambda item: (
                    -item.confidence,
                    item.canonical_mnemonic,
                    item.curve_id,
                ),
            )
        )

    def resolve_dataset(
        self,
        dataset: Dataset,
        *,
        targets: Iterable[str] | None = None,
        user_mappings: Mapping[str, str] | None = None,
        minimum_confidence: float = 0.65,
    ) -> DatasetParameterResolution:
        target_set = {item.strip().upper() for item in targets or () if item.strip()}
        user_mappings = user_mappings or {}
        grouped: dict[str, list[ParameterMatch]] = {}
        unresolved: list[str] = []

        for curve in dataset.curves.values():
            user_mapping = _lookup_user_mapping(curve, user_mappings)
            candidates = self.infer_curve(curve, user_mapping=user_mapping)
            if target_set:
                candidates = tuple(
                    item for item in candidates if item.canonical_mnemonic in target_set
                )
            candidates = tuple(item for item in candidates if item.confidence >= minimum_confidence)
            if not candidates:
                unresolved.append(curve.metadata.curve_id)
                continue
            # One curve may produce several semantic candidates. Only its strongest candidate
            # participates in the dataset-level competition unless confidence is exactly tied.
            best_confidence = candidates[0].confidence
            for candidate in candidates:
                if best_confidence - candidate.confidence > 0.005:
                    break
                grouped.setdefault(candidate.canonical_mnemonic, []).append(candidate)

        matches: dict[str, ParameterMatch] = {}
        ambiguities: dict[str, tuple[ParameterMatch, ...]] = {}
        for canonical, candidates in grouped.items():
            ordered = sorted(candidates, key=_dataset_candidate_key)
            best = ordered[0]
            tied = tuple(
                item
                for item in ordered
                if abs(item.confidence - best.confidence) <= 0.01
                and _coverage_ratio(item.curve) == _coverage_ratio(best.curve)
            )
            if len({item.curve_id for item in tied}) > 1 and best.matched_by != "user_mapping":
                ambiguities[canonical] = tied
            else:
                matches[canonical] = best

        return DatasetParameterResolution(
            MappingProxyType(matches),
            MappingProxyType(ambiguities),
            tuple(unresolved),
        )

    def _match_alias_value(
        self,
        candidates: dict[str, ParameterMatch],
        curve: CurveData,
        value: str,
        *,
        is_description: bool,
    ) -> None:
        key = normalize_sensor_key(value)
        if not key:
            return

        exact = _ALIAS_INDEX.get(key, ())
        for canonical in exact:
            self._add_candidate(
                candidates,
                ParameterMatch(
                    canonical,
                    curve,
                    0.93 if is_description else 0.985,
                    "description_alias" if is_description else "mnemonic_alias",
                    (f"совпадение: {value}",),
                ),
            )

        stripped = _MNEMONIC_SUFFIX_RE.sub("", key)
        if stripped != key:
            for canonical in _ALIAS_INDEX.get(stripped, ()):
                self._add_candidate(
                    candidates,
                    ParameterMatch(
                        canonical,
                        curve,
                        0.91 if not is_description else 0.84,
                        "mnemonic_suffix" if not is_description else "description_suffix",
                        (f"обозначение без служебного суффикса: {value}",),
                    ),
                )

        if is_description and len(key) >= 7:
            for alias_key, canonicals in _ALIAS_INDEX.items():
                # Very short aliases (C1, SP, GR) are unsafe as substrings of a sentence.
                if len(alias_key) < 5:
                    continue
                if alias_key in key or key in alias_key:
                    for canonical in canonicals:
                        self._add_candidate(
                            candidates,
                            ParameterMatch(
                                canonical,
                                curve,
                                0.84,
                                "description_contains",
                                (f"описание содержит термин: {value}",),
                            ),
                        )

        # Controlled patterns cover common acquisition-system wrappers such as GAS_C1_PPM.
        if not is_description:
            gas_match = re.fullmatch(r"(?:GAS|CHROM|GC)?(IC|NC)?C([1-5])", stripped)
            if gas_match:
                prefix, number = gas_match.groups()
                canonical = f"{prefix or ''}C{number}"
                if canonical in _GAS_COMPONENTS:
                    self._add_candidate(
                        candidates,
                        ParameterMatch(
                            canonical,
                            curve,
                            0.88,
                            "gas_mnemonic_pattern",
                            (f"структура газовой мнемоники: {value}",),
                        ),
                    )

    @staticmethod
    def _add_candidate(
        candidates: dict[str, ParameterMatch],
        candidate: ParameterMatch,
    ) -> None:
        current = candidates.get(candidate.canonical_mnemonic)
        if current is None or candidate.confidence > current.confidence:
            candidates[candidate.canonical_mnemonic] = candidate

    @staticmethod
    def _apply_unit_evidence(candidate: ParameterMatch) -> ParameterMatch:
        canonical = candidate.canonical_mnemonic
        unit = candidate.unit
        confidence = candidate.confidence
        evidence = list(candidate.evidence)
        if canonical in _GAS_PARAMETERS:
            scale = concentration_scale_to_percent(unit)
            if scale is not None:
                confidence = min(1.0, confidence + 0.01)
                evidence.append(f"единица концентрации: {unit or 'не указана'}")
            elif unit and _looks_like_non_concentration_unit(unit):
                confidence = max(0.0, confidence - 0.35)
                evidence.append(f"единица противоречит газовой концентрации: {unit}")
        return ParameterMatch(
            candidate.canonical_mnemonic,
            candidate.curve,
            confidence,
            candidate.matched_by,
            tuple(evidence),
        )


def infer_canonical_mnemonic(
    mnemonic: str,
    *,
    description: str = "",
    unit: str = "",
    catalog: SensorCatalog | None = None,
    minimum_confidence: float = 0.84,
) -> str | None:
    """Infer a canonical mnemonic for import without losing the original LAS name."""

    from geoworkbench.domain.models import CurveMetadata

    temporary_curve = CurveData(
        CurveMetadata(
            curve_id="resolver-preview",
            original_mnemonic=mnemonic,
            canonical_mnemonic=mnemonic,
            unit=unit or None,
            description=description or None,
            source_dataset_id="resolver-preview",
        ),
        np.empty(0, dtype=np.float64),
    )
    matches = LasParameterResolver(catalog).infer_curve(temporary_curve)
    if not matches or matches[0].confidence < minimum_confidence:
        return None
    if len(matches) > 1 and abs(matches[0].confidence - matches[1].confidence) <= 0.01:
        return None
    return matches[0].canonical_mnemonic


def resolve_gas_ratio_inputs(
    dataset: Dataset,
    *,
    resolver: LasParameterResolver | None = None,
    user_mappings: Mapping[str, str] | None = None,
) -> dict[str, Array]:
    """Resolve and normalize gas curves required by the basic Gas Ratio calculation."""

    parameter_resolver = resolver or LasParameterResolver()
    targets = ("C1", "C2", "C3", "C4", "IC4", "NC4", "C5", "IC5", "NC5")
    resolution = parameter_resolver.resolve_dataset(
        dataset,
        targets=targets,
        user_mappings=user_mappings,
    )
    required_matches = [resolution.require(name) for name in ("C1", "C2", "C3")]
    optional_matches = [
        match
        for name in targets[3:]
        if (match := resolution.get(name)) is not None
    ]
    selected = required_matches + optional_matches
    scales = _resolve_concentration_scales(selected)
    return {
        match.canonical_mnemonic: np.asarray(match.curve.values, dtype=np.float64)
        * scales[match.curve_id]
        for match in selected
    }


def concentration_scale_to_percent(unit: str | None) -> float | None:
    """Return a multiplier converting a concentration unit to percent by volume."""

    raw = (unit or "").strip()
    if not raw:
        return None
    normalized = normalize_unit(raw).casefold()
    normalized = normalized.replace("об.%", "%").replace("vol.", "vol")
    normalized = re.sub(r"[\s_\-]", "", normalized)
    percent_units = {
        "%",
        "pct",
        "percent",
        "percentage",
        "vol%",
        "%vol",
        "v/v%",
        "mol%",
        "%mol",
        "процент",
        "проценты",
    }
    if normalized in percent_units:
        return 1.0
    if normalized in {"ppm", "ppmv", "ppmvol"}:
        return 1.0e-4
    if normalized in {"ppb", "ppbv", "ppbvol"}:
        return 1.0e-7
    if normalized in {"fraction", "volfraction", "v/v", "ratio", "unitless", "1"}:
        return 100.0
    return None


def _resolve_concentration_scales(matches: Iterable[ParameterMatch]) -> dict[str, float]:
    values = tuple(matches)
    known: dict[str, float] = {}
    unknown: list[ParameterMatch] = []
    for match in values:
        scale = concentration_scale_to_percent(match.unit)
        if scale is None:
            unknown.append(match)
        else:
            known[match.curve_id] = scale

    if not unknown:
        return known
    if not known:
        # All components have the same unknown/empty scale. Ratios remain valid and the
        # calculated total preserves that common source scale.
        normalized_units = {normalize_unit(item.unit) for item in unknown if item.unit}
        if len(normalized_units) > 1:
            units = ", ".join(sorted(normalized_units))
            raise ParameterResolutionError(
                f"Газовые компоненты имеют несовместимые неизвестные единицы: {units}",
                code="unknown_units",
                values={"units": units},
            )
        return {item.curve_id: 1.0 for item in unknown}

    known_scales = set(known.values())
    if len(known_scales) == 1 and all(not item.unit for item in unknown):
        inferred = next(iter(known_scales))
        # Missing units are commonly caused by incomplete LAS headers. When every known gas
        # component agrees, inheriting the common scale is deterministic and auditable.
        known.update({item.curve_id: inferred for item in unknown})
        return known

    details = ", ".join(
        f"{item.source_mnemonic} [{item.unit or 'единица не указана'}]" for item in unknown
    )
    raise ParameterResolutionError(
        "Невозможно безопасно привести газовые компоненты к одной единице: " + details,
        code="unit_conversion",
        values={"details": details},
    )


def _lookup_user_mapping(curve: CurveData, mappings: Mapping[str, str]) -> str | None:
    metadata = curve.metadata
    for key in (
        metadata.curve_id,
        metadata.original_mnemonic,
        normalize_sensor_key(metadata.original_mnemonic),
    ):
        if key in mappings:
            return mappings[key]
    return None


def _coverage_ratio(curve: CurveData) -> float:
    values = np.asarray(curve.values, dtype=np.float64)
    if values.size == 0:
        return 0.0
    return float(np.count_nonzero(np.isfinite(values))) / float(values.size)


def _dataset_candidate_key(candidate: ParameterMatch) -> tuple[float, float, int, str]:
    return (
        -candidate.confidence,
        -_coverage_ratio(candidate.curve),
        0 if candidate.matched_by == "user_mapping" else 1,
        candidate.curve_id,
    )


def _looks_like_non_concentration_unit(unit: str) -> bool:
    normalized = normalize_unit(unit)
    non_concentration_tokens = {
        "m",
        "ft",
        "m/h",
        "ft/h",
        "rpm",
        "psi",
        "bar",
        "mpa",
        "g/cm3",
        "kg/m3",
        "degc",
        "c",
        "f",
        "api",
    }
    return normalized in non_concentration_tokens
