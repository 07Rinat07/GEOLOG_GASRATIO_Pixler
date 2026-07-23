from __future__ import annotations

from geoworkbench.services.uom_dictionary import QuantityClass, UomDictionary


def test_uom_dictionary_normalizes_common_russian_and_las_units() -> None:
    dictionary = UomDictionary()

    assert dictionary.resolve("м/ч").canonical == "m/h"
    assert dictionary.resolve("м/ч").quantity_class is QuantityClass.LINEAR_VELOCITY
    assert dictionary.resolve("g/cm³").canonical == "g/cm3"
    assert dictionary.resolve("ohm*m").quantity_class is QuantityClass.RESISTIVITY
    assert dictionary.resolve("µs/ft").quantity_class is QuantityClass.SLOWNESS


def test_uom_dictionary_keeps_unknown_vendor_unit_explicit() -> None:
    resolution = UomDictionary().resolve("vendorTicks")

    assert resolution.recognized is False
    assert resolution.canonical == "vendorTicks"
    assert resolution.quantity_class is QuantityClass.UNKNOWN


def test_uom_compatibility_is_quantity_based_and_unknown_is_indeterminate() -> None:
    dictionary = UomDictionary()

    assert dictionary.compatible("м", "ft") is True
    assert dictionary.compatible("м", "psi") is False
    assert dictionary.compatible("м", "vendor") is None


def test_uom_dictionary_covers_engineering_units_used_by_sensor_catalog() -> None:
    dictionary = UomDictionary()

    assert dictionary.resolve("мкр/ч").canonical == "uR/h"
    assert dictionary.resolve("мкр/ч").quantity_class is QuantityClass.GAMMA_RAY
    assert dictionary.resolve("b/e").quantity_class is QuantityClass.DIMENSIONLESS
    assert dictionary.resolve("gauss").quantity_class is QuantityClass.MAGNETIC_FLUX_DENSITY
