from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_create_and_tablet_save_use_library_reference_dialog() -> None:
    manager = (ROOT / "src/geoworkbench/ui/form_manager_dialog.py").read_text(encoding="utf-8")
    main_window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    dialog = (ROOT / "src/geoworkbench/ui/form_create_dialog.py").read_text(encoding="utf-8")

    assert "FormCreateDialog(" in manager
    assert "def _available_forms" in manager
    assert "materialized_factory_templates(self.dataset, self.language).values()" in manager
    assert 'mode="save"' in main_window
    assert "dialog.existing_form" in main_window

    save_handler = main_window.split("def save_current_tablet_as_user_form", 1)[1].split(
        "def save_tablet_preset", 1
    )[0]
    assert "FormCreateDialog(" in save_handler
    assert "QInputDialog.getText" not in save_handler

    assert "Все формы и шаблоны" in dialog
    assert "Детали выбранной формы" in dialog
    assert "Готовые формы" in dialog
    assert "self.create_button.setEnabled(False)" in dialog


def test_create_dialog_contains_ru_kk_en_user_guidance() -> None:
    dialog = (ROOT / "src/geoworkbench/ui/form_create_dialog.py").read_text(encoding="utf-8")

    for phrase in (
        "Создание формы",
        "Пішін жасау",
        "Create form",
        "Сохранение пользовательской формы",
        "Пайдаланушы пішінін сақтау",
        "Save user form",
        "Название новой формы:",
        "Жаңа пішін атауы:",
        "New form name:",
    ):
        assert phrase in dialog
