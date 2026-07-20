from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.forms import (
    FormApplyEngine,
    factory_templates,
    materialize_form_for_dataset,
    materialized_factory_templates,
)
from geoworkbench.tablet.models import TrackKind


def _dataset(*, time: bool = False) -> Dataset:
    domain = DepthDomain.TIME if time else DepthDomain.MD
    dataset = Dataset(
        "data-time" if time else "data-depth",
        "LAS",
        DatasetKind.GTI,
        domain,
        np.array([1000.0, 1000.5, 1001.0]),
    )
    rows = (
        ("ROP_AVG", "ROP", "Скорость проходки", "m/h"),
        ("TGAS", "TOTAL_GAS", "Суммарный газ", "%"),
        ("C1", "C1", "Метан", "%"),
        ("GR", "GR", "Гамма-каротаж", "API"),
        ("CUSTOM_A", "CUSTOM_A", "Пользовательская кривая A", "u"),
        ("CUSTOM_B", "CUSTOM_B", "Пользовательская кривая B", "u"),
        ("CUSTOM_C", "CUSTOM_C", "Пользовательская кривая C", "u"),
    )
    for position, (mnemonic, canonical, description, unit) in enumerate(rows):
        metadata = CurveMetadata(
            curve_id=f"curve-{position}",
            original_mnemonic=mnemonic,
            canonical_mnemonic=canonical,
            unit=unit,
            description=description,
            source_dataset_id=dataset.dataset_id,
        )
        dataset.curves[metadata.curve_id] = CurveData(
            metadata,
            np.array([float(position), float(position + 1), float(position + 2)]),
        )
    return dataset


def test_basic_depth_template_is_materialized_with_all_las_curves() -> None:
    source = factory_templates("ru")["factory-depth-basic"]

    info = materialize_form_for_dataset(
        source,
        _dataset(),
        "ru",
        max_bindings_per_column=2,
    )

    assert info.compatible_axis is True
    assert info.generated_binding_count == 7
    assert source.columns[1].tracks[0].bindings == []
    assert info.form.read_only is True
    assert info.form.columns[0].tracks[0].kind is TrackKind.DEPTH
    curve_tracks = [
        track
        for column in info.form.columns
        for track in column.tracks
        if track.kind is TrackKind.CURVE
    ]
    assert curve_tracks
    assert all(1 <= len(track.bindings) <= 2 for track in curve_tracks)
    assert {binding.source_mnemonic for track in curve_tracks for binding in track.bindings} == {
        "ROP_AVG",
        "TGAS",
        "C1",
        "GR",
        "CUSTOM_A",
        "CUSTOM_B",
        "CUSTOM_C",
    }
    assert any(
        binding.display_name == "Пользовательская кривая A"
        for track in curve_tracks
        for binding in track.bindings
    )


def test_materialized_factory_templates_preserve_language_and_stable_id() -> None:
    templates = materialized_factory_templates(_dataset(), "en", max_bindings_per_column=3)
    form = templates["factory-depth-basic"]

    assert form.form_id == "factory-depth-basic"
    assert form.name == "LAS — working depth form"
    assert form.columns[0].title == "Depth"
    assert sum(len(track.bindings) for column in form.columns for track in column.tracks) == 7


def test_basic_form_applies_directly_without_manual_curve_setup() -> None:
    dataset = _dataset()

    result = FormApplyEngine().build_layout(
        factory_templates("ru")["factory-depth-basic"],
        dataset,
    )

    resolved = {mnemonic for track in result.layout.tracks for mnemonic in track.curve_mnemonics}
    assert resolved == {"ROP_AVG", "TGAS", "C1", "GR", "CUSTOM_A", "CUSTOM_B", "CUSTOM_C"}
    assert result.resolved_count == 7
    assert not result.missing


def test_time_form_requires_time_axis_and_materializes_when_available() -> None:
    depth_dataset = _dataset()
    time_dataset = _dataset(time=True)
    form = factory_templates("ru")["factory-time-basic"]

    with pytest.raises(ValueError, match="совместимой"):
        FormApplyEngine().build_layout(form, depth_dataset)

    result = FormApplyEngine().build_layout(form, time_dataset)
    assert result.resolved_count == 7
    assert result.layout.vertical_index_id == "data-time:primary-index"


def test_materialization_uses_autoscale_for_equal_legacy_sensor_range() -> None:
    dataset = Dataset(
        "legacy-range",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 100.5, 101.0]),
    )
    metadata = CurveMetadata(
        curve_id="curve-sensor-90",
        original_mnemonic="SENSOR_90",
        canonical_mnemonic="SENSOR_90",
        unit="",
        description="Кнопка",
        source_dataset_id=dataset.dataset_id,
    )
    dataset.curves[metadata.curve_id] = CurveData(
        metadata,
        np.array([0.0, 0.0, 1.0]),
    )

    info = materialize_form_for_dataset(
        factory_templates("ru")["factory-depth-basic"],
        dataset,
        "ru",
    )

    bindings = [
        binding
        for column in info.form.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    assert len(bindings) == 1
    assert bindings[0].x_min is None
    assert bindings[0].x_max is None
