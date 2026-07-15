from hashlib import sha256

import numpy as np
import pytest

from geoworkbench.data.las_adapter import (
    LasExportError,
    LasImportError,
    export_las,
    import_las,
    import_las_with_report,
)
from geoworkbench.data.las_export_plan import LasExportPlan, LasExportVersion
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.depth_axis import DepthDirection


class FakeHeaderItem:
    def __init__(self, mnemonic: str, value: object = "", unit: str = "", descr: str = ""):
        self.mnemonic = mnemonic
        self.value = value
        self.unit = unit
        self.descr = descr


class FakeLas:
    version = [FakeHeaderItem("VERS", "2.0"), FakeHeaderItem("WRAP", "NO")]
    curves = [
        FakeHeaderItem("DEPT", unit="m", descr="Depth"),
        FakeHeaderItem("C1", unit="%", descr="Methane"),
        FakeHeaderItem("ROP", unit="m/h", descr="Rate of penetration"),
    ]
    well = [
        FakeHeaderItem("WELL", "Test Well"),
        FakeHeaderItem("STRT", "100"),
        FakeHeaderItem("STOP", "101"),
        FakeHeaderItem("STEP", "1"),
        FakeHeaderItem("NULL", "-999.25"),
    ]
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


def test_import_las_with_report_captures_source_and_depth_diagnostics(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "descending.las"
    raw = b"exact LAS source\n"
    source.write_bytes(raw)

    class DescendingLas(FakeLas):
        index = np.array([101.0, 100.0])
        well = [
            FakeHeaderItem("STRT", "101"),
            FakeHeaderItem("STOP", "100"),
            FakeHeaderItem("STEP", "-1"),
            FakeHeaderItem("NULL", "-999.25"),
        ]

    monkeypatch.setattr(
        "geoworkbench.data.las_adapter.lasio.read", lambda *args, **kwargs: DescendingLas()
    )

    result = import_las_with_report(source)

    assert result.report.source.size_bytes == len(raw)
    assert result.report.source.sha256 == sha256(raw).hexdigest()
    assert result.source_document.to_bytes() == raw
    assert result.report.source.encoding == "utf-8"
    assert result.report.source.section_names == ()
    assert result.report.source.las_version == "2.0"
    assert result.report.source.wrap == "NO"
    assert result.report.source.null_value == pytest.approx(-999.25)
    assert result.report.depth_axis.direction is DepthDirection.DESCENDING
    assert any(issue.code == "index-descending" for issue in result.report.issues)


def test_import_las_detects_relative_time_index(tmp_path, monkeypatch) -> None:
    source = tmp_path / "time.las"
    source.write_text("fake", encoding="utf-8")

    class TimeLas(FakeLas):
        curves = [
            FakeHeaderItem("TIME", unit="s", descr="Elapsed time"),
            FakeHeaderItem("C1", unit="%", descr="Methane"),
        ]
        index = np.array([0.0, 1.0])
        _values = {"C1": np.array([1.0, 2.0])}

    monkeypatch.setattr("geoworkbench.data.las_adapter.lasio.read", lambda *a, **k: TimeLas())

    dataset = import_las(source)

    assert dataset.depth_domain is DepthDomain.TIME
    assert dataset.active_index.role is IndexRole.TIME
    assert dataset.active_index.index_type is IndexType.RELATIVE_TIME
    assert dataset.active_index.confidence >= 0.7


def test_import_report_detects_header_mismatch_and_duplicate_mnemonics(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "diagnostics.las"
    source.write_text("fake", encoding="utf-8")

    class ProblemLas(FakeLas):
        curves = [
            FakeHeaderItem("DEPT"),
            FakeHeaderItem("C1"),
            FakeHeaderItem("c1"),
        ]
        well = [
            FakeHeaderItem("STRT", "99"),
            FakeHeaderItem("STOP", "101"),
            FakeHeaderItem("STEP", "1"),
        ]
        _values = {"C1": np.array([1.0, 2.0]), "c1": np.array([1.0, 2.0])}

    monkeypatch.setattr(
        "geoworkbench.data.las_adapter.lasio.read", lambda *args, **kwargs: ProblemLas()
    )

    report = import_las_with_report(source).report
    codes = {issue.code for issue in report.issues}

    assert "duplicate-mnemonics" in codes
    assert "missing-null" in codes
    assert "header-strt-mismatch" in codes
    assert report.warning_count == len(report.issues)
    assert not report.has_errors


def test_import_report_detects_source_section_structure(tmp_path, monkeypatch) -> None:
    source = tmp_path / "sections.las"
    source.write_bytes(
        b"~V\r\nVERS. 2.0\r\n"
        b"~W\r\nNULL. -999.25\n"
        b"~W\nWELL. TEST\n"
        b"~C\nDEPT.M\nC1.%\n"
    )
    monkeypatch.setattr("geoworkbench.data.las_adapter.lasio.read", lambda *a, **k: FakeLas())

    report = import_las_with_report(source).report
    codes = {issue.code for issue in report.issues}

    assert report.source.section_names == ("v", "w", "w", "c")
    assert "duplicate-sections" in codes
    assert "missing-ascii-section" in codes
    assert "mixed-newlines" in codes


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


def test_lossless_export_preserves_custom_section_and_updates_data(tmp_path) -> None:
    source = tmp_path / "source.las"
    custom_section = b"~Other Vendor Block\r\n# keep this exact\r\nVENDOR_CODE. 42\r\n"
    source.write_bytes(
        b"~Version Information\r\n"
        b"VERS. 2.0 : LAS version\r\n"
        b"WRAP. NO : one line per depth\r\n"
        b"~Well Information\r\n"
        b"STRT.M 100\r\nSTOP.M 101\r\nSTEP.M 1\r\nNULL. -999.25\r\nWELL. TEST\r\n"
        b"~Curve Information\r\n"
        b"DEPT.M : Depth\r\nC1.% : Methane\r\n"
        + custom_section
        + b"~ASCII Log Data\r\n100 1\r\n101 2\r\n"
    )
    imported = import_las_with_report(source)
    imported.dataset.curve_by_mnemonic("C1").values[0] = 9.0  # type: ignore[union-attr]
    target = tmp_path / "edited.las"

    export_las(imported.dataset, target, source_document=imported.source_document)

    exported_bytes = target.read_bytes()
    assert custom_section in exported_bytes
    assert b"\r\n" in exported_bytes
    restored = import_las(target)
    c1 = restored.curve_by_mnemonic("C1")
    assert c1 is not None
    assert c1.values[0] == pytest.approx(9.0)


def test_export_plan_controls_version_wrap_null_and_precision(tmp_path) -> None:
    dataset = make_export_dataset()
    dataset.curve_by_mnemonic("ROP").values[:] = [10.123456, np.nan, 30.0]  # type: ignore[union-attr]
    target = tmp_path / "planned.las"

    export_las(
        dataset,
        target,
        plan=LasExportPlan(
            version=LasExportVersion.V1_2,
            wrap=True,
            null_value=-1234.5,
            precision=3,
        ),
    )

    written = target.read_text(encoding="utf-8")
    parsed = import_las_with_report(target)
    assert parsed.report.source.las_version == "1.2"
    assert parsed.report.source.wrap == "YES"
    assert parsed.report.source.null_value == pytest.approx(-1234.5)
    assert "10.123" in written
    assert "-1234.5" in written


def test_export_plan_can_explicitly_disable_custom_section_preservation(tmp_path) -> None:
    source = parse_lossless_las(b"~Other\nCUSTOM. keep\n")
    target = tmp_path / "plain.las"

    export_las(
        make_export_dataset(),
        target,
        source_document=source,
        plan=LasExportPlan(preserve_custom_sections=False),
    )

    assert b"CUSTOM. keep" not in target.read_bytes()


def test_export_refuses_null_collision_before_creating_file(tmp_path) -> None:
    dataset = make_export_dataset()
    dataset.curve_by_mnemonic("ROP").values[0] = -9999.25  # type: ignore[union-attr]
    target = tmp_path / "collision.las"

    with pytest.raises(LasExportError, match="NULL совпадает"):
        export_las(dataset, target, plan=LasExportPlan(null_value=-9999.25))

    assert not target.exists()


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
