from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lithology_quick_editor_exposes_saved_description() -> None:
    dialog = (ROOT / "src/geoworkbench/ui/lithology_interval_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "QPlainTextEdit" in dialog
    assert 'setObjectName("lithology-quick-description")' in dialog
    assert "def description(self) -> str | None:" in dialog


def test_lithology_reedit_persists_description_and_interval() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert "description=dialog.description" in source
    assert "content_language=self.language.value" in source
    assert "top_depth=dialog.top_depth" in source
    assert "bottom_depth=dialog.bottom_depth" in source


def test_stratigraphy_quick_reedit_preserves_all_localized_content() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert "for language_code, editor in dialog.name_inputs.items():" in source
    assert "for language_code, editor in dialog.description_inputs.items():" in source
    assert "interval.name_i18n.get(" in source
    assert "interval.description_i18n.get(" in source
