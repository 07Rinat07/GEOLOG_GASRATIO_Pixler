from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Iterable, Sequence

import numpy as np


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


@dataclass(frozen=True, slots=True)
class UomConversion:
    source_uom: str
    target_uom: str
    quantity_class: QuantityClass
    scale: float
    offset: float = 0.0

    def convert_scalar(self, value: float | int) -> float:
        return float(value) * self.scale + self.offset

    def convert_array(self, values: Sequence[float] | np.ndarray) -> np.ndarray:
        array = np.asarray(values, dtype=np.float64)
        return array * self.scale + self.offset


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
    UomDefinition("cm", QuantityClass.LENGTH, ("centimeter", "centimetre", "см")),
    UomDefinition("mm", QuantityClass.LENGTH, ("millimeter", "millimetre", "мм")),
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
    UomDefinition("lbf", QuantityClass.FORCE, ("lb-force", "pound-force", "lbs")),
    UomDefinition("klbf", QuantityClass.FORCE, ("kip", "1000 lbf", "10^3 lbf")),
    UomDefinition("kgf", QuantityClass.FORCE, ("kilogram-force", "кгс")),
    UomDefinition("tf", QuantityClass.FORCE, ("tonne-force", "ton-force", "тс")),
    UomDefinition("N.m", QuantityClass.TORQUE, ("n*m", "nm", "н.м", "н*м")),
    UomDefinition("t.m", QuantityClass.TORQUE, ("t*m", "т.м", "т*м")),
    UomDefinition("m3", QuantityClass.VOLUME, ("m^3", "м3", "м^3")),
    UomDefinition("cm3", QuantityClass.VOLUME, ("cm^3", "см3", "см^3")),
    UomDefinition("L", QuantityClass.VOLUME, ("l", "liter", "litre", "л")),
    UomDefinition("m3/h", QuantityClass.VOLUME_FLOW_RATE, ("m3/hr", "м3/ч")),
    UomDefinition("m3/min", QuantityClass.VOLUME_FLOW_RATE, ("м3/мин",)),
    UomDefinition("m3/s", QuantityClass.VOLUME_FLOW_RATE, ("м3/с",)),
    UomDefinition("L/min", QuantityClass.VOLUME_FLOW_RATE, ("l/min", "л/мин")),
    UomDefinition("L/s", QuantityClass.VOLUME_FLOW_RATE, ("l/s", "л/с", "л/c")),
    UomDefinition("gpm", QuantityClass.VOLUME_FLOW_RATE, ("gal/min", "us gal/min")),
    UomDefinition("kg/m3", QuantityClass.MASS_DENSITY, ("kg/m^3", "кг/м3", "кг/м^3")),
    UomDefinition("g/cm3", QuantityClass.MASS_DENSITY, ("g/cm^3", "г/см3", "г/см^3")),
    UomDefinition("ppg", QuantityClass.MASS_DENSITY, ("lb/gal", "lbs/gal")),
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


