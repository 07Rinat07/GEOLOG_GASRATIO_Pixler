import json

import numpy as np
import pytest

from geoworkbench.data.dataset_json_export import (
    DatasetJsonExportError,
    export_dataset_json,
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


def make_multi_index_dataset() -> Dataset:
    depth = np.array([100.0, 101.0, 102.0])
    dataset = Dataset("dataset", "Logging", DatasetKind.GTI, DepthDomain.MD, depth)
    dataset.add_index(
        DatasetIndex(
            "time",
            "DATE_TIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            None,
            np.array(
                ["2026-01-01T00:00:00", "NaT", "2026-01-01T00:00:02"],
                dtype="datetime64[ns]",
            ),
            timezone="UTC",
        )
    )
    dataset.curves["rop"] = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", "Rate", dataset.dataset_id),
        np.array([10.0, np.nan, 30.0]),
    )
    return dataset


def test_json_export_preserves_all_indexes_metadata_and_nulls(tmp_path) -> None:
    target = export_dataset_json(make_multi_index_dataset(), tmp_path / "dataset.json")

    payload = json.loads(target.read_text(encoding="utf-8"))
    data = payload["dataset"]
    assert payload["format_version"] == 1
    assert data["active_index_id"] == "dataset:primary-index"
    assert set(data["indexes"]) == {"dataset:primary-index", "time"}
    assert data["indexes"]["time"]["values"] == [
        "2026-01-01T00:00:00.000000000",
        None,
        "2026-01-01T00:00:02.000000000",
    ]
    assert data["curves"]["rop"]["values"] == [10.0, None, 30.0]
    assert "NaN" not in target.read_text(encoding="utf-8")


def test_json_export_rejects_wrong_extension_and_overwrite(tmp_path) -> None:
    dataset = make_multi_index_dataset()
    target = tmp_path / "dataset.json"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(DatasetJsonExportError, match="расширение"):
        export_dataset_json(dataset, tmp_path / "dataset.txt")
    with pytest.raises(FileExistsError):
        export_dataset_json(dataset, target)

    assert target.read_text(encoding="utf-8") == "original"


def test_json_export_includes_semantic_channel_snapshot(tmp_path) -> None:
    from geoworkbench.services.semantic_channels import SemanticChannelDictionary

    dataset = make_multi_index_dataset()
    curve = dataset.curves["rop"]
    semantic = SemanticChannelDictionary().resolve("ROP", unit="m/h")
    curve.metadata = CurveMetadata(
        curve.metadata.curve_id,
        curve.metadata.original_mnemonic,
        semantic.canonical_mnemonic,
        curve.metadata.unit,
        curve.metadata.description,
        curve.metadata.source_dataset_id,
        curve.metadata.provenance,
        semantic,
    )

    target = export_dataset_json(dataset, tmp_path / "semantic.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    stored = payload["dataset"]["curves"]["rop"]["metadata"]["semantic"]

    assert stored["canonical_kind"] == "drilling.rop"
    assert stored["quantity_class"] == "linear_velocity"
    assert stored["sensor_id"] == "editor_gid_106"
