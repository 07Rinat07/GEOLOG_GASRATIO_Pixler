from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.forms import FormApplyEngine, factory_templates
from geoworkbench.forms.a4_factory_templates import a4_factory_templates
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerTrackSettings,
)


def _dataset() -> Dataset:
    dataset = Dataset("data", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([1000.0, 1001.0]))
    for mnemonic, canonical in (("TGAS", "TOTAL_GAS"), ("ROP_AVG", "ROP"), ("WETNESS", "WETNESS")):
        metadata = CurveMetadata(
            curve_id=f"curve-{mnemonic}",
            original_mnemonic=mnemonic,
            canonical_mnemonic=canonical,
            unit="",
            description=canonical,
            source_dataset_id=dataset.dataset_id,
        )
        dataset.curves[metadata.curve_id] = CurveData(metadata, np.array([1.0, 2.0]))
    return dataset


def test_form_apply_builds_layout_and_reports_missing_bindings() -> None:
    result = FormApplyEngine().build_layout(factory_templates()["factory-gas-ratio"], _dataset())

    assert result.layout.localize_factory_labels is True
    assert result.layout.tracks[0].kind.value == "depth"
    assert any("TGAS" in track.curve_mnemonics for track in result.layout.tracks)
    assert any("ROP_AVG" in track.curve_mnemonics for track in result.layout.tracks)
    total_gas_track = next(
        track for track in result.layout.tracks if "TGAS" in track.curve_mnemonics
    )
    assert total_gas_track.curve_display_settings("TGAS").display_name == "Суммарный газ"
    assert result.resolved_count == 3
    assert {item.canonical_parameter_id for item in result.missing} == {
        "TG_CALC",
        "TG_NORM",
        "BALANCE",
        "CHARACTER",
    }


def test_form_apply_propagates_track_title_presentation() -> None:
    form = factory_templates()["factory-gas-ratio"].editable_copy()
    source_track = next(
        track for column in form.columns for track in column.tracks if track.bindings
    )
    source_track.title_orientation = "vertical_top_to_bottom"
    source_track.title_position = "top"
    source_track.vertical_ruler = VerticalRulerTrackSettings(
        mode=VerticalRulerMode.OFF,
        label_every_major=2,
        major_tick_every=3,
        minor_tick_every=4,
    )

    result = FormApplyEngine().build_layout(form, _dataset())
    applied = next(track for track in result.layout.tracks if track.title == source_track.title)

    assert result.layout.localize_factory_labels is False
    assert applied.title_orientation == "vertical_top_to_bottom"
    assert applied.title_position == "top"
    assert applied.vertical_ruler == source_track.vertical_ruler


def test_explicit_binding_has_priority() -> None:
    form = factory_templates()["factory-gas-ratio"].editable_copy()
    binding = form.columns[2].tracks[0].bindings[0]
    object.__setattr__(binding, "source_mnemonic", "TGAS")

    resolution = FormApplyEngine().resolve_binding(_dataset(), binding)

    assert resolution.mnemonic == "TGAS"
    assert resolution.matched_by == "explicit"


def test_specialized_depth_form_keeps_non_curve_tracks_and_resolves_available_data() -> None:
    result = FormApplyEngine().build_layout(
        factory_templates("en")["factory-gas-ratio-pixler-depth"],
        _dataset(),
    )

    kinds = [track.kind.value for track in result.layout.tracks]
    assert kinds[0] == "depth"
    assert "lithology" in kinds
    assert "interpretation" in kinds
    assert any("TGAS" in track.curve_mnemonics for track in result.layout.tracks)
    assert any("ROP_AVG" in track.curve_mnemonics for track in result.layout.tracks)
    assert result.layout.vertical_index_id == "data:primary-index"


def test_factory_form_draws_server_normalized_total_gas_alias() -> None:
    dataset = _dataset()
    metadata = CurveMetadata(
        curve_id="curve-server-normalized-gas",
        original_mnemonic="NORMALIZED_TOTAL_GAS",
        canonical_mnemonic="NORMALIZED_TOTAL_GAS",
        unit="normalized gas units",
        description="Operator normalized total gas",
        source_dataset_id=dataset.dataset_id,
        provenance="source:server",
    )
    dataset.curves[metadata.curve_id] = CurveData(metadata, np.array([12.0, 14.0]))

    result = FormApplyEngine().build_layout(
        factory_templates()["factory-normalized-gas-qc"],
        dataset,
    )

    assert any(
        "NORMALIZED_TOTAL_GAS" in track.curve_mnemonics
        for track in result.layout.tracks
    )


