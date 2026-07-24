from __future__ import annotations

from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.ui.form_create_dialog import FormCreateDialog


def test_create_dialog_shows_ready_factory_user_forms_and_blocks_duplicate_name(qapp) -> None:
    factory = FormDocument.create("Эталонная форма", FormAxisKind.DEPTH)
    factory.form_id = "factory-test"
    factory.read_only = True
    ready = FormDocument.create("Готовая форма", FormAxisKind.DEPTH)
    ready.read_only = True
    user = FormDocument.create("Рабочая форма", FormAxisKind.TIME)

    dialog = FormCreateDialog([factory, ready, user], language="ru")
    dialog.show()
    qapp.processEvents()

    assert dialog.tree.topLevelItemCount() == 3
    assert dialog.tree.topLevelItem(0).childCount() == 1
    assert dialog.tree.topLevelItem(1).childCount() == 1
    assert dialog.tree.topLevelItem(2).childCount() == 1

    dialog.name_input.setText("  РАБОЧАЯ   ФОРМА ")
    qapp.processEvents()
    assert dialog.create_button.isEnabled() is False
    assert "уже существует" in dialog.validation_label.text()

    dialog.name_input.setText("Газовый каротаж — скважина 12")
    qapp.processEvents()
    assert dialog.create_button.isEnabled() is True


def test_create_dialog_returns_clean_name_and_selected_axis(qapp) -> None:
    dialog = FormCreateDialog([], language="en")
    dialog.name_input.setText("  Gas   monitoring  ")
    dialog.axis_combo.setCurrentIndex(1)
    dialog._accept()

    assert dialog.form_name == "Gas monitoring"
    assert dialog.axis_kind is FormAxisKind.TIME


def test_save_dialog_replaces_editable_form_but_protects_ready_template(qapp) -> None:
    ready = FormDocument.create("Мастерлог — A4, книжная", FormAxisKind.DEPTH)
    ready.read_only = True
    user = FormDocument.create("Скважина 12 — рабочая", FormAxisKind.DEPTH)

    dialog = FormCreateDialog(
        [ready, user],
        language="ru",
        mode="save",
        initial_name=user.name,
        initial_axis_kind=FormAxisKind.DEPTH,
        axis_editable=False,
    )
    qapp.processEvents()

    assert dialog.axis_combo.isEnabled() is False
    assert dialog.create_button.text() == "Сохранить"
    assert dialog.create_button.isEnabled() is True
    assert dialog.existing_form is user
    assert "новая ревизия" in dialog.validation_label.text()

    dialog.name_input.setText(ready.name)
    qapp.processEvents()
    assert dialog.create_button.isEnabled() is False
    assert dialog.existing_form is None
    assert "защищённым шаблоном" in dialog.validation_label.text()
