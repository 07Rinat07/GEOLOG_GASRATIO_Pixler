from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRange,
    ReportDepthRangeError,
    resolve_report_depth_range,
)


def _dataset(*depths: float) -> Dataset:
    return Dataset(
        dataset_id="dataset-report-range",
        name="Report range",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray(depths, dtype=np.float64),
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("1980–2016.20 m", ReportDepthRange(1980.0, 2016.2)),
        ("1980,0-2016,2 м", ReportDepthRange(1980.0, 2016.2)),
        ("1980 to 2016.2", ReportDepthRange(1980.0, 2016.2)),
        ("1980 до 2016,2", ReportDepthRange(1980.0, 2016.2)),
    ),
)
def test_resolve_report_depth_range_accepts_supported_user_formats(
    text: str,
    expected: ReportDepthRange,
) -> None:
    dataset = _dataset(47.0, 1980.0, 2016.2, 2200.0)

    assert resolve_report_depth_range(text, dataset) == expected


def test_blank_report_interval_uses_complete_dataset_depth() -> None:
    dataset = _dataset(47.0, np.nan, 1980.0, 2200.0)

    assert resolve_report_depth_range("", dataset) == ReportDepthRange(47.0, 2200.0)


@pytest.mark.parametrize(
    "text",
    (
        "2016.2–1980 m",
        "1980 m",
        "46–2016.2 m",
        "1980–2201 m",
    ),
)
def test_report_interval_fails_closed_when_it_cannot_be_applied(
    text: str,
) -> None:
    dataset = _dataset(47.0, 1980.0, 2016.2, 2200.0)

    with pytest.raises(ReportDepthRangeError):
        resolve_report_depth_range(text, dataset)


def test_report_depth_range_formats_canonical_interval() -> None:
    assert ReportDepthRange(1980.0, 2016.2).formatted("m") == "1980.00–2016.20 m"
