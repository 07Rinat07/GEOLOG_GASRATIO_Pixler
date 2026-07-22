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

    assert result.status is batch.BatchStatus.ERROR
    assert result.records == 7
    assert result.warnings == 1
    assert "требуется профиль" in result.message
    assert "material_issues" not in result.message
