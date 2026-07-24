from pathlib import Path
import struct

import numpy as np
import pytest

from geoworkbench.importers.paradox.batch import _target_name


def _encode_sorted(payload: bytes) -> bytes:
    data = bytearray(payload)
    if data[0] & 0x80:
        return bytes((~byte) & 0xFF for byte in data)
    data[0] |= 0x80
    return bytes(data)


def _encode_number(value: float) -> bytes:
    return _encode_sorted(struct.pack(">d", value))


def _write_fractional_depth_paradox(path: Path, step: float) -> None:
    header_size = 0x1000
    block_size = 0x800
    record_size = 16
    rows = tuple((100.0 + index * step, 10.0 + index) for index in range(4))
    header = bytearray(header_size)
    struct.pack_into("<H", header, 0x00, record_size)
    struct.pack_into("<H", header, 0x02, header_size)
    header[0x04] = 2
    header[0x05] = block_size // 1024
    struct.pack_into("<I", header, 0x06, len(rows))
    struct.pack_into("<H", header, 0x0C, 1)
    struct.pack_into("<H", header, 0x0E, 1)
    struct.pack_into("<H", header, 0x10, 1)
    struct.pack_into("<H", header, 0x21, 2)
    header[0x39] = 12
    struct.pack_into("<H", header, 0x6A, 1251)
    header[0x78:0x7C] = bytes((6, 8, 6, 8))
    cursor = 0x7C
    for value in (b"STEP.db\x00", b"DEPT\x00", b"VALUE\x00"):
        header[cursor : cursor + len(value)] = value
        cursor += len(value)
    header[cursor : cursor + 4] = struct.pack("<HH", 1, 2)

    block = bytearray(block_size)
    struct.pack_into("<HHh", block, 0, 0, 0, (len(rows) - 1) * record_size)
    cursor = 6
    for depth, value in rows:
        payload = _encode_number(depth) + _encode_number(value)
        block[cursor : cursor + record_size] = payload
        cursor += record_size
    path.write_bytes(header + block)


def test_batch_name_mask_supports_only_safe_filename_placeholders() -> None:
    source = Path('/tmp/BLData.db')

    assert _target_name('{source_name}_{mode}.las', source, 'depth') == 'BLData_depth.las'
    assert _target_name('{source_name}-{mode}', source, 'time') == 'BLData-time.las'

    with pytest.raises(ValueError, match='только'):
        _target_name('{unknown}.las', source, 'depth')
    with pytest.raises(ValueError, match='путь'):
        _target_name('../{source_name}.las', source, 'depth')


def test_batch_ambiguous_table_requires_manual_configuration(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        IssueSeverity,
        ParadoxIssue,
        QualitySummary,
    )

    source = tmp_path / "ambiguous.db"
    source.write_bytes(b"placeholder")
    table = SimpleNamespace(rows_read=7)
    issue = ParadoxIssue(
        IssueSeverity.WARNING,
        "ambiguous-index",
        "Несколько кандидатов индекса",
        source,
    )
    quality = QualitySummary(DatasetClassification.MIXED, (), (), (issue,))
    monkeypatch.setattr(batch, "read_paradox", lambda *args, **kwargs: table)
    monkeypatch.setattr(batch, "analyze_table", lambda value: quality)

    (result,) = batch.convert_batch([source], tmp_path / "out")

    assert result.status is batch.BatchStatus.CONFIGURATION_REQUIRED
    assert result.records == 7
    assert result.warnings == 1
    assert "требуется профиль" in result.message
    assert "material_issues" not in result.message


def test_batch_rejects_duplicate_target_names_before_reading(tmp_path: Path) -> None:
    from geoworkbench.importers.paradox import batch

    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    with pytest.raises(ValueError, match="один файл|Несколько операций"):
        batch.convert_batch(
            [first, second],
            tmp_path / "out",
            name_mask="result.las",
        )


