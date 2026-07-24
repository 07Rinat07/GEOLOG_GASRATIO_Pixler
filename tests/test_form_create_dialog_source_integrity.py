from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_create_form_uses_library_reference_dialog_instead_of_blind_name_prompt() -> None:
    manager = (ROOT / "src/geoworkbench/ui/form_manager_dialog.py").read_text(encoding="utf-8")
    dialog = (ROOT / "src/geoworkbench/ui/form_create_dialog.py").read_text(encoding="utf-8")

    assert "FormCreateDialog(" in manager
    assert "def _available_forms" in manager
    assert "materialized_factory_templates(self.dataset, self.language).values()" in manager
    assert "Существующие формы и шаблоны" in dialog
    assert "Детали выбранной формы" in dialog
    assert "duplicate_form_names" in dialog
    assert "self.create_button.setEnabled(False)" in dialog


def test_create_dialog_contains_ru_kk_en_user_guidance() -> None:
    dialog = (ROOT / "src/geoworkbench/ui/form_create_dialog.py").read_text(encoding="utf-8")

    for phrase in (
        "Создание формы",
        "Пішін жасау",
        "Create form",
        "Название новой формы:",
        "Жаңа пішін атауы:",
        "New form name:",
    ):
        assert phrase in dialog
