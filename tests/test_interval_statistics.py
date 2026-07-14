import numpy as np
import pytest

from geoworkbench.calculations.interval_statistics import calculate_interval_statistics
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain


def make_dataset() -> Dataset:
    dataset = Dataset(
        "dataset",
        "Well",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    dataset.upsert_curve("ROP", np.array([1.0, 2.0, np.nan, 8.0]), unit="m/h")
    dataset.upsert_curve("TG", np.array([10.0, 20.0, 30.0, 40.0]), unit="%")
    return dataset


def test_interval_statistics_uses_inclusive_depth_block_and_ignores_nan() -> None:
    result = calculate_interval_statistics(make_dataset(), 101.0, 102.0)

    assert [item.mnemonic for item in result] == ["ROP", "TG"]
    rop, total_gas = result
    assert rop.valid_count == 1
    assert rop.minimum == rop.maximum == rop.mean == 2.0
    assert total_gas.valid_count == 2
    assert total_gas.minimum == 20.0
    assert total_gas.maximum == 30.0
    assert total_gas.mean == 25.0


def test_interval_statistics_can_filter_mnemonics() -> None:
    result = calculate_interval_statistics(make_dataset(), 100.0, 103.0, ["tg"])
    assert [item.mnemonic for item in result] == ["TG"]


def test_interval_statistics_rejects_invalid_or_empty_depth_block() -> None:
    dataset = make_dataset()
    with pytest.raises(ValueError, match="меньше"):
        calculate_interval_statistics(dataset, 102.0, 101.0)
    with pytest.raises(ValueError, match="нет отсчётов"):
        calculate_interval_statistics(dataset, 200.0, 300.0)
