from pathlib import Path
from types import SimpleNamespace
import re

import numpy as np
from PySide6.QtWidgets import QLabel, QPushButton

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.forms.models import FormAxisKind, FormDocument, FormPageOrientation
from geoworkbench.forms.repository import FormRepository
from geoworkbench.printing.form_width_advisor import FormWidthLevel
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageSettings,
)
from geoworkbench.ui.form_manager_dialog import FormManagerDialog


def test_form_manager_changes_a4_orientation_and_persists_callback(qapp, tmp_path) -> None:
    received: list[PrintPageSettings] = []
    dialog = FormManagerDialog(
        FormRepository(tmp_path / "forms"),
        language="en",
        print_page_settings=PrintPageSettings(orientation=PrintOrientation.PORTRAIT),
        print_page_settings_changed=received.append,
    )

    dialog.print_orientation_combo.setCurrentIndex(
        dialog.print_orientation_combo.findData(PrintOrientation.LANDSCAPE.value)
    )

    assert received
    assert received[-1].orientation is PrintOrientation.LANDSCAPE
    assert received[-1].fit_form_columns is True
    assert dialog.print_orientation_combo.currentText() == "A4 — landscape"
    dialog.close()


def test_form_manager_can_disable_adaptive_column_fit(qapp, tmp_path) -> None:
    received: list[PrintPageSettings] = []
    dialog = FormManagerDialog(
        FormRepository(tmp_path / "forms"),
        print_page_settings_changed=received.append,
    )

    dialog.fit_columns_check.setChecked(False)

    assert received[-1].fit_form_columns is False
    dialog.close()


def test_form_manager_print_button_calls_selected_form_callback(qapp, tmp_path) -> None:
    selected = []
    dataset = Dataset(
        "dataset-form-print",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0]),
    )
    dialog = FormManagerDialog(
        FormRepository(tmp_path / "forms"),
        dataset=dataset,
        print_form_callback=selected.append,
    )

    assert dialog.print_button.isEnabled()
    dialog.print_button.click()

    assert selected
    assert selected[-1].form_id == dialog._current().form_id
    dialog.close()



def test_orientation_switch_selects_paired_form_from_same_family(qapp, tmp_path) -> None:
    received: list[PrintPageSettings] = []
    dialog = FormManagerDialog(
        FormRepository(tmp_path / "forms"),
        language="en",
        print_page_settings=PrintPageSettings(orientation=PrintOrientation.PORTRAIT),
        print_page_settings_changed=received.append,
    )
    before = dialog._current()

    assert before is not None
    assert before.preferred_page_orientation is FormPageOrientation.PORTRAIT

    dialog.print_orientation_combo.setCurrentIndex(
        dialog.print_orientation_combo.findData(PrintOrientation.LANDSCAPE.value)
    )
    after = dialog._current()

    assert after is not None
    assert after.family_id == before.family_id
    assert after.form_id != before.form_id
    assert after.preferred_page_orientation is FormPageOrientation.LANDSCAPE
    assert dialog.print_page_settings.orientation is PrintOrientation.LANDSCAPE
    assert received[-1].orientation is PrintOrientation.LANDSCAPE
    dialog.close()


def test_orientation_switch_fails_closed_when_family_pair_is_missing(qapp, tmp_path) -> None:
    repository = FormRepository(tmp_path / "forms")
    form = FormDocument.create(
        "Customer portrait",
        FormAxisKind.DEPTH,
        preferred_page_orientation=FormPageOrientation.PORTRAIT,
    )
    repository.save(form)
    received: list[PrintPageSettings] = []
    dialog = FormManagerDialog(
        repository,
        language="en",
        print_page_settings=PrintPageSettings(orientation=PrintOrientation.PORTRAIT),
        print_page_settings_changed=received.append,
    )
    dialog.reload(form.form_id)

    dialog.print_orientation_combo.setCurrentIndex(
        dialog.print_orientation_combo.findData(PrintOrientation.LANDSCAPE.value)
    )

    current = dialog._current()
    assert current is not None
    assert current.form_id == form.form_id
    assert dialog.print_page_settings.orientation is PrintOrientation.PORTRAIT
    assert (
        dialog.print_orientation_combo.currentData()
        == PrintOrientation.PORTRAIT.value
    )
    assert "no paired layout" in dialog.print_layout_hint.text()
    assert not [
        settings
        for settings in received
        if settings.orientation is PrintOrientation.LANDSCAPE
    ]
    dialog.close()


def test_explicit_form_selection_synchronizes_page_before_print(qapp, tmp_path) -> None:
    repository = FormRepository(tmp_path / "forms")
    form = FormDocument.create(
        "Customer landscape",
        FormAxisKind.DEPTH,
        preferred_page_orientation=FormPageOrientation.LANDSCAPE,
    )
    repository.save(form)
    dataset = Dataset(
        "dataset-family-print",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0]),
    )
    received: list[PrintPageSettings] = []
    printed: list[FormDocument] = []
    dialog = FormManagerDialog(
        repository,
        language="en",
        dataset=dataset,
        print_page_settings=PrintPageSettings(orientation=PrintOrientation.PORTRAIT),
        print_page_settings_changed=received.append,
        print_form_callback=printed.append,
    )

    dialog.reload(form.form_id)

    assert dialog.print_page_settings.orientation is PrintOrientation.LANDSCAPE
    assert (
        dialog.print_orientation_combo.currentData()
        == PrintOrientation.LANDSCAPE.value
    )
    assert received == []

    dialog.print_button.click()

    assert printed and printed[-1].form_id == form.form_id
    assert received and received[-1].orientation is PrintOrientation.LANDSCAPE
    dialog.close()



