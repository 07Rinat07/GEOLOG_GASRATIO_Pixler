from __future__ import annotations

from dataclasses import replace

import numpy as np

from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.semantic_channels import default_semantic_channel_dictionary
from geoworkbench.services.wits0_live_derived import (
    Wits0DerivedChannelStatus,
    Wits0DerivedUnavailableReason,
    Wits0LiveDerivedChannelService,
)


def _dataset(*, unit: str = "% abs", omit: set[str] | None = None) -> Dataset:
    dataset = Dataset(
        dataset_id="wits-derived",
        name="WITS derived",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([1000.0, 1000.5], dtype=np.float64),
    )
    omitted = omit or set()
    for mnemonic, value in {
        "C1": 80.0,
        "C2": 10.0,
        "C3": 5.0,
        "IC4": 1.0,
        "NC4": 2.0,
        "IC5": 1.0,
        "NC5": 1.0,
    }.items():
        if mnemonic in omitted:
            continue
        dataset.upsert_curve(
            mnemonic,
            np.full(dataset.depth.shape, value, dtype=np.float64),
            unit=unit,
            description=f"Source {mnemonic}",
            provenance="wits:test",
        )
    return dataset


def test_live_derived_service_projects_sourced_haworth_and_pixler_without_mutation() -> None:
    dataset = _dataset()
    curve_ids_before = tuple(dataset.curves)
    values_before = {
        curve_id: curve.values.copy()
        for curve_id, curve in dataset.curves.items()
    }

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    available = {
        item.mnemonic: item
        for item in snapshots
        if item.status is Wits0DerivedChannelStatus.AVAILABLE
    }
    assert set(available) == {"WH", "BH", "CH", "C1_C2", "C1_C3", "C1_C4", "C1_C5"}
    assert available["WH"].values == (20.0, 20.0)
    assert available["BH"].values == (9.0, 9.0)
    assert available["CH"].values == (1.0, 1.0)
    assert available["C1_C2"].values == (8.0, 8.0)
    assert available["C1_C3"].values == (16.0, 16.0)
    assert np.allclose(available["C1_C4"].values, (80.0 / 3.0, 80.0 / 3.0))
    assert available["C1_C5"].values == (40.0, 40.0)
    assert available["WH"].profile_id == "haworth.wetness"
    assert available["WH"].profile_version == "1.0.0"
    assert available["WH"].provenance == "formula:haworth.wetness:1.0.0"

    assert tuple(dataset.curves) == curve_ids_before
    for curve_id, expected in values_before.items():
        np.testing.assert_array_equal(dataset.curves[curve_id].values, expected)


def test_live_derived_service_reports_missing_inputs_instead_of_nan_only_channel() -> None:
    dataset = _dataset(omit={"NC5"})

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    by_mnemonic = {item.mnemonic: item for item in snapshots}
    assert by_mnemonic["WH"].status is Wits0DerivedChannelStatus.UNAVAILABLE
    assert by_mnemonic["WH"].unavailable_reason is Wits0DerivedUnavailableReason.MISSING_INPUT
    assert by_mnemonic["WH"].unavailable_inputs == ("NC5",)
    assert by_mnemonic["WH"].values == ()
    assert by_mnemonic["C1_C2"].status is Wits0DerivedChannelStatus.AVAILABLE


def test_live_derived_service_rejects_unverified_concentration_units_explicitly() -> None:
    dataset = _dataset(unit="vendor-counts")

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    by_mnemonic = {item.mnemonic: item for item in snapshots}
    c1_c2 = by_mnemonic["C1_C2"]
    assert c1_c2.status is Wits0DerivedChannelStatus.UNAVAILABLE
    assert c1_c2.unavailable_reason is Wits0DerivedUnavailableReason.UNSUPPORTED_UNIT
    assert c1_c2.unavailable_inputs == ("C1", "C2")
    assert c1_c2.values == ()


def _add_drilling_inputs(
    dataset: Dataset,
    *,
    rop: tuple[float, str] = (18.288, "m/h"),
    rpm: tuple[float, str] = (100.0, "rpm"),
    wob: tuple[float, str] = (222.411080763025, "kN"),
    bit: tuple[float, str] = (254.0, "mm"),
) -> None:
    for mnemonic, (value, unit) in {
        "ROP": rop,
        "RPM": rpm,
        "WOB": wob,
        "BIT": bit,
    }.items():
        dataset.upsert_curve(
            mnemonic,
            np.full(dataset.depth.shape, value, dtype=np.float64),
            unit=unit,
            description=f"Source {mnemonic}",
            provenance="wits:test",
        )


def test_live_derived_service_calculates_dexp_through_verified_uom_conversions() -> None:
    dataset = _dataset()
    _add_drilling_inputs(dataset)
    curve_ids_before = tuple(dataset.curves)

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    by_mnemonic = {item.mnemonic: item for item in snapshots}
    dexp = by_mnemonic["DEXP"]
    assert dexp.status is Wits0DerivedChannelStatus.AVAILABLE
    assert dexp.profile_id == "dexp.jorden_shirley"
    assert dexp.profile_version == "1.0.0"
    assert dexp.provenance == "formula:dexp.jorden_shirley:1.0.0"
    assert np.allclose(dexp.values, (1.6368638103758524, 1.6368638103758524))
    assert dexp.input_conversions == (
        "ROP_FPH:m/h->ft/h",
        "RPM:1/min->1/min",
        "WOB_LBF:kN->lbf",
        "BIT_IN:mm->in",
        "RPM_MODE:surface+no-bit-rpm",
    )
    assert tuple(dataset.curves) == curve_ids_before
    assert dataset.curve_by_mnemonic("DEXP") is None


