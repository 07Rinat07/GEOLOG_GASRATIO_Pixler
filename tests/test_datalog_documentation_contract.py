"""DATALOG-SHOW-01 documentation synchronization and safety boundaries."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_datalog_documentation_is_indexed_and_source_scoped() -> None:
    index = (ROOT / "docs/DOCUMENTATION_INDEX.md").read_text(encoding="utf-8")
    spec = (ROOT / "docs/DATALOG_OIL_SHOW_METHODS.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/PROJECT_PLAN.md").read_text(encoding="utf-8")
    for name in ("ru", "kk", "en"):
        relative = f"{name}/DATALOG_OIL_SHOW_METHODS.md"
        assert relative in index
        guide = (ROOT / "docs" / relative).read_text(encoding="utf-8")
        assert "DATALOG_OIL_SHOW_METHODS.md" in guide
        assert "UV+" in guide and "UV" in guide
        assert "H₂S" in guide
        assert "QFT" in spec
    assert "DATALOG-SHOW-01" in plan
    assert "data-only" in plan
    assert "eb5c88148b93e731d28f188be08a8248fd663c8b792e17e52dce60a5f872c2ad" in spec


def test_documentation_never_claims_legacy_ui_is_full_datalog() -> None:
    for lang in ("ru", "kk", "en"):
        body = (
            ROOT / "docs" / lang / "DATALOG_OIL_SHOW_METHODS.md"
        ).read_text(encoding="utf-8")
        assert "lba_cut_*" in body
        assert "lba_residue_*" in body
        assert "LAS" in body
    spec = (ROOT / "docs/DATALOG_OIL_SHOW_METHODS.md").read_text(encoding="utf-8")
    assert "не подключён" in spec
    assert "migration" in spec
    assert "смешивается с водой" in spec