def test_form_manager_restores_explicit_initial_form_id(qapp, tmp_path) -> None:
    repository = FormRepository(tmp_path / "forms")
    selected = FormDocument.create(
        "Persisted landscape",
        FormAxisKind.DEPTH,
        preferred_page_orientation=FormPageOrientation.LANDSCAPE,
    )
    repository.save(selected)

    dialog = FormManagerDialog(
        repository,
        language="en",
        print_page_settings=PrintPageSettings(orientation=PrintOrientation.PORTRAIT),
        initial_form_id=selected.form_id,
    )

    current = dialog._current()
    assert current is not None
    assert current.form_id == selected.form_id
    assert dialog.print_page_settings.orientation is PrintOrientation.LANDSCAPE
    dialog.close()


def test_form_manager_stale_initial_form_id_falls_back_to_page_orientation(
    qapp, tmp_path
) -> None:
    dialog = FormManagerDialog(
        FormRepository(tmp_path / "forms"),
        language="en",
        print_page_settings=PrintPageSettings(orientation=PrintOrientation.LANDSCAPE),
        initial_form_id="deleted-form-id",
    )

    current = dialog._current()
    assert current is not None
    assert current.form_id != "deleted-form-id"
    assert current.preferred_page_orientation is FormPageOrientation.LANDSCAPE
    assert dialog.print_page_settings.orientation is PrintOrientation.LANDSCAPE
    dialog.close()

def test_form_manager_imports_geosight_form_through_callback(
    qapp, tmp_path, monkeypatch
) -> None:
    repository = FormRepository(tmp_path / "forms")
    imported = FormDocument.create("Legacy GeoSight", FormAxisKind.TIME)
    selected_file = tmp_path / "legacy.sf2"
    selected_file.write_text("object MainForm: TForm\nend\n", encoding="cp1251")
    received = []

    def import_geosight(source):
        received.append(source)
        repository.save(imported)
        return imported, "GeoSight imported"

    monkeypatch.setattr(
        "geoworkbench.ui.form_manager_dialog.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(selected_file), ""),
    )
    messages = []
    monkeypatch.setattr(
        "geoworkbench.ui.form_manager_dialog.QMessageBox.information",
        lambda _parent, _title, message: messages.append(message),
    )
    dialog = FormManagerDialog(
        repository,
        language="en",
        geosight_import_callback=import_geosight,
    )
    button = next(
        item
        for item in dialog.findChildren(QPushButton)
        if item.text() == "Import GeoSight"
    )

    button.click()

    assert received == [selected_file]
    current = dialog._current()
    assert current is not None
    assert current.form_id == imported.form_id
    assert messages[-1] == "GeoSight imported"
    dialog.close()



def test_form_manager_uses_shared_palette_aware_presentation(qapp, tmp_path) -> None:
    dialog = FormManagerDialog(FormRepository(tmp_path / "forms"), language="en")

    assert dialog.objectName() == "form-manager-dialog"
    assert dialog.styleSheet() == ""
    heading = dialog.findChild(QLabel, "form-manager-heading")
    assert heading is not None
    assert heading.styleSheet() == ""
    assert dialog.print_layout_hint.objectName() == "form-manager-print-layout-hint"
    assert dialog.print_layout_hint.styleSheet() == ""
    primary_buttons = [
        button
        for button in dialog.findChildren(QPushButton)
        if button.property("uiRole") == "primary"
    ]
    assert len(primary_buttons) >= 4
    dialog.close()


def test_form_manager_print_hint_uses_semantic_roles(qapp, tmp_path, monkeypatch) -> None:
    dialog = FormManagerDialog(FormRepository(tmp_path / "forms"), language="en")
    dialog._family_pair_message = "No paired layout is available."
    dialog._update_print_layout_hint()
    assert dialog.print_layout_hint.property("hintRole") == "warning"

    dialog._family_pair_message = None
    for level, expected_role in (
        (FormWidthLevel.FITS_PORTRAIT, "success"),
        (FormWidthLevel.FITS_LANDSCAPE, "warning"),
        (FormWidthLevel.NEEDS_FIT, "warning"),
        (FormWidthLevel.NEEDS_SPLIT, "error"),
    ):
        monkeypatch.setattr(
            "geoworkbench.ui.form_manager_dialog.audit_form_width",
            lambda _widths, level=level: SimpleNamespace(
                visible_columns=3,
                total_width_px=780,
                total_width_mm=206.0,
                portrait_scale_percent=92.0,
                landscape_scale_percent=100.0,
                level=level,
            ),
        )
        dialog._update_print_layout_hint()
        assert dialog.print_layout_hint.property("hintRole") == expected_role
        assert dialog.print_layout_hint.styleSheet() == ""

    dialog.close()


def test_form_manager_source_has_no_local_presentation_qss_or_fixed_hex() -> None:
    source = Path(
        "src/geoworkbench/ui/form_manager_dialog.py"
    ).read_text(encoding="utf-8")

    assert ".setStyleSheet(" not in source
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", source) is None
    assert 'setProperty("uiRole", "primary")' in source
    assert 'setObjectName("form-manager-print-layout-hint")' in source