def test_live_derived_service_reports_missing_dexp_input_explicitly() -> None:
    dataset = _dataset()
    _add_drilling_inputs(dataset)
    wob_curve = dataset.curve_by_mnemonic("WOB")
    assert wob_curve is not None
    del dataset.curves[wob_curve.metadata.curve_id]

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    dexp = {item.mnemonic: item for item in snapshots}["DEXP"]
    assert dexp.status is Wits0DerivedChannelStatus.UNAVAILABLE
    assert dexp.unavailable_reason is Wits0DerivedUnavailableReason.MISSING_INPUT
    assert dexp.unavailable_inputs == ("WOB_LBF",)
    assert dexp.values == ()


def test_live_derived_service_reports_unsupported_dexp_uom_explicitly() -> None:
    dataset = _dataset()
    _add_drilling_inputs(dataset, wob=(50_000.0, "vendor-force"))

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    dexp = {item.mnemonic: item for item in snapshots}["DEXP"]
    assert dexp.status is Wits0DerivedChannelStatus.UNAVAILABLE
    assert dexp.unavailable_reason is Wits0DerivedUnavailableReason.UNSUPPORTED_UNIT
    assert dexp.unavailable_inputs == ("WOB_LBF",)
    assert dexp.values == ()


def test_live_derived_service_reports_no_valid_dexp_samples_explicitly() -> None:
    dataset = _dataset()
    _add_drilling_inputs(dataset, rop=(0.0, "ft/h"))

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    dexp = {item.mnemonic: item for item in snapshots}["DEXP"]
    assert dexp.status is Wits0DerivedChannelStatus.UNAVAILABLE
    assert dexp.unavailable_reason is Wits0DerivedUnavailableReason.NO_VALID_SAMPLES
    assert dexp.unavailable_inputs == ()
    assert dexp.values == ()


def test_live_derived_service_uses_original_wits_kdn_for_wob_conversion() -> None:
    dataset = _dataset()
    _add_drilling_inputs(dataset, wob=(50.0, "t"))
    wob_curve = dataset.curve_by_mnemonic("WOB")
    assert wob_curve is not None
    semantic = default_semantic_channel_dictionary().resolve(
        "WOB",
        unit="KDN",
        source_mnemonic="WOBA",
        canonical_mnemonic="WOB",
    )
    wob_curve.metadata = replace(
        wob_curve.metadata,
        unit="t",
        provenance="wits0:0116",
        semantic=semantic,
    )

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    dexp = {item.mnemonic: item for item in snapshots}["DEXP"]
    assert dexp.status is Wits0DerivedChannelStatus.AVAILABLE
    assert "WOB_LBF:kdaN->lbf" in dexp.input_conversions
    wob_lbf = 50.0 * 10_000.0 / 4.4482216152605
    expected = build_all_sourced_formula_registry().calculate(
        "dexp.jorden_shirley",
        {
            "ROP_FPH": np.full(2, 60.0),
            "RPM": np.full(2, 100.0),
            "WOB_LBF": np.full(2, wob_lbf),
            "BIT_IN": np.full(2, 10.0),
        },
    )
    np.testing.assert_allclose(dexp.values, expected)


def test_live_derived_service_uses_downhole_rpm_for_sliding_dexp() -> None:
    dataset = _dataset()
    _add_drilling_inputs(dataset, rpm=(0.0, "rev/min"))
    dataset.upsert_curve(
        "FLOW_IN",
        np.full(dataset.depth.shape, 500.0, dtype=np.float64),
        unit="L/M",
        description="Mud flow in",
        provenance="wits:test",
    )
    dataset.upsert_curve(
        "MOTOR_RPM",
        np.full(dataset.depth.shape, 150.0, dtype=np.float64),
        unit="rev/min",
        description="Downhole motor RPM",
        provenance="wits:test",
    )

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    dexp = {item.mnemonic: item for item in snapshots}["DEXP"]
    assert dexp.status is Wits0DerivedChannelStatus.AVAILABLE
    assert "RPM_MODE:surface+MOTOR_RPM" in dexp.input_conversions
    assert "MODE_FLOW:L/min->gpm" in dexp.input_conversions
    expected = build_all_sourced_formula_registry().calculate(
        "dexp.jorden_shirley",
        {
            "ROP_FPH": np.full(2, 60.0),
            "RPM": np.full(2, 150.0),
            "WOB_LBF": np.full(2, 50_000.0),
            "BIT_IN": np.full(2, 10.0),
        },
    )
    np.testing.assert_allclose(dexp.values, expected)


def test_live_derived_service_does_not_guess_bit_rpm_during_slide() -> None:
    dataset = _dataset()
    _add_drilling_inputs(dataset, rpm=(0.0, "rev/min"))
    dataset.upsert_curve(
        "FLOW_IN",
        np.full(dataset.depth.shape, 500.0, dtype=np.float64),
        unit="L/M",
        description="Mud flow in",
        provenance="wits:test",
    )

    snapshots = Wits0LiveDerivedChannelService().snapshot(dataset)

    dexp = {item.mnemonic: item for item in snapshots}["DEXP"]
    assert dexp.status is Wits0DerivedChannelStatus.UNAVAILABLE
    assert dexp.unavailable_reason is Wits0DerivedUnavailableReason.NO_VALID_SAMPLES
    assert "RPM_MODE:surface+no-bit-rpm" in dexp.input_conversions