def test_form_prefers_contextual_geoscape_channel_over_empty_normal_source() -> None:
    dataset = _dataset()
    for mnemonic, canonical, values, provenance in (
        ("S1628", "NC4", [np.nan, np.nan], "source:paradox"),
        ("C4", "C4", [0.2, 0.3], "source:las"),
        ("IC4", "IC4", [0.1, 0.1], "source:las"),
        ("C5", "C5", [0.1, 0.2], "source:las"),
        ("IC5", "IC5", [0.05, 0.07], "source:las"),
    ):
        metadata = CurveMetadata(
            curve_id=f"curve-{mnemonic}",
            original_mnemonic=mnemonic,
            canonical_mnemonic=canonical,
            unit="%",
            description="nC4",
            source_dataset_id=dataset.dataset_id,
            provenance=provenance,
        )
        dataset.curves[metadata.curve_id] = CurveData(
            metadata,
            np.asarray(values, dtype=np.float64),
        )

    result = FormApplyEngine().build_layout(
        a4_factory_templates()["factory-complex-gas-a4-landscape"],
        dataset,
    )
    component_track = next(
        track for track in result.layout.tracks if track.title == "Компоненты C1–C5"
    )

    assert "C4" in component_track.curve_mnemonics
    assert "S1628" not in component_track.curve_mnemonics
    assert component_track.show_x_scale is False
    assert component_track.grid_x is False
    assert all(
        component_track.curve_display_settings(mnemonic).automatic_range
        for mnemonic in component_track.curve_mnemonics
    )
    assert all(
        component_track.curve_display_settings(mnemonic).x_scale.value == "linear"
        for mnemonic in component_track.curve_mnemonics
    )


def _geoscape_depth_dataset(
    *, include_companions: bool = True, rop_unit: str = "м/ч",
    gas_unit: str = "%",
) -> Dataset:
    """Synthetic S-series channel family from the Maksat M-1 LAS header."""
    dataset = Dataset(
        "geoscape", "GeoScape LAS", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000.0, 1000.2, 1000.4]),
    )
    codes = {
        "S106": (rop_unit, [8.0, 9.0, 10.0]),
        "S1600": (gas_unit, [0.5, 1.0, 1.5]),
        "CACO3": ("%", [80.0, 85.0, 90.0]),
        "CAMG_CO3_2": ("%", [10.0, 5.0, 10.0]),
    }
    if include_companions:
        codes.update({
            "S107": ("min/m", [1.0, 1.0, 1.0]),
            "S108": ("m", [1.0, 1.0, 1.0]),
            "S109": ("h", [1.0, 1.0, 1.0]),
            "S1601": ("%", [0.4, 0.8, 1.2]),
            "S1602": ("%", [0.1, 0.2, 0.3]),
            "S1603": ("%", [0.0, 0.0, 0.0]),
        })
    for code, (unit, values) in codes.items():
        metadata = CurveMetadata(
            f"curve-{code}", code, code, unit,
            "Legacy GeoScape sensor channel", dataset.dataset_id,
        )
        dataset.curves[metadata.curve_id] = CurveData(
            metadata, np.asarray(values, dtype=np.float64),
        )
    return dataset


def test_masterlog_geoscape_channels_bind_only_with_family_evidence() -> None:
    dataset = _geoscape_depth_dataset()
    engine = FormApplyEngine()
    for template_id in (
        "factory-masterlog-a4-portrait",
        "factory-masterlog-a4-landscape",
    ):
        result = engine.build_layout(a4_factory_templates()[template_id], dataset)
        by_canonical = {
            item.canonical_parameter_id: item
            for item in result.resolutions
        }
        assert by_canonical["ROP"].mnemonic == "S106"
        assert by_canonical["TOTAL_GAS"].mnemonic == "S1600"
        assert by_canonical["INSOLUBLE_RESIDUE"].mnemonic is None
        assert any("S106" in track.curve_mnemonics for track in result.layout.tracks)
        assert any("S1600" in track.curve_mnemonics for track in result.layout.tracks)


def test_geoscape_code_is_not_accepted_without_family_or_valid_unit() -> None:
    from geoworkbench.forms.models import ParameterBinding

    engine = FormApplyEngine()
    rop = ParameterBinding("rop-test", "ROP", "ROP")
    gas = ParameterBinding("gas-test", "TOTAL_GAS", "Total gas")
    for dataset in (
        _geoscape_depth_dataset(include_companions=False),
        _geoscape_depth_dataset(rop_unit="kg", gas_unit="m/h"),
    ):
        # The existing Sensors catalog already identifies S106 as ROP by
        # legacy GID identity, independently of the new family-only fallback.
        rop_resolution = engine.resolve_binding(dataset, rop)
        assert rop_resolution.matched_by != "geoscape_family"
        # The new fallback must never invent a total-gas match from a lone
        # vendor code or from a source with incorrect units.
        assert engine.resolve_binding(dataset, gas).mnemonic is None


def test_masterlog_never_derives_unmeasured_insoluble_residue() -> None:
    from geoworkbench.forms.models import ParameterBinding

    dataset = _geoscape_depth_dataset()
    missing = FormApplyEngine().resolve_binding(
        dataset, ParameterBinding("insoluble-test", "INSOLUBLE_RESIDUE", "IR"),
    )
    assert missing.mnemonic is None
