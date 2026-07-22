from __future__ import annotations

from dataclasses import replace

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.time_display import (
    format_datetime_at_row,
    format_datetime_value,
    format_elapsed_time,
    format_index_at_row,
    format_time_curve_at_row,
    format_unix_seconds,
    ole_automation_to_datetime,
)


def _dataset() -> Dataset:
    datetimes = np.array(
        [
            np.datetime64("2014-04-11T05:43:29.000", "ns"),
            np.datetime64("2014-04-11T07:50:57.200", "ns"),
        ]
    )
    depth = np.array([100.0, 100.2])
    dataset = Dataset(
        dataset_id="time-display",
        name="sample",
        kind=DatasetKind.USER,
        depth_domain=DepthDomain.MD,
        depth=depth,
        headers={"DATE": "2014-04-11", "TIME": "05:43:29"},
        indexes={
            "depth": DatasetIndex(
                "depth", "DEPT", IndexType.MD, IndexRole.DEPTH, "m", depth
            ),
            "datetime": DatasetIndex(
                "datetime",
                "DATETIME",
                IndexType.DATETIME,
                IndexRole.TIME,
                None,
                datetimes,
            ),
            "time": DatasetIndex(
                "time",
                "TIME",
                IndexType.RELATIVE_TIME,
                IndexRole.TIME,
                "s",
                np.array([0.0, 7648.2]),
            ),
        },
        active_index_id="depth",
    )
    curve_id = "time-curve"
    dataset.curves[curve_id] = CurveData(
        CurveMetadata(
            curve_id,
            "TIME",
            "TIME",
            "s",
            "ELAPSED TIME",
            dataset.dataset_id,
        ),
        np.array([0.0, 7648.2]),
    )
    return dataset


def test_datetime_format_is_platform_independent() -> None:
    value = np.datetime64("2014-04-11T05:43:29.125", "ns")
    assert format_datetime_value(value, include_milliseconds=True) == "11.04.2014 05:43:29.125"
    seconds = (value.astype(np.int64) / 1_000_000_000.0)
    assert format_unix_seconds(seconds, include_milliseconds=True) == "11.04.2014 05:43:29.125"


def test_elapsed_time_is_not_rendered_as_raw_seconds() -> None:
    assert format_elapsed_time(7648.2, "s") == "02:07:28.2"
    assert format_elapsed_time(90_000, "ms") == "00:01:30"


def test_companion_datetime_is_used_for_time_curve_and_index() -> None:
    dataset = _dataset()
    curve = dataset.curve_by_mnemonic("TIME")
    assert curve is not None
    assert format_datetime_at_row(dataset, 1) == "11.04.2014 07:50:57.2"
    assert format_time_curve_at_row(dataset, curve, 1) == "11.04.2014 07:50:57.2"
    assert format_index_at_row(dataset, dataset.indexes["time"], 1) == "11.04.2014 07:50:57.2"


def test_header_origin_is_used_when_datetime_index_is_absent() -> None:
    dataset = _dataset()
    dataset.indexes.pop("datetime")
    curve = dataset.curve_by_mnemonic("TIME")
    assert curve is not None
    assert format_time_curve_at_row(dataset, curve, 1) == "11.04.2014 07:50:57"


def test_invalid_values_are_safe() -> None:
    assert format_datetime_value(np.datetime64("NaT")) == "—"
    assert format_unix_seconds(float("nan")) == "—"
    assert format_elapsed_time(float("inf"), "s") == "—"


def test_time_formatter_source_does_not_use_platform_timestamp_conversion() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/services/time_display.py"
    ).read_text(encoding="utf-8")
    assert ".fromtimestamp(" not in source
    assert ".utcfromtimestamp(" not in source


def test_ole_delphi_calendar_curve_is_rendered_as_date_time_without_companion_index() -> None:
    dataset = _dataset()
    dataset.indexes.pop("datetime")
    dataset.headers.clear()
    curve = dataset.curve_by_mnemonic("TIME")
    assert curve is not None
    curve.values[:] = [41740.0, 41740.238539]
    curve.metadata = replace(
        curve.metadata,
        unit="d",
        provenance="paradox:S0:NUMBER:raw-time",
        description="Delphi/OLE source time",
    )

    assert ole_automation_to_datetime(41740.238539) is not None
    assert format_time_curve_at_row(dataset, curve, 1) == "11.04.2014 05:43:29"