# Canonical-unit conversion entries use: family, scale-to-base, offset-to-base.
# A conversion is allowed only inside the same family. This is intentionally stricter
# than QuantityClass because, for example, API and uR/h are both gamma-ray units but
# do not have a universal linear conversion.
_CONVERSION_TO_BASE: dict[str, tuple[str, float, float]] = {
    "1": ("dimensionless", 1.0, 0.0),
    "v/v": ("volume_fraction", 1.0, 0.0),
    "%": ("volume_fraction", 1e-2, 0.0),
    "ppm": ("volume_fraction", 1e-6, 0.0),
    "ppb": ("volume_fraction", 1e-9, 0.0),
    "m": ("length", 1.0, 0.0),
    "cm": ("length", 1e-2, 0.0),
    "mm": ("length", 1e-3, 0.0),
    "ft": ("length", 0.3048, 0.0),
    "in": ("length", 0.0254, 0.0),
    "s": ("time", 1.0, 0.0),
    "min": ("time", 60.0, 0.0),
    "h": ("time", 3600.0, 0.0),
    "m/s": ("linear_velocity", 1.0, 0.0),
    "m/h": ("linear_velocity", 1.0 / 3600.0, 0.0),
    "ft/h": ("linear_velocity", 0.3048 / 3600.0, 0.0),
    "min/m": ("slowness", 60.0, 0.0),
    "us/ft": ("slowness", 1e-6 / 0.3048, 0.0),
    "Pa": ("pressure", 1.0, 0.0),
    "kPa": ("pressure", 1e3, 0.0),
    "MPa": ("pressure", 1e6, 0.0),
    "bar": ("pressure", 1e5, 0.0),
    "psi": ("pressure", 6894.757293168, 0.0),
    "atm": ("pressure", 101325.0, 0.0),
    "kg": ("mass", 1.0, 0.0),
    "g": ("mass", 1e-3, 0.0),
    "t": ("mass", 1e3, 0.0),
    "N": ("force", 1.0, 0.0),
    "kN": ("force", 1e3, 0.0),
    "lbf": ("force", 4.4482216152605, 0.0),
    "klbf": ("force", 4448.2216152605, 0.0),
    "kgf": ("force", 9.80665, 0.0),
    "tf": ("force", 9806.65, 0.0),
    "N.m": ("torque", 1.0, 0.0),
    "t.m": ("torque", 9806.65, 0.0),
    "m3": ("volume", 1.0, 0.0),
    "cm3": ("volume", 1e-6, 0.0),
    "L": ("volume", 1e-3, 0.0),
    "m3/h": ("volume_flow_rate", 1.0 / 3600.0, 0.0),
    "m3/min": ("volume_flow_rate", 1.0 / 60.0, 0.0),
    "m3/s": ("volume_flow_rate", 1.0, 0.0),
    "L/min": ("volume_flow_rate", 1e-3 / 60.0, 0.0),
    "L/s": ("volume_flow_rate", 1e-3, 0.0),
    "gpm": ("volume_flow_rate", 0.003785411784 / 60.0, 0.0),
    "kg/m3": ("mass_density", 1.0, 0.0),
    "g/cm3": ("mass_density", 1000.0, 0.0),
    "ppg": ("mass_density", 119.826427316, 0.0),
    "degC": ("temperature_c", 1.0, 0.0),
    "deg": ("angle", 1.0, 0.0),
    "mg/L": ("mass_concentration", 1.0, 0.0),
    "mg/g": ("mass_fraction", 1.0, 0.0),
    "mS/cm": ("conductivity", 1.0, 0.0),
    "ohm.m": ("resistivity", 1.0, 0.0),
    "mD": ("permeability", 1.0, 0.0),
    "V": ("electric_potential", 1.0, 0.0),
    "mV": ("electric_potential", 1e-3, 0.0),
    "A": ("electric_current", 1.0, 0.0),
    "mA": ("electric_current", 1e-3, 0.0),
}


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

    def conversion(self, source: str | None, target: str | None) -> UomConversion | None:
        left = self.resolve(source)
        right = self.resolve(target)
        if not left.recognized or not right.recognized:
            return None
        if left.quantity_class is not right.quantity_class:
            return None
        if left.canonical == right.canonical:
            return UomConversion(
                left.canonical, right.canonical, left.quantity_class, 1.0, 0.0
            )
        source_entry = _CONVERSION_TO_BASE.get(left.canonical)
        target_entry = _CONVERSION_TO_BASE.get(right.canonical)
        if source_entry is None or target_entry is None:
            return None
        source_family, source_scale, source_offset = source_entry
        target_family, target_scale, target_offset = target_entry
        if source_family != target_family:
            return None
        scale = source_scale / target_scale
        offset = (source_offset - target_offset) / target_scale
        return UomConversion(
            left.canonical, right.canonical, left.quantity_class, scale, offset
        )

    def convert_scalar(
        self, value: float | int, source: str | None, target: str | None
    ) -> float:
        conversion = self.conversion(source, target)
        if conversion is None:
            raise ValueError(f"Unsupported UOM conversion: {source!r} -> {target!r}")
        return conversion.convert_scalar(value)

    def convert_array(
        self, values: Sequence[float] | np.ndarray, source: str | None, target: str | None
    ) -> np.ndarray:
        conversion = self.conversion(source, target)
        if conversion is None:
            raise ValueError(f"Unsupported UOM conversion: {source!r} -> {target!r}")
        return conversion.convert_array(values)


_DEFAULT_DICTIONARY = UomDictionary()


def default_uom_dictionary() -> UomDictionary:
    return _DEFAULT_DICTIONARY
