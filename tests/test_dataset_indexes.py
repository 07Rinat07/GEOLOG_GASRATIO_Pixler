import numpy as np
import pytest

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)


def make_dataset() -> Dataset:
    return Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )


def test_legacy_dataset_automatically_gets_primary_index() -> None:
    dataset = make_dataset()

    assert len(dataset.indexes) == 1
    assert dataset.active_index.index_type is IndexType.MD
    assert dataset.active_index.role is IndexRole.DEPTH
    np.testing.assert_array_equal(dataset.active_index.values, dataset.depth)
    dataset.depth[0] = 99.0
    assert dataset.active_index.values[0] == 99.0


def test_switching_depth_index_updates_compatibility_depth_view() -> None:
    dataset = make_dataset()
    tvd = DatasetIndex(
        "tvd",
        "TVD",
        IndexType.TVD,
        IndexRole.DEPTH,
        "m",
        np.array([90.0, 91.0]),
    )

    dataset.add_index(tvd, make_active=True)

    assert dataset.active_index_id == "tvd"
    assert dataset.depth_domain is DepthDomain.TVD
    np.testing.assert_array_equal(dataset.depth, [90.0, 91.0])


def test_switching_time_index_does_not_replace_depth_compatibility_view() -> None:
    dataset = make_dataset()
    original_depth = dataset.depth.copy()
    time = DatasetIndex(
        "time",
        "TIME",
        IndexType.RELATIVE_TIME,
        IndexRole.TIME,
        "s",
        np.array([0.0, 1.0]),
    )

    dataset.add_index(time, make_active=True)

    assert dataset.active_index is time
    np.testing.assert_array_equal(dataset.depth, original_depth)
    assert dataset.depth_domain is DepthDomain.MD


def test_dataset_rejects_index_with_different_length() -> None:
    dataset = make_dataset()
    invalid = DatasetIndex(
        "short",
        "TVD",
        IndexType.TVD,
        IndexRole.DEPTH,
        "m",
        np.array([90.0]),
    )

    with pytest.raises(ValueError, match="Размер нового индекса"):
        dataset.add_index(invalid)
