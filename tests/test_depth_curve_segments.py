from __future__ import annotations

import numpy as np

from geoworkbench.printing.depth_curve_segments import continuous_depth_segments


def test_continuous_depth_segments_breaks_real_missing_depth_run() -> None:
    depth = np.asarray([0.0, 1.0, 100.0, 101.0], dtype=np.float64)
    indices = np.asarray([0, 1, 2, 3], dtype=np.int64)

    segments = continuous_depth_segments(depth, indices, limit=100)

    assert [segment.tolist() for segment in segments] == [[0, 1], [2, 3]]


def test_continuous_depth_segments_downsamples_inside_runs_without_bridging() -> None:
    first = np.arange(0.0, 1000.0, 0.5, dtype=np.float64)
    second = np.arange(2000.0, 3000.0, 0.5, dtype=np.float64)
    depth = np.concatenate((first, second))
    indices = np.arange(depth.size, dtype=np.int64)

    segments = continuous_depth_segments(depth, indices, limit=500)

    assert len(segments) == 2
    assert depth[segments[0][-1]] < 1000.0
    assert depth[segments[1][0]] >= 2000.0
    assert sum(segment.size for segment in segments) <= 504
    assert segments[0][0] == 0
    assert segments[-1][-1] == depth.size - 1


def test_continuous_depth_segments_keeps_short_dense_series_exact() -> None:
    depth = np.asarray([10.0, 10.5, 11.0, 11.5], dtype=np.float64)
    indices = np.asarray([0, 1, 2, 3], dtype=np.int64)

    segments = continuous_depth_segments(depth, indices, limit=100)

    assert len(segments) == 1
    assert segments[0].tolist() == [0, 1, 2, 3]


def test_sustained_coarse_sampling_remains_drawable_after_fine_sampling() -> None:
    depth = np.asarray([0.0, 1.0, 2.0, 7.0, 12.0, 17.0, 18.0, 19.0])
    indices = np.arange(depth.size, dtype=np.int64)

    segments = continuous_depth_segments(depth, indices, limit=100)

    assert [segment.tolist() for segment in segments] == [indices.tolist()]


def test_sparse_runs_keep_their_gaps_and_obey_the_total_point_limit() -> None:
    depth = np.asarray(
        [step for index in range(400) for step in (index * 20.0, index * 20.0 + 1.0)],
        dtype=np.float64,
    )
    indices = np.arange(depth.size, dtype=np.int64)
    segments = continuous_depth_segments(depth, indices, limit=200)

    assert len(segments) == 100
    assert sum(len(segment) for segment in segments) == 200
    assert all(depth[segment[-1]] - depth[segment[0]] == 1.0 for segment in segments)
