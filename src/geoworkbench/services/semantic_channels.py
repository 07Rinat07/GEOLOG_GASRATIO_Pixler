from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from geoworkbench.catalogs.sensors import (
    SensorCatalog,
    SensorDefinition,
    default_sensor_catalog,
)
from geoworkbench.services.uom_dictionary import (
    QuantityClass,
    UomDictionary,
    default_uom_dictionary,
)


_KIND_TOKEN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class SemanticChannelDefinition:
    canonical_kind: str
    canonical_mnemonic: str
    quantity_class: QuantityClass
    canonical_uom: str | None
    aliases: tuple[str, ...]
    sensor_id: str | None
    source: str | None
    family: str
    category: str

    def __post_init__(self) -> None:
        if not self.canonical_kind.strip() or not self.canonical_mnemonic.strip():
            raise ValueError("Semantic channel definition requires canonical identifiers")
        if not isinstance(self.quantity_class, QuantityClass):
            raise ValueError("Semantic quantity class must use QuantityClass")
        if not self.aliases or any(not alias.strip() for alias in self.aliases):
            raise ValueError("Semantic channel aliases must be non-empty strings")


@dataclass(frozen=True, slots=True)
class SemanticChannelBinding:
    """Serializable semantic snapshot attached to one imported/project curve."""

    canonical_kind: str
    canonical_mnemonic: str
    quantity_class: QuantityClass
    canonical_uom: str | None
    source_uom: str | None
    aliases: tuple[str, ...]
    sensor_id: str | None
    source: str | None
    family: str
    category: str
    source_mnemonic: str
    confidence: float
    matched_by: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.canonical_kind.strip() or not self.canonical_mnemonic.strip():
            raise ValueError("Semantic channel binding requires canonical identifiers")
        if not self.source_mnemonic.strip():
            raise ValueError("Semantic channel binding requires the source mnemonic")
        if not isinstance(self.quantity_class, QuantityClass):
            raise ValueError("Semantic quantity class must use QuantityClass")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Semantic confidence must be in the range 0..1")
        if any(not alias.strip() for alias in self.aliases):
            raise ValueError("Semantic aliases must be non-empty strings")
        if any(not item.strip() for item in self.evidence):
            raise ValueError("Semantic evidence must be non-empty strings")

    @property
    def resolved(self) -> bool:
        return self.sensor_id is not None or self.confidence >= 0.8


_FAMILY_QUANTITY: dict[str, QuantityClass] = {
    "gas": QuantityClass.VOLUME_FRACTION,
    "rop": QuantityClass.LINEAR_VELOCITY,
    "rotary_speed": QuantityClass.ROTATIONAL_SPEED,
    "wob": QuantityClass.FORCE,
    "torque": QuantityClass.TORQUE,
    "pressure": QuantityClass.PRESSURE,
    "hookload": QuantityClass.FORCE,
    "flow": QuantityClass.VOLUME_FLOW_RATE,
    "drilling_depth": QuantityClass.LENGTH,
    "mud_density": QuantityClass.MASS_DENSITY,
    "temperature": QuantityClass.TEMPERATURE,
    "pit_volume": QuantityClass.VOLUME,
    "conductivity": QuantityClass.ELECTRICAL_CONDUCTIVITY,
    "chlorides": QuantityClass.MASS_CONCENTRATION,
    "gamma_ray": QuantityClass.GAMMA_RAY,
    "sp": QuantityClass.ELECTRIC_POTENTIAL,
    "caliper": QuantityClass.LENGTH,
    "bulk_density": QuantityClass.MASS_DENSITY,
    "neutron": QuantityClass.VOLUME_FRACTION,
    "sonic": QuantityClass.SLOWNESS,
    "resistivity": QuantityClass.RESISTIVITY,
    "pef": QuantityClass.DIMENSIONLESS,
    "dexp": QuantityClass.DIMENSIONLESS,
}


