from importlib.util import find_spec
import json

import numpy as np
import pytest

from geoworkbench.data.dataset_parquet_export import (
    DatasetParquetExportError,
    _unique_column_name,
    export_dataset_parquet,
)
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


def make_dataset() -> Dataset:
    dataset = Dataset("dataset", "Logging", DatasetKind.GTI, DepthDomain.MD, np.array([1.0, 2.0]))
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            None,
            np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[ns]"),
            timezone="UTC",
        )
    )
    dataset.curves["curve"] = CurveData(
        CurveMetadata("curve", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.array([10.0, np.nan]),
    )
    return dataset


def test_parquet_export_reports_missing_optional_dependency(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "geoworkbench.data.dataset_parquet_export.import_module",
        lambda name: (_ for _ in ()).throw(ImportError(name)),
    )

    with pytest.raises(DatasetParquetExportError, match="analysis"):
        export_dataset_parquet(make_dataset(), tmp_path / "dataset.parquet")

    assert not (tmp_path / "dataset.parquet").exists()


def test_parquet_column_names_remain_unique() -> None:
    names = ["DEPTH", "ROP"]

    assert _unique_column_name("TIME", "time", names) == "TIME"
    assert _unique_column_name("ROP", "curve-2", names) == "ROP__curve-2"


@pytest.mark.skipif(find_spec("pyarrow") is None, reason="pyarrow is optional")
def test_parquet_export_preserves_columns_and_schema_metadata(tmp_path) -> None:
    import pyarrow.parquet as parquet

    target = export_dataset_parquet(make_dataset(), tmp_path / "dataset.parquet")
    table = parquet.read_table(target)

    assert table.column_names == ["DEPT", "TIME", "ROP"]
    metadata = json.loads(table.schema.metadata[b"geoworkbench.dataset"])
    assert metadata["active_index_id"] == "dataset:primary-index"
    assert metadata["columns"]["TIME"]["timezone"] == "UTC"
    assert table.column("ROP").null_count == 1
