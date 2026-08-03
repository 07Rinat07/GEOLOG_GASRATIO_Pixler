from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.report_passport import _interval_snapshot


def test_report_passport_accepts_unix_second_datetime_bounds() -> None:
    values = np.array(
        [
            "2026-07-21T00:00:00.000",
            "2026-07-21T00:00:00.240",
            "2026-07-21T00:00:01.000",
        ],
        dtype="datetime64[ms]",
    )
    index = DatasetIndex(
        "datetime",
        "DATETIME",
        IndexType.DATETIME,
        IndexRole.TIME,
        None,
        values,
    )
    dataset = Dataset(
        "time-dataset",
        "Time",
        DatasetKind.USER,
        DepthDomain.TIME,
        np.array([0.0, 1.0, 2.0]),
        indexes={index.index_id: index},
        active_index_id=index.index_id,
    )
    start = float(values[0].astype("datetime64[ns]").astype(np.int64)) / 1e9
    end = float(values[-1].astype("datetime64[ns]").astype(np.int64)) / 1e9

    snapshot = _interval_snapshot(dataset, (start, end))

    assert snapshot.start == "2026-07-21T00:00:00.000000000"
    assert snapshot.end == "2026-07-21T00:00:01.000000000"
    assert snapshot.sample_count == 3
