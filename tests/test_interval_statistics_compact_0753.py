from pathlib import Path


def test_interval_statistics_panel_uses_compact_readable_layout() -> None:
    source = Path("src/geoworkbench/ui/interval_statistics_panel.py").read_text(
        encoding="utf-8"
    )

    assert "font-size:9px" in source
    assert "QTableWidget {font-size:8px" in source
    assert "setDefaultSectionSize(34)" in source
    assert "setColumnWidth(column, 66)" in source
    assert 'details = f"{details} · {item.unit}"' in source
    assert "ScrollBarAsNeeded" in source
