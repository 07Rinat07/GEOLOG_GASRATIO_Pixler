from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_reference_pack_contains_only_derived_data_and_hashes() -> None:
    reference = ROOT / "vendor_reference/geosensor_geoscape2"
    forbidden = {".exe", ".dll", ".bpl", ".mdb", ".fdb", ".zip", ".pdf"}
    assert not [path for path in reference.rglob("*") if path.suffix.casefold() in forbidden]
    manifest = json.loads(
        (reference / "inventory/reference_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sourceArchive"]["sha256"] == (
        "b9b358b76e1956058421ce6969ff04a0c961a986160dc2f207d2bfa5a921cf44"  # pragma: allowlist secret
    )
    assert manifest["redistributionPolicy"]


def test_read_only_mdb_export_script_has_no_write_sql() -> None:
    source = (ROOT / "tools/export_geosensor_gswits_mdb.ps1").read_text(
        encoding="utf-8"
    )
    upper = source.upper()
    assert "MODE=READ" in upper
    assert 'COMMANDTEXT = "SELECT * FROM' in upper
    for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE", "ALTER TABLE"):
        assert forbidden not in upper
    assert "GET-FILEHASH" in upper