def test_batch_manual_plan_converts_ambiguous_table(tmp_path: Path, monkeypatch) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        ParadoxImportPlan,
        QualitySummary,
    )

    source = tmp_path / "ambiguous.db"
    source.write_bytes(b"placeholder")
    table = SimpleNamespace(rows_read=3)
    quality = QualitySummary(DatasetClassification.MIXED, (), (), ())
    dataset = SimpleNamespace(
        active_index=SimpleNamespace(values=[1.0, 2.0, 3.0]),
        curves={},
        parameters={},
    )
    imported = SimpleNamespace(dataset=dataset, imported_channels=2)
    plan = ParadoxImportPlan(
        classification=DatasetClassification.MIXED,
        depth_field="DEPTH",
        time_field="TIME",
        active_role="depth",
    )

    monkeypatch.setattr(batch, "read_paradox", lambda *args, **kwargs: table)
    monkeypatch.setattr(batch, "analyze_table", lambda value: quality)
    monkeypatch.setattr(batch, "import_paradox", lambda *args, **kwargs: imported)

    adapter = ModuleType("geoworkbench.data.las_adapter")

    def export_las(_dataset, target, **_kwargs):
        Path(target).write_text("LAS", encoding="utf-8")

    adapter.export_las = export_las
    adapter.import_las = lambda _target: SimpleNamespace(
        active_index=SimpleNamespace(values=[1.0, 2.0, 3.0]),
        headers={"STRT": "1", "STOP": "3", "STEP": "1"},
        curves={},
    )
    export_plan = ModuleType("geoworkbench.data.las_export_plan")
    export_plan.LasExportPlan = lambda **kwargs: SimpleNamespace(precision=5, **kwargs)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_adapter", adapter)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_export_plan", export_plan)

    (result,) = batch.convert_batch(
        [source],
        tmp_path / "out",
        plan_factory=lambda _source, _table: plan,
    )

    assert result.status is batch.BatchStatus.SUCCESS
    assert result.target is not None and result.target.is_file()
    assert result.records == 3
    assert result.channels == 2


def test_batch_manual_plan_accepts_qt_string_enums(tmp_path: Path, monkeypatch) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        ParadoxImportPlan,
        QualitySummary,
    )

    source = tmp_path / "qt-plan.db"
    source.write_bytes(b"placeholder")
    table = SimpleNamespace(rows_read=2)
    quality = QualitySummary(DatasetClassification.MIXED, (), (), ())
    dataset = SimpleNamespace(
        active_index=SimpleNamespace(values=[1.0, 2.0]),
        curves={},
        parameters={},
    )
    imported = SimpleNamespace(dataset=dataset, imported_channels=1)
    plan = ParadoxImportPlan(
        classification="mixed",
        depth_field="DEPTH",
        time_field="TIME",
        active_role="time",
        duplicate_depth_policy="keep_all",
    )

    monkeypatch.setattr(batch, "read_paradox", lambda *args, **kwargs: table)
    monkeypatch.setattr(batch, "analyze_table", lambda value: quality)
    monkeypatch.setattr(batch, "import_paradox", lambda *args, **kwargs: imported)

    adapter = ModuleType("geoworkbench.data.las_adapter")
    adapter.export_las = lambda _dataset, target, **_kwargs: Path(target).write_text(
        "LAS", encoding="utf-8"
    )
    adapter.import_las = lambda _target: SimpleNamespace(
        active_index=SimpleNamespace(values=[1.0, 2.0]),
        headers={"STRT": "1", "STOP": "2", "STEP": "1"},
        curves={},
    )
    export_plan = ModuleType("geoworkbench.data.las_export_plan")
    export_plan.LasExportPlan = lambda **kwargs: SimpleNamespace(precision=5, **kwargs)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_adapter", adapter)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_export_plan", export_plan)

    (result,) = batch.convert_batch(
        [source],
        tmp_path / "out",
        mode="time",
        plan_factory=lambda _source, _table: plan,
    )

    assert result.status is batch.BatchStatus.SUCCESS
    assert "object has no attribute" not in result.message