class SemanticChannelDictionary:
    """Single semantic resolver for LAS, CSV/Excel and Paradox channels.

    The existing Sensors catalog remains the source of aliases and vendor identifiers.
    This layer adds engineering semantics and captures a stable per-curve binding that
    can later be reviewed without re-running fuzzy matching against a newer catalog.
    """

    def __init__(
        self,
        catalog: SensorCatalog | None = None,
        uoms: UomDictionary | None = None,
    ) -> None:
        self.catalog = catalog or default_sensor_catalog()
        self.uoms = uoms or default_uom_dictionary()

    def definition(self, sensor: SensorDefinition) -> SemanticChannelDefinition:
        reference_uom = self.uoms.resolve(sensor.unit)
        family_quantity = _FAMILY_QUANTITY.get(sensor.family, QuantityClass.UNKNOWN)
        quantity = (
            family_quantity
            if family_quantity is not QuantityClass.UNKNOWN
            else reference_uom.quantity_class
            if reference_uom.recognized
            else QuantityClass.UNKNOWN
        )
        aliases = _unique((sensor.canonical_mnemonic, *sensor.aliases))
        return SemanticChannelDefinition(
            canonical_kind=_canonical_kind(sensor.category, sensor.canonical_mnemonic),
            canonical_mnemonic=sensor.canonical_mnemonic.strip().upper(),
            quantity_class=quantity,
            canonical_uom=(reference_uom.canonical or None) if reference_uom.recognized else (
                sensor.unit.strip() or None
            ),
            aliases=aliases,
            sensor_id=sensor.sensor_id,
            source=sensor.source or self.catalog.catalog_name,
            family=sensor.family,
            category=sensor.category,
        )

    def definitions(self) -> tuple[SemanticChannelDefinition, ...]:
        return tuple(self.definition(sensor) for sensor in self.catalog.sensors)

    def resolve(
        self,
        mnemonic: str,
        *,
        description: str = "",
        unit: str = "",
        source_mnemonic: str | None = None,
        canonical_mnemonic: str | None = None,
    ) -> SemanticChannelBinding:
        original = (source_mnemonic or mnemonic).strip() or mnemonic.strip()
        source_unit = unit.strip()
        source_uom = self.uoms.resolve(source_unit)
        match = self.catalog.match(mnemonic, description=description, unit=source_unit)
        evidence: list[str] = []

        if match is None:
            canonical = (canonical_mnemonic or mnemonic).strip().upper()
            quantity = (
                source_uom.quantity_class if source_uom.recognized else QuantityClass.UNKNOWN
            )
            if source_unit and not source_uom.recognized:
                evidence.append(f"unrecognized source UOM: {source_unit}")
            evidence.append("no Sensors catalog match")
            return SemanticChannelBinding(
                canonical_kind=_canonical_kind("unknown", canonical),
                canonical_mnemonic=canonical,
                quantity_class=quantity,
                canonical_uom=(source_uom.canonical or None) if source_uom.recognized else (
                    source_unit or None
                ),
                source_uom=source_unit or None,
                aliases=_unique((canonical, mnemonic, original)),
                sensor_id=None,
                source=None,
                family="other",
                category="unknown",
                source_mnemonic=original,
                confidence=0.0,
                matched_by="unresolved",
                evidence=tuple(evidence),
            )

        definition = self.definition(match.definition)
        canonical = (canonical_mnemonic or definition.canonical_mnemonic).strip().upper()
        # A user-facing canonical mnemonic may be preserved from an older project, but the
        # engineering kind remains the catalog definition. Otherwise a display/name override
        # would silently create a different physical channel identity.
        canonical_kind = definition.canonical_kind
        confidence = match.confidence
        matched_by = f"sensor_{match.matched_by}"
        reference_uom = self.uoms.resolve(definition.canonical_uom)
        quantity = definition.quantity_class
        canonical_uom = definition.canonical_uom

        if canonical != definition.canonical_mnemonic:
            matched_by += "+canonical_hint"
            evidence.append(
                f"canonical mnemonic preserved as {canonical}; catalog suggested "
                f"{definition.canonical_mnemonic}"
            )
        if source_uom.recognized:
            if quantity is QuantityClass.UNKNOWN:
                quantity = source_uom.quantity_class
            if not canonical_uom:
                canonical_uom = source_uom.canonical or None
            if (
                reference_uom.recognized
                and source_uom.quantity_class is not reference_uom.quantity_class
            ):
                confidence = max(0.0, confidence - 0.25)
                evidence.append(
                    "source UOM quantity conflicts with catalog quantity: "
                    f"{source_unit} vs {definition.canonical_uom}"
                )
        elif source_unit:
            evidence.append(f"unrecognized source UOM: {source_unit}")

        evidence.extend(
            (
                f"sensor_id={definition.sensor_id}",
                f"source={definition.source}",
            )
        )
        return SemanticChannelBinding(
            canonical_kind=canonical_kind,
            canonical_mnemonic=canonical,
            quantity_class=quantity,
            canonical_uom=canonical_uom,
            source_uom=source_unit or None,
            aliases=_unique((canonical, *definition.aliases, mnemonic, original)),
            sensor_id=definition.sensor_id,
            source=definition.source,
            family=definition.family,
            category=definition.category,
            source_mnemonic=original,
            confidence=max(0.0, min(1.0, confidence)),
            matched_by=matched_by,
            evidence=tuple(evidence),
        )

    def search(self, text: str) -> tuple[SemanticChannelDefinition, ...]:
        return tuple(self.definition(sensor) for sensor in self.catalog.search(text))


def _canonical_kind(category: str, mnemonic: str) -> str:
    prefix = _KIND_TOKEN.sub("_", category.strip().casefold()).strip("_") or "unknown"
    token = _KIND_TOKEN.sub("_", mnemonic.strip().casefold()).strip("_") or "channel"
    return f"{prefix}.{token}"


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return tuple(result)


_DEFAULT_DICTIONARY: SemanticChannelDictionary | None = None


def default_semantic_channel_dictionary() -> SemanticChannelDictionary:
    global _DEFAULT_DICTIONARY
    if _DEFAULT_DICTIONARY is None:
        _DEFAULT_DICTIONARY = SemanticChannelDictionary()
    return _DEFAULT_DICTIONARY
