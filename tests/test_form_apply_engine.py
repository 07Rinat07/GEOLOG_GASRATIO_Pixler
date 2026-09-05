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
