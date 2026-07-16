import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.dataset_selection import DatasetIntervalSelection


def make_dataset() -> Dataset:
    dataset = Dataset(
        "dataset", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 101.0, 102.0])
    )
    dataset.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", None, dataset.dataset_id),
        np.array([10.0, 20.0, 30.0]),
    )
    return dataset


def test_interval_selection_normalizes_to_available_samples_and_deduplicates(qapp) -> None:
    dataset = make_dataset()
    selection = DatasetIntervalSelection()
    changes: list[object] = []
    selection.changed.connect(changes.append)

    selection.select(dataset, 100.2, 101.8, ("gr", "gr"))
    selection.select(dataset, 101.0, 101.0, ("gr",))

    assert selection.dataset_id == "dataset"
    assert selection.interval == (101.0, 101.0)
    assert selection.curve_ids == ("gr",)
    assert len(changes) == 1


def test_interval_selection_rejects_unknown_curve(qapp) -> None:
    with pytest.raises(KeyError, match="missing"):
        DatasetIntervalSelection().select(make_dataset(), 100.0, 101.0, ("missing",))
