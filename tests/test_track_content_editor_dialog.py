from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.tablet.models import TrackKind
from geoworkbench.ui.track_content_editor_dialog import (
    TrackContentEditorDialog,
    _CurveOption,
    _CurveSelectionDialog,
)


def _structure() -> tuple[FormStructureEditor, str]:
    binding = ParameterBinding.create(
        "ROP",
        "Rate of penetration",
        source_mnemonic="ROP",
        unit="m/h",
    )
    track = FormTrack.create(
        "Drilling",
        TrackKind.CURVE,
        bindings=[binding],
    )
    column = FormColumn.create("Parameters", tracks=[track])
    form = FormDocument.create("Adaptive form", FormAxisKind.DEPTH)
    form.add_column(column)
    return FormStructureEditor(form), track.track_id


def test_track_content_editor_keeps_actions_visible_and_fits_work_area(qapp) -> None:
    structure, track_id = _structure()
    dialog = TrackContentEditorDialog(structure, track_id, language="en")
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert dialog.actions_toolbar.objectName() == "track-content-actions"
        assert len(dialog.actions_toolbar.actions()) == 5
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        assert not dialog.properties_scroll.isAncestorOf(buttons)
        assert dialog.table.rowCount() == 1
    finally:
        dialog.close()


def test_curve_selection_dialog_fits_work_area_and_filters(qapp) -> None:
    dialog = _CurveSelectionDialog(
        [
            _CurveOption("ROP", "ROP", "Rate of penetration", "m/h"),
            _CurveOption("C1", "C1", "Methane", "%"),
        ],
        language="en",
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()

        dialog.search.setText("methane")
        qapp.processEvents()
        assert dialog.list_widget.item(0).isHidden()
        assert not dialog.list_widget.item(1).isHidden()
    finally:
        dialog.close()
