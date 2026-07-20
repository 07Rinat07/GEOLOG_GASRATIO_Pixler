import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.catalogs.sensors import default_sensor_catalog
from geoworkbench.services.curve_catalog import (
    CurveCategory,
    CurveFamily,
    analyze_dataset_curves,
    recommended_curve_mnemonics,
)


def make_dataset() -> Dataset:
    dataset = Dataset(
        "dataset",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    for mnemonic, unit, description, values in (
        ("C1", "%", "Methane", [1.0, 2.0, np.nan]),
        ("BIT_RPM", "rpm", "Bit rotation", [100.0, 110.0, 120.0]),
        ("MW", "g/cm3", "Mud weight", [1.1, 1.2, 1.3]),
        ("EMPTY", "", "No data", [np.nan, np.nan, np.nan]),
    ):
        curve_id = f"curve-{mnemonic}"
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                mnemonic,
                mnemonic,
                unit,
                description,
                dataset.dataset_id,
            ),
            np.asarray(values, dtype=float),
        )
    return dataset


def test_curve_catalog_exposes_quality_range_and_category() -> None:
    entries = {item.mnemonic: item for item in analyze_dataset_curves(make_dataset())}

    assert entries["C1"].category is CurveCategory.GAS
    assert entries["C1"].valid_count == 2
    assert entries["C1"].coverage_percent == 100.0 * 2.0 / 3.0
    assert entries["C1"].range_text == "1 … 2"
    assert entries["BIT_RPM"].category is CurveCategory.DRILLING
    assert entries["BIT_RPM"].family is CurveFamily.ROTARY_SPEED
    assert entries["MW"].category is CurveCategory.MUD
    assert entries["MW"].family is CurveFamily.MUD_DENSITY
    assert entries["EMPTY"].range_text == "—"


def test_recommended_curves_skip_empty_channels() -> None:
    selected = recommended_curve_mnemonics(make_dataset())

    assert "C1" in selected
    assert "BIT_RPM" in selected
    assert "MW" in selected
    assert "EMPTY" not in selected


def test_recommended_curves_cover_multiple_available_categories() -> None:
    dataset = make_dataset()
    for mnemonic, unit in (("GR", "API"), ("DEXP", ""), ("ROP", "m/h")):
        curve_id = f"curve-{mnemonic}"
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(curve_id, mnemonic, mnemonic, unit, "", dataset.dataset_id),
            np.asarray([1.0, 2.0, 3.0]),
        )

    selected = recommended_curve_mnemonics(dataset, maximum=5)

    assert {"C1", "MW", "GR", "DEXP"} <= set(selected)
    assert {"BIT_RPM", "ROP"} & set(selected)


def test_curve_catalog_resolves_vendor_aliases_from_sensor_reference() -> None:
    dataset = Dataset(
        "aliases",
        "Aliases",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0, 2.0, 3.0]),
    )
    for mnemonic, unit in (("CH4", "%"), ("QOUT", "m3/h"), ("GAMMA_RAY", "API")):
        curve_id = f"curve-{mnemonic}"
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(curve_id, mnemonic, mnemonic, unit, "", dataset.dataset_id),
            np.array([1.0, 2.0, 3.0]),
        )

    entries = {
        item.mnemonic: item for item in analyze_dataset_curves(dataset, default_sensor_catalog())
    }

    assert entries["CH4"].canonical_mnemonic == "C1"
    assert entries["CH4"].category is CurveCategory.GAS
    assert entries["QOUT"].family is CurveFamily.FLOW
    assert entries["GAMMA_RAY"].family is CurveFamily.GAMMA_RAY
    assert entries["CH4"].reference_source.endswith("Sensors.DB")