def test_batch_error_identifies_conversion_stage(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        QualitySummary,
    )

    source = tmp_path / "stage.db"
    source.write_bytes(b"placeholder")
    table = SimpleNamespace(rows_read=1)
    quality = QualitySummary(DatasetClassification.DEPTH, (), (), ())
    monkeypatch.setattr(batch, "read_paradox", lambda *args, **kwargs: table)
    monkeypatch.setattr(batch, "analyze_table", lambda value: quality)

    (result,) = batch.convert_batch(
        [source],
        tmp_path / "out",
        plan_factory=lambda _source, _table: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert result.status is batch.BatchStatus.ERROR
    assert "подготовка плана импорта" in result.message
    assert "boom" in result.message


@pytest.mark.parametrize("step", [0.2, 0.4])
def test_batch_preserves_actual_fractional_depth_step(
    tmp_path: Path,
    step: float,
) -> None:
    from geoworkbench.data.las_adapter import import_las
    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.importer import default_mappings
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        ParadoxImportPlan,
    )
    from geoworkbench.importers.paradox.reader import read_paradox

    source = tmp_path / f"step-{step:g}.db"
    _write_fractional_depth_paradox(source, step)
    table = read_paradox(source)
    plan = ParadoxImportPlan(
        classification=DatasetClassification.DEPTH,
        depth_field="DEPT",
        active_role="depth",
        mappings=default_mappings(table),
    )

    (result,) = batch.convert_batch(
        [source],
        tmp_path / "out",
        plan_factory=lambda _source, _table: plan,
    )

    assert result.status is batch.BatchStatus.SUCCESS
    assert result.target is not None
    reopened = import_las(result.target)
    np.testing.assert_allclose(
        reopened.depth,
        np.array([100.0, 100.0 + step, 100.0 + 2 * step, 100.0 + 3 * step]),
    )
    assert float(reopened.headers["STEP"]) == pytest.approx(step)
    assert f"STEP={step:g}" in result.message


def test_batch_roundtrip_failure_does_not_replace_or_leave_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        ParadoxImportPlan,
        QualitySummary,
    )

    source = tmp_path / "failure.db"
    source.write_bytes(b"placeholder")
    output = tmp_path / "out"
    output.mkdir()
    target = output / "failure_depth.las"
    target.write_text("previous verified LAS", encoding="utf-8")
    table = SimpleNamespace(rows_read=2)
    quality = QualitySummary(DatasetClassification.DEPTH, (), (), ())
    imported = SimpleNamespace(
        dataset=SimpleNamespace(
            active_index=SimpleNamespace(values=[100.0, 100.4]),
            curves={},
            parameters={},
        ),
        imported_channels=0,
    )
    plan = ParadoxImportPlan(
        classification=DatasetClassification.DEPTH,
        depth_field="DEPTH",
        active_role="depth",
    )
    monkeypatch.setattr(batch, "read_paradox", lambda *args, **kwargs: table)
    monkeypatch.setattr(batch, "analyze_table", lambda value: quality)
    monkeypatch.setattr(batch, "import_paradox", lambda *args, **kwargs: imported)

    adapter = ModuleType("geoworkbench.data.las_adapter")
    adapter.export_las = lambda _dataset, path, **_kwargs: Path(path).write_text(
        "unverified candidate", encoding="utf-8"
    )
    adapter.import_las = lambda _path: (_ for _ in ()).throw(
        RuntimeError("round-trip failed")
    )
    export_plan = ModuleType("geoworkbench.data.las_export_plan")
    export_plan.LasExportPlan = lambda **kwargs: SimpleNamespace(precision=5, **kwargs)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_adapter", adapter)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_export_plan", export_plan)

    (result,) = batch.convert_batch(
        [source],
        output,
        overwrite=True,
        plan_factory=lambda _source, _table: plan,
    )

    assert result.status is batch.BatchStatus.ERROR
    assert target.read_text(encoding="utf-8") == "previous verified LAS"
    assert not list(output.glob("*.pending.las"))


def test_batch_can_create_explicit_geoscape_02_derived_grid(tmp_path: Path) -> None:
    from geoworkbench.data.las_adapter import import_las
    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.importer import default_mappings
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        ParadoxImportPlan,
    )
    from geoworkbench.importers.paradox.reader import read_paradox

    source = tmp_path / "source-04.db"
    _write_fractional_depth_paradox(source, 0.4)
    table = read_paradox(source)
    plan = ParadoxImportPlan(
        classification=DatasetClassification.DEPTH,
        depth_field="DEPT",
        active_role="depth",
        mappings=default_mappings(table),
    )

    (result,) = batch.convert_batch(
        [source],
        tmp_path / "out",
        plan_factory=lambda _source, _table: plan,
        target_depth_step=0.2,
    )

    assert result.status is batch.BatchStatus.SUCCESS
    assert result.target is not None
    reopened = import_las(result.target)
    np.testing.assert_allclose(reopened.depth, np.arange(100.0, 101.21, 0.2))
    np.testing.assert_allclose(
        reopened.curve_by_mnemonic("VALUE").values,
        np.arange(10.0, 13.01, 0.5),
    )
    assert float(reopened.headers["STEP"]) == pytest.approx(0.2)
    assert reopened.parameters["PARADOX_BATCH_TARGET_DEPTH_STEP_M"] == "0.2"
    assert reopened.parameters["PARADOX_BATCH_RESAMPLE_METHOD"] == (
        "linear-without-bridging"
    )


