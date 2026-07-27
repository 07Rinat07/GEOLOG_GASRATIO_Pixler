from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.tablet.axis_selection import (
    dataset_has_absolute_calendar_time,
    resolve_vertical_axis,
)


ROOT = Path(__file__).resolve().parents[1]


def _index(
    index_id: str,
    *,
    mnemonic: str,
    index_type: IndexType,
    role: IndexRole,
    values: np.ndarray,
    confidence: float = 1.0,
) -> DatasetIndex:
    return DatasetIndex(
        index_id=index_id,
        mnemonic=mnemonic,
        index_type=index_type,
        role=role,
        unit="s" if role is IndexRole.TIME else "m",
        values=values,
        confidence=confidence,
    )


def _geoscape_dataset(*, active_index_id: str = "calendar") -> Dataset:
    relative = _index(
        "relative",
        mnemonic="TIME",
        index_type=IndexType.RELATIVE_TIME,
        role=IndexRole.TIME,
        values=np.array([0.0, 1.0, 2.0]),
        confidence=0.8,
    )
    calendar = _index(
        "calendar",
        mnemonic="DATETIME",
        index_type=IndexType.DATETIME,
        role=IndexRole.TIME,
        values=np.array(
            [
                "2026-07-27T01:00:00",
                "2026-07-27T01:00:01",
                "2026-07-27T01:00:02",
            ],
            dtype="datetime64[s]",
        ),
        confidence=0.99,
    )
    depth = _index(
        "depth",
        mnemonic="DEPT",
        index_type=IndexType.MD,
        role=IndexRole.DEPTH,
        values=np.array([1000.0, 1000.1, 1000.2]),
        confidence=0.95,
    )
    return Dataset(
        dataset_id="gs2-dataset",
        name="GeoScape2",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.TIME,
        depth=np.array([0.0, 1.0, 2.0]),
        indexes={
            relative.index_id: relative,
            calendar.index_id: calendar,
            depth.index_id: depth,
        },
        active_index_id=active_index_id,
        parameters={
            "SOURCE_FORMAT": "GeoScape2 GS2",
            "PARADOX_TIME_REPRESENTATION": "unix-seconds",
        },
    )


def test_stale_form_axis_falls_back_without_none_dereference() -> None:
    dataset = _geoscape_dataset(active_index_id="calendar")

    resolution = resolve_vertical_axis(
        dataset,
        "axis-from-previous-dataset",
        prefer_calendar_time=dataset_has_absolute_calendar_time(dataset),
    )

    assert resolution.index is dataset.indexes["calendar"]
    assert resolution.replace_layout_index is True
    assert resolution.calendar_time_preferred is False


def test_stale_form_axis_with_relative_active_prefers_calendar_time() -> None:
    dataset = _geoscape_dataset(active_index_id="relative")

    resolution = resolve_vertical_axis(
        dataset,
        "axis-from-previous-dataset",
        prefer_calendar_time=True,
    )

    assert resolution.index is dataset.indexes["calendar"]
    assert resolution.replace_layout_index is True
    assert resolution.calendar_time_preferred is True


def test_legacy_relative_time_form_is_migrated_to_datetime() -> None:
    dataset = _geoscape_dataset(active_index_id="relative")

    resolution = resolve_vertical_axis(
        dataset,
        "relative",
        prefer_calendar_time=True,
    )

    assert resolution.index is dataset.indexes["calendar"]
    assert resolution.replace_layout_index is True
    assert resolution.calendar_time_preferred is True


def test_explicit_depth_axis_is_preserved_for_geoscape_dataset() -> None:
    dataset = _geoscape_dataset(active_index_id="calendar")

    resolution = resolve_vertical_axis(
        dataset,
        "depth",
        prefer_calendar_time=True,
    )

    assert resolution.index is dataset.indexes["depth"]
    assert resolution.replace_layout_index is False
    assert resolution.calendar_time_preferred is False


def test_non_absolute_source_keeps_relative_time_axis() -> None:
    dataset = _geoscape_dataset(active_index_id="relative")
    dataset.parameters.clear()

    assert dataset_has_absolute_calendar_time(dataset) is False
    resolution = resolve_vertical_axis(
        dataset,
        "relative",
        prefer_calendar_time=False,
    )

    assert resolution.index is dataset.indexes["relative"]
    assert resolution.replace_layout_index is False


def test_form_candidate_is_bound_before_geoscape_axis_reconciliation() -> None:
    source = (
        ROOT / "src/geoworkbench/tablet/tablet_view.py"
    ).read_text(encoding="utf-8")
    method = source.split("    def set_layout_and_dataset(\n", 1)[1].split(
        "    @property\n    def cursor_depth", 1
    )[0]

    assert method.index("self._bind_layout_model(") < method.index(
        "self._prefer_calendar_time_axis_for_geoscape(dataset)"
    )


def test_dataset_replacement_does_not_reconcile_against_old_layout_early() -> None:
    source = (
        ROOT / "src/geoworkbench/tablet/tablet_view.py"
    ).read_text(encoding="utf-8")
    method = source.split("    def _replace_dataset_reference(", 1)[1].split(
        "    def _prefer_calendar_time_axis_for_geoscape", 1
    )[0]

    assert "_prefer_calendar_time_axis_for_geoscape" not in method
