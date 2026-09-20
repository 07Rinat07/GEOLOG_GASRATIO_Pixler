from __future__ import annotations

from pathlib import Path

from geoworkbench.data.csv_adapter import CsvImportPlan, import_csv


def test_csv_import_attaches_semantic_channel_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "sample.csv"
    source.write_text("DEPTH [m],ROP [м/ч],S200 [т]\n100,4.5,15\n100.2,5.0,16\n", encoding="utf-8")

    result = import_csv(source, CsvImportPlan(index_column="DEPTH [m]"))
    curves = {curve.metadata.original_mnemonic: curve for curve in result.dataset.curves.values()}

    rop = curves["ROP"].metadata.semantic
    hookload = curves["S200"].metadata.semantic
    assert rop is not None
    assert rop.canonical_kind == "drilling.rop"
    assert rop.canonical_uom == "m/h"
    assert hookload is not None
    assert hookload.canonical_mnemonic == "HKLD"
    assert hookload.source_mnemonic == "S200"
    assert "csv_column=1" in rop.evidence
    assert "csv_header=ROP [м/ч]" in rop.evidence
    assert any(item.startswith("catalog_version=sensors-v1:") for item in rop.evidence)


def test_csv_import_uses_semantic_context_boundary() -> None:
    source = Path("src/geoworkbench/data/csv_adapter.py").read_text(encoding="utf-8")

    assert "semantic_dictionary.context(" in source
    assert 'f"csv_column={position}"' in source
    assert 'f"csv_header={header}"' in source
    assert "semantic_dictionary.resolve_context(semantic_context)" in source
