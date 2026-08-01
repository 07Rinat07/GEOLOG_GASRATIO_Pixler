from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.ui.grid_settings_widget import GridSettingsWidget
from geoworkbench.ui.tablet_track_editor_dialog import TabletTrackEditorDialog


def test_grid_settings_explains_axis_contract_and_dependent_states(qapp) -> None:
    widget = GridSettingsWidget(language="en")
    widget.set_values(False, False, 4, 10, 0.35, False)

    assert "Parameter X" in widget.grid_x_input.text()
    assert "Depth/time" in widget.grid_y_input.text()
    assert "Major intervals" in widget.grid_major_label.text()
    assert "intensity" in widget.grid_alpha_label.text().casefold()
    assert "5-unit" in widget.depth_standard_hint.text()
    assert "adaptive" in widget.depth_standard_hint.text()
    assert widget.grid_major_input.isEnabled() is False
    assert widget.grid_minor_input.isEnabled() is False
    assert widget.grid_alpha_input.isEnabled() is False
    assert widget.grid_print_input.isEnabled() is False
    assert widget.grid_major_label.isEnabled() is False
    assert widget.grid_minor_label.isEnabled() is False
    assert widget.grid_alpha_label.isEnabled() is False

    widget.grid_y_input.setChecked(True)
    assert widget.grid_major_input.isEnabled() is False
    assert widget.grid_major_label.isEnabled() is False
    assert widget.grid_minor_label.isEnabled() is False
    assert widget.grid_alpha_input.isEnabled() is True
    assert widget.grid_alpha_label.isEnabled() is True
    assert widget.grid_print_input.isEnabled() is True

    widget.grid_x_input.setChecked(True)
    assert widget.grid_major_input.isEnabled() is True
    assert widget.grid_minor_input.isEnabled() is True
    assert widget.grid_major_label.isEnabled() is True
    assert widget.grid_minor_label.isEnabled() is True
    widget.close()


def test_grid_settings_standard_is_one_explicit_print_ready_preset(qapp) -> None:
    widget = GridSettingsWidget(language="ru")
    widget.set_values(False, False, 2, 3, 0.75, False)
    emitted: list[bool] = []
    widget.settings_changed.connect(lambda: emitted.append(True))

    QTest.mouseClick(widget.standard_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert widget.values() == (True, True, 5, 5, 0.2, True)
    assert emitted == [True]
    assert widget.standard_button.text() == "Стандарт 5×5"
    widget.close()


def test_grid_settings_controls_have_accessible_names_and_help(qapp) -> None:
    widget = GridSettingsWidget(language="en")
    controls = (
        widget.grid_x_input,
        widget.grid_y_input,
        widget.grid_major_input,
        widget.grid_minor_input,
        widget.grid_alpha_input,
        widget.grid_print_input,
        widget.standard_button,
        widget.depth_standard_hint,
    )

    assert all(control.accessibleName() for control in controls)
    assert all(control.toolTip() for control in controls)
    widget.close()


def test_tablet_track_editor_reuses_grid_controls_and_preset(qapp) -> None:
    track = TrackDefinition(
        "curve",
        "Curve",
        TrackKind.CURVE,
        grid_x=False,
        grid_y=False,
        grid_major_divisions=2,
        grid_minor_divisions=3,
        grid_alpha=0.4,
        grid_print=False,
    )
    dialog = TabletTrackEditorDialog(track, language="en")

    assert dialog.grid_x_input is dialog.grid_editor.grid_x_input
    assert dialog.grid_y_input is dialog.grid_editor.grid_y_input
    dialog.grid_editor.standard_button.click()
    qapp.processEvents()
    candidate = dialog._track_from_controls()

    assert (
        candidate.grid_x,
        candidate.grid_y,
        candidate.grid_major_divisions,
        candidate.grid_minor_divisions,
        candidate.grid_alpha,
        candidate.grid_print,
    ) == (True, True, 5, 5, 0.2, True)
    dialog.close()
