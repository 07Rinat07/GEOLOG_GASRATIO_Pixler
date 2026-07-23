from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Iterable


class QuantityClass(StrEnum):
    """Stable quantity classes used by semantic channels and Import Review.

    The names intentionally describe engineering meaning rather than display grouping.
    They are compatible with the Energistics concept that every UOM belongs to one
    quantity/measure class, while unknown vendor units remain explicit instead of being
    guessed.
    """

    UNKNOWN = "unknown"
    DIMENSIONLESS = "dimensionless"
    ANGLE = "angle"
    COUNT = "count"
    ELECTRIC_CURRENT = "electric_current"
    ELECTRIC_POTENTIAL = "electric_potential"
    ELECTRICAL_CONDUCTIVITY = "electrical_conductivity"
    FORCE = "force"
    FREQUENCY = "frequency"
    GAMMA_RAY = "gamma_ray"
    LENGTH = "length"
    LINEAR_VELOCITY = "linear_velocity"
    MASS = "mass"
    MASS_CONCENTRATION = "mass_concentration"
    MASS_DENSITY = "mass_density"
    MAGNETIC_FLUX_DENSITY = "magnetic_flux_density"
    PERMEABILITY = "permeability"
    PRESSURE = "pressure"
    RESISTIVITY = "resistivity"
    ROTATIONAL_SPEED = "rotational_speed"
    SLOWNESS = "slowness"
    TEMPERATURE = "temperature"
    TIME = "time"
    TORQUE = "torque"
    VOLUME = "volume"
    VOLUME_FLOW_RATE = "volume_flow_rate"
    VOLUME_FRACTION = "volume_fraction"


@dataclass(frozen=True, slots=True)
class UomDefinition:
    symbol: str
    quantity_class: QuantityClass
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UomResolution:
    source: str
    canonical: str
    quantity_class: QuantityClass
    recognized: bool


_NON_WORD = re.compile(r"\s+")


