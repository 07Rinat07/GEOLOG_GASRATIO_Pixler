from pathlib import Path

import pytest

from geoworkbench.importers.paradox.batch import _target_name


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
    adapter.import_las = lambda _target: SimpleNamespace(depth=[1.0, 2.0, 3.0])
    export_plan = ModuleType("geoworkbench.data.las_export_plan")
    export_plan.LasExportPlan = lambda **kwargs: kwargs
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
