from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.new_las_dialog import NewLasDialog


def test_new_las_dialog_previews_grid_and_blocks_invalid_range(qapp) -> None:
    dialog = NewLasDialog(language=AppLanguage.EN)
    ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    dialog.stop_input.setValue(1.0)
    dialog.step_input.setValue(0.2)

    assert dialog.plan is not None
    assert dialog.plan.sample_count == 6
    assert "6 samples" in dialog.preview.text()
    assert ok_button.isEnabled()

    dialog.stop_input.setValue(0.0)
    assert dialog.plan is None
    assert "Invalid" in dialog.preview.text()
    assert not ok_button.isEnabled()
    dialog.close()
