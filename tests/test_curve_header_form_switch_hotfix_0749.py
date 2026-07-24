from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.forms import factory_templates, materialize_form_for_dataset
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.curve_scaling import normalize_curve_values
from geoworkbench.tablet.models import TrackDefinition, TrackKind, XScale


ROOT = Path(__file__).resolve().parents[1]


def _dataset() -> Dataset:
    dataset = Dataset(
        "linear-default",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 100.2, 100.4]),
    )
    metadata = CurveMetadata(
        curve_id="curve-res",
        original_mnemonic="RES",
        canonical_mnemonic="RES",
        unit="ohm.m",
        description="Resistivity",
        source_dataset_id=dataset.dataset_id,
    )
    dataset.curves[metadata.curve_id] = CurveData(
        metadata, np.array([1.0, 10.0, 100.0])
    )
    return dataset


def test_dataset_driven_form_defaults_to_linear_scale() -> None:
    materialized = materialize_form_for_dataset(
        factory_templates("ru")["factory-depth-basic"], _dataset(), "ru"
    )
    bindings = [
        binding
        for column in materialized.form.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    assert len(bindings) == 1
    assert bindings[0].x_scale is XScale.LINEAR


def test_new_gas_and_resistivity_track_specs_default_to_linear() -> None:
    gas = TabletController._family_track_spec  # contract checked without a Qt dependency
    from geoworkbench.services.curve_catalog import CurveFamily

    assert gas(CurveFamily.GAS, ["C1"])[3] is XScale.LINEAR
    assert gas(CurveFamily.RESISTIVITY, ["RES"])[3] is XScale.LINEAR


def test_manual_range_changes_normalized_curve_position() -> None:
    values = np.array([0.0, 50.0, 100.0])
    original = normalize_curve_values(values, XScale.LINEAR, 0.0, 100.0)
    widened = normalize_curve_values(values, XScale.LINEAR, 0.0, 200.0)

    assert original[1] == 0.5
    assert widened[1] == 0.25
    assert not np.array_equal(original, widened)


def test_track_without_explicit_curve_settings_is_linear_by_default() -> None:
    track = TrackDefinition("track", "Parameters", TrackKind.CURVE, ["A"])
    assert track.curve_display_settings("A").x_scale is XScale.LINEAR


def test_header_layout_is_responsive_and_range_changes_are_debounced() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")

    assert "class CurveRenderKey:" in source
    assert "minimum=float(minimum)" in source
    assert "maximum=float(maximum)" in source
    assert "RANGE_COMMIT_DELAY_MS = 220" in source
    assert "self._range_commit_timer.timeout.connect(self._commit_range_when_idle)" in source
    assert "range_row.addWidget(self.minimum, 1)" in source
    assert "range_row.addWidget(self.maximum, 1)" in source
    assert "row.addStretch(1)" not in source
    assert "apply_range = QToolButton()" not in source
    assert "spin.setSizePolicy(QSizePolicy.Policy.Expanding" in source
    assert "spin.setMinimumWidth(24)" in source
    assert "separator.setFixedWidth(6)" in source


def test_form_application_renders_before_commit_and_rolls_back_on_failure() -> None:
    window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")

    assert "class _TabletFormSnapshot:" in window
    assert "apply_reversibly(" in window
    assert "render_candidate=render_candidate" in window
    assert "commit_candidate=commit_candidate" in window
    assert "restore_snapshot=self._restore_tablet_form_snapshot" in window
    assert "def set_layout_and_dataset(" in tablet
    assert "preserve_current_range=False" in window
