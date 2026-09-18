from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.ui.tablet_track_editor_dialog import TabletTrackEditorDialog


def test_tablet_track_editor_fits_work_area_and_keeps_actions_reachable(qapp) -> None:
    track = TrackDefinition(
        track_id="adaptive-track",
        title="ROP",
        kind=TrackKind.CURVE,
        curve_mnemonics=["ROP"],
    )
    dialog = TabletTrackEditorDialog(track, language="en")
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()

        assert dialog.editor_scroll.objectName() == "tablet-track-editor-scroll"
        assert dialog.editor_scroll.minimumWidth() == 340
        assert dialog.preview.minimumWidth() == 220
        assert dialog.preview.minimumHeight() == 220

        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        assert not dialog.editor_scroll.isAncestorOf(dialog.toolbar)
        assert not dialog.editor_scroll.isAncestorOf(buttons)
    finally:
        dialog.close()
