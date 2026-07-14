import numpy as np
import pytest

from geoworkbench.data.las_adapter import LasImportError, import_las


class FakeArray:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def to_numpy(self, *, dtype, copy: bool) -> np.ndarray:
        return np.array(self.values, dtype=dtype, copy=copy)


class FakeFrame:
    def __init__(self) -> None:
        self.index = FakeArray([100.0, 101.0])
        self.columns = ["C1", "ROP"]
        self._values = {
            "C1": FakeArray([1.0, 2.0]),
            "ROP": FakeArray([10.0, 12.0]),
        }

    def __getitem__(self, column: str) -> FakeArray:
        return self._values[column]


class FakeHeaderItem:
    def __init__(self, mnemonic: str, value: object = "", unit: str = "", descr: str = ""):
        self.mnemonic = mnemonic
        self.value = value
        self.unit = unit
        self.descr = descr


class FakeLas:
    curves = [
        FakeHeaderItem("C1", unit="%", descr="Methane"),
        FakeHeaderItem("ROP", unit="m/h", descr="Rate of penetration"),
    ]
    well = [FakeHeaderItem("WELL", "Test Well")]
    params = [FakeHeaderItem("RUN", "1")]

    def df(self) -> FakeFrame:
        return FakeFrame()


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
