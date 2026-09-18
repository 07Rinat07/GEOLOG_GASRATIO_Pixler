import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.forms.models import FormAxisKind, FormDocument, FormPageOrientation
from geoworkbench.forms.repository import FormRepository
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
