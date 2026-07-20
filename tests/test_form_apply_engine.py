from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.forms import FormApplyEngine, factory_templates


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

    assert result.layout.tracks[0].kind.value == "depth"
    assert any("TGAS" in track.curve_mnemonics for track in result.layout.tracks)
    assert any("ROP_AVG" in track.curve_mnemonics for track in result.layout.tracks)
    total_gas_track = next(
        track for track in result.layout.tracks if "TGAS" in track.curve_mnemonics
    )
    assert total_gas_track.curve_display_settings("TGAS").display_name == "Суммарный газ"
    assert result.resolved_count == 3
    assert {item.canonical_parameter_id for item in result.missing} == {
        "NORMALIZED_TOTAL_GAS",
        "BALANCE",
        "CHARACTER",
    }


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
