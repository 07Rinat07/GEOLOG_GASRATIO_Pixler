from __future__ import annotations

from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.ui.form_create_dialog import FormCreateDialog


def test_create_dialog_shows_existing_forms_and_blocks_duplicate_name(qapp) -> None:
    factory = FormDocument.create("Эталонная форма", FormAxisKind.DEPTH)
    factory.read_only = True
    user = FormDocument.create("Рабочая форма", FormAxisKind.TIME)

    dialog = FormCreateDialog([factory, user], language="ru")
    dialog.show()
    qapp.processEvents()

    assert dialog.tree.topLevelItemCount() == 2
    assert dialog.tree.topLevelItem(0).childCount() == 1
    assert dialog.tree.topLevelItem(1).childCount() == 1

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