def test_batch_uses_explicit_dept_candidate_even_when_table_is_classified_mixed() -> None:
    from geoworkbench.importers.paradox.batch import _select_automatic_candidate
    from geoworkbench.importers.paradox.models import IndexCandidate

    candidates = (
        IndexCandidate("RANGE", "depth", 0.88, (), ()),
        IndexCandidate("DEPT", "depth", 0.82, (), ("reverse",)),
    )
    underscored = (IndexCandidate("HOLE_DEPTH", "depth", 0.75, (), ()),)

    assert _select_automatic_candidate(candidates, "depth") == "DEPT"
    assert _select_automatic_candidate(underscored, "depth") == "HOLE_DEPTH"


def test_batch_does_not_guess_between_generic_close_candidates() -> None:
    from geoworkbench.importers.paradox.batch import _select_automatic_candidate
    from geoworkbench.importers.paradox.models import IndexCandidate

    candidates = (
        IndexCandidate("S110", "depth", 0.81, (), ()),
        IndexCandidate("S115", "depth", 0.78, (), ()),
    )

    assert _select_automatic_candidate(candidates, "depth") is None


def test_batch_auto_uses_explicit_dept_from_mixed_table_and_sorts_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    from geoworkbench.importers.paradox import batch
    from geoworkbench.importers.paradox.models import (
        DatasetClassification,
        IndexCandidate,
        QualitySummary,
    )

    source = tmp_path / "D1174.db"
    source.write_bytes(b"placeholder")
    table = SimpleNamespace(rows_read=3)
    quality = QualitySummary(
        DatasetClassification.MIXED,
        (
            IndexCandidate("RANGE", "depth", 0.88, (), ()),
            IndexCandidate("DEPT", "depth", 0.82, (), ("mixed-order",)),
        ),
        (),
        (),
    )
    captured = {}
    dataset = SimpleNamespace(
        active_index=SimpleNamespace(values=[100.0, 101.0, 102.0]),
        curves={},
        parameters={},
    )
    imported = SimpleNamespace(dataset=dataset, imported_channels=70)

    monkeypatch.setattr(batch, "read_paradox", lambda *args, **kwargs: table)
    monkeypatch.setattr(batch, "analyze_table", lambda value: quality)
    monkeypatch.setattr(batch, "default_mappings", lambda *args, **kwargs: ())

    def import_paradox(_source, plan, **_kwargs):
        captured["plan"] = plan
        return imported

    monkeypatch.setattr(batch, "import_paradox", import_paradox)

    adapter = ModuleType("geoworkbench.data.las_adapter")
    adapter.export_las = lambda _dataset, target, **_kwargs: Path(target).write_text(
        "LAS", encoding="utf-8"
    )
    adapter.import_las = lambda _target: SimpleNamespace(
        active_index=SimpleNamespace(values=[100.0, 101.0, 102.0]),
        headers={"STRT": "100", "STOP": "102", "STEP": "1"},
        curves={},
    )
    export_plan = ModuleType("geoworkbench.data.las_export_plan")
    export_plan.LasExportPlan = lambda **kwargs: SimpleNamespace(precision=5, **kwargs)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_adapter", adapter)
    monkeypatch.setitem(sys.modules, "geoworkbench.data.las_export_plan", export_plan)

    (result,) = batch.convert_batch([source], tmp_path / "out")

    assert result.status is batch.BatchStatus.SUCCESS
    assert captured["plan"].depth_field == "DEPT"
    assert captured["plan"].sort_by_index is True
    assert captured["plan"].active_role == "depth"
