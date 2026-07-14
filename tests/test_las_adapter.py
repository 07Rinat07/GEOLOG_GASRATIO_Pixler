import numpy as np
import pytest

from geoworkbench.data.las_adapter import LasExportError, LasImportError, export_las, import_las
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)


class FakeHeaderItem:
    def __init__(self, mnemonic: str, value: object = "", unit: str = "", descr: str = ""):
        self.mnemonic = mnemonic
        self.value = value
        self.unit = unit
        self.descr = descr


class FakeLas:
    curves = [
        FakeHeaderItem("DEPT", unit="m", descr="Depth"),
        FakeHeaderItem("C1", unit="%", descr="Methane"),
        FakeHeaderItem("ROP", unit="m/h", descr="Rate of penetration"),
    ]
    well = [FakeHeaderItem("WELL", "Test Well")]
    params = [FakeHeaderItem("RUN", "1")]
    index = np.array([100.0, 101.0])
    _values = {
        "C1": np.array([1.0, 2.0]),
        "ROP": np.array([10.0, 12.0]),
    }

    def __getitem__(self, mnemonic: str) -> np.ndarray:
        return self._values[mnemonic]


def test_import_las_builds_dataset_with_metadata(tmp_path, monkeypatch) -> None:
    source = tmp_path / "sample.LAS"
    source.write_text("fake", encoding="utf-8")
    monkeypatch.setattr("geoworkbench.data.las_adapter.lasio.read", lambda *args, **kwargs: FakeLas())

    dataset = import_las(source)

    assert dataset.name == "sample"
    assert dataset.source_path == source
    np.testing.assert_allclose(dataset.depth, [100.0, 101.0])
    c1 = dataset.curve_by_mnemonic("c1")
    assert c1 is not None
    assert c1.metadata.unit == "%"
    assert c1.metadata.description == "Methane"
    np.testing.assert_allclose(c1.values, [1.0, 2.0])
    assert dataset.headers["WELL"] == "Test Well"
    assert dataset.parameters["RUN"] == "1"


def test_import_las_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        import_las(tmp_path / "missing.las")


def test_import_las_rejects_wrong_extension(tmp_path) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("not las", encoding="utf-8")

    with pytest.raises(LasImportError, match="Ожидался LAS-файл"):
        import_las(source)


def test_import_las_wraps_parser_errors(tmp_path, monkeypatch) -> None:
    source = tmp_path / "broken.las"
    source.write_text("broken", encoding="utf-8")

    def fail(*args, **kwargs):
        raise ValueError("parser internals")

    monkeypatch.setattr("geoworkbench.data.las_adapter.lasio.read", fail)

    with pytest.raises(LasImportError, match="Не удалось прочитать LAS-файл") as error:
        import_las(source)

    assert isinstance(error.value.__cause__, ValueError)
    assert str(source) in str(error.value)


def make_export_dataset(source_path=None) -> Dataset:
    dataset = Dataset(
        "dataset-1",
        "Edited",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
        source_path=source_path,
        headers={"WELL": "Test Well"},
    )
    curve = CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", "Rate", dataset.dataset_id),
        np.array([10.0, 20.0, 30.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    return dataset


def test_export_las_round_trip_preserves_depth_curve_and_metadata(tmp_path) -> None:
    target = tmp_path / "edited.las"

    export_las(make_export_dataset(), target)
    restored = import_las(target)

    np.testing.assert_allclose(restored.depth, [100.0, 101.0, 102.0])
    rop = restored.curve_by_mnemonic("ROP")
    assert rop is not None
    np.testing.assert_allclose(rop.values, [10.0, 20.0, 30.0])
    assert rop.metadata.unit == "m/h"
    assert restored.headers["WELL"] == "Test Well"


def test_export_las_never_overwrites_source_file(tmp_path) -> None:
    source = tmp_path / "source.las"
    source.write_text("original", encoding="utf-8")

    with pytest.raises(LasExportError, match="Исходный LAS"):
        export_las(make_export_dataset(source), source, overwrite=True)

    assert source.read_text(encoding="utf-8") == "original"


def test_export_las_requires_explicit_overwrite(tmp_path) -> None:
    target = tmp_path / "existing.las"
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        export_las(make_export_dataset(), target)

    assert target.read_text(encoding="utf-8") == "existing"


def test_export_las_removes_temporary_file_after_write_failure(tmp_path, monkeypatch) -> None:
    target = tmp_path / "failed.las"

    def fail_write(*args, **kwargs) -> None:
        raise OSError("write failed")

    monkeypatch.setattr("geoworkbench.data.las_adapter.lasio.LASFile.write", fail_write)

    with pytest.raises(LasExportError, match="Не удалось экспортировать"):
        export_las(make_export_dataset(), target)

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