def normalize_uom_key(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = normalized.replace("³", "3").replace("²", "2").replace("·", ".")
    normalized = normalized.replace("°", "deg")
    normalized = normalized.replace("\\", "/")
    normalized = _NON_WORD.sub("", normalized)
    return normalized


_DEFAULT_UOMS: tuple[UomDefinition, ...] = (
    UomDefinition("1", QuantityClass.DIMENSIONLESS, ("unitless", "none", "безразм")),
    UomDefinition("%", QuantityClass.VOLUME_FRACTION, ("pct", "percent", "%vol", "vol%", "% отн")),
    UomDefinition("v/v", QuantityClass.VOLUME_FRACTION, ("vol/vol", "cm3/cm3", "см3/см3")),
    UomDefinition("ppm", QuantityClass.VOLUME_FRACTION, ("ppmv",)),
    UomDefinition("ppb", QuantityClass.VOLUME_FRACTION, ("ppbv",)),
    UomDefinition("m", QuantityClass.LENGTH, ("meter", "metre", "meters", "metres", "м")),
    UomDefinition("ft", QuantityClass.LENGTH, ("feet", "foot")),
    UomDefinition("in", QuantityClass.LENGTH, ("inch", "inches")),
    UomDefinition("s", QuantityClass.TIME, ("sec", "second", "seconds", "с")),
    UomDefinition("min", QuantityClass.TIME, ("minute", "minutes", "мин", "мин.")),
    UomDefinition("h", QuantityClass.TIME, ("hr", "hour", "hours", "ч", "ч.")),
    UomDefinition("m/s", QuantityClass.LINEAR_VELOCITY, ("м/с",)),
    UomDefinition("m/h", QuantityClass.LINEAR_VELOCITY, ("m/hr", "м/ч", "м/час")),
    UomDefinition("ft/h", QuantityClass.LINEAR_VELOCITY, ("ft/hr",)),
    UomDefinition("min/m", QuantityClass.SLOWNESS, ("мин/м",)),
    UomDefinition("us/ft", QuantityClass.SLOWNESS, ("µs/ft", "μs/ft")),
    UomDefinition("1/min", QuantityClass.ROTATIONAL_SPEED, ("rpm", "min-1", "мин-1")),
    UomDefinition("Hz", QuantityClass.FREQUENCY, ("hz.", "гц", "гц.")),
    UomDefinition("Pa", QuantityClass.PRESSURE, ("pa",)),
    UomDefinition("kPa", QuantityClass.PRESSURE, ("kpa",)),
    UomDefinition("MPa", QuantityClass.PRESSURE, ("mpa", "мпа")),
    UomDefinition("bar", QuantityClass.PRESSURE, ("bars",)),
    UomDefinition("psi", QuantityClass.PRESSURE, ()),
    UomDefinition("atm", QuantityClass.PRESSURE, ("атм",)),
    UomDefinition("kg", QuantityClass.MASS, ("кг",)),
    UomDefinition("g", QuantityClass.MASS, ("г",)),
    UomDefinition("t", QuantityClass.MASS, ("tonne", "ton", "т")),
    UomDefinition("N", QuantityClass.FORCE, ("newton", "н")),
    UomDefinition("kN", QuantityClass.FORCE, ("kn", "кн")),
    UomDefinition("N.m", QuantityClass.TORQUE, ("n*m", "nm", "н.м", "н*м")),
    UomDefinition("t.m", QuantityClass.TORQUE, ("t*m", "т.м", "т*м")),
    UomDefinition("m3", QuantityClass.VOLUME, ("m^3", "м3", "м^3")),
    UomDefinition("cm3", QuantityClass.VOLUME, ("cm^3", "см3", "см^3")),
    UomDefinition("L", QuantityClass.VOLUME, ("l", "liter", "litre", "л")),
    UomDefinition("m3/h", QuantityClass.VOLUME_FLOW_RATE, ("m3/hr", "м3/ч")),
    UomDefinition("L/s", QuantityClass.VOLUME_FLOW_RATE, ("l/s", "л/с", "л/c")),
    UomDefinition("kg/m3", QuantityClass.MASS_DENSITY, ("kg/m^3", "кг/м3", "кг/м^3")),
    UomDefinition("g/cm3", QuantityClass.MASS_DENSITY, ("g/cm^3", "г/см3", "г/см^3")),
    UomDefinition("degC", QuantityClass.TEMPERATURE, ("c", "degc", "°c", "сelsius")),
    UomDefinition("deg", QuantityClass.ANGLE, ("degree", "degrees", "град", "°")),
    UomDefinition("mg/L", QuantityClass.MASS_CONCENTRATION, ("mg/l", "мг/л")),
    UomDefinition("mg/g", QuantityClass.MASS_CONCENTRATION, ("мг/г",)),
    UomDefinition("mS/cm", QuantityClass.ELECTRICAL_CONDUCTIVITY, ("ms/cm", "мсм/см")),
    UomDefinition("ohm.m", QuantityClass.RESISTIVITY, ("ohm*m", "ohm-m", "ом.м", "ом*м")),
    UomDefinition("API", QuantityClass.GAMMA_RAY, ("gapi",)),
    UomDefinition("uR/h", QuantityClass.GAMMA_RAY, ("мкр/ч", "мкр/час", "ur/h")),
    UomDefinition("mD", QuantityClass.PERMEABILITY, ("md", "мд")),
    UomDefinition("V", QuantityClass.ELECTRIC_POTENTIAL, ("v", "в")),
    UomDefinition("mV", QuantityClass.ELECTRIC_POTENTIAL, ("mv", "мв")),
    UomDefinition("A", QuantityClass.ELECTRIC_CURRENT, ("a", "а", "а.")),
    UomDefinition("mA", QuantityClass.ELECTRIC_CURRENT, ("ma", "ма")),
    UomDefinition("gauss", QuantityClass.MAGNETIC_FLUX_DENSITY, ("гаусс",)),
    UomDefinition("b/e", QuantityClass.DIMENSIONLESS, ("barn/electron",)),
    UomDefinition("point", QuantityClass.COUNT, ("points", "балл", "баллы")),
)


class UomDictionary:
    """Immutable UOM alias dictionary with explicit unknown-unit handling."""

    def __init__(self, definitions: Iterable[UomDefinition] = _DEFAULT_UOMS) -> None:
        rows = tuple(definitions)
        if not rows:
            raise ValueError("UOM dictionary must contain at least one definition")
        index: dict[str, UomDefinition] = {}
        for definition in rows:
            values = (definition.symbol, *definition.aliases)
            for value in values:
                key = normalize_uom_key(value)
                if key in index and index[key] != definition:
                    raise ValueError(f"Duplicate UOM alias: {value}")
                index[key] = definition
        self.definitions = rows
        self._index = index

    def resolve(self, value: str | None) -> UomResolution:
        source = (value or "").strip()
        key = normalize_uom_key(source)
        if not key:
            return UomResolution(source, source, QuantityClass.UNKNOWN, False)
        definition = self._index.get(key)
        if definition is None:
            return UomResolution(source, source, QuantityClass.UNKNOWN, False)
        return UomResolution(
            source=source,
            canonical=definition.symbol,
            quantity_class=definition.quantity_class,
            recognized=True,
        )

    def compatible(self, first: str | None, second: str | None) -> bool | None:
        left = self.resolve(first)
        right = self.resolve(second)
        if not left.recognized or not right.recognized:
            return None
        return left.quantity_class is right.quantity_class


_DEFAULT_DICTIONARY = UomDictionary()


def default_uom_dictionary() -> UomDictionary:
    return _DEFAULT_DICTIONARY
