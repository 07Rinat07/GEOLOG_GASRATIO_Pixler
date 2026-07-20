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
    from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
    import numpy as np

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
