from __future__ import annotations

import pytest

from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.ui.tablet_track_editor_dialog import TabletTrackEditorDialog


@pytest.mark.parametrize("kind", [TrackKind.TEXT, TrackKind.INTERPRETATION])
def test_description_tracks_expose_interval_border_toggle(qapp, kind: TrackKind) -> None:
    track = TrackDefinition(
        "description-track",
        "Описание пород",
        kind,
        show_description_borders=False,
    )
    dialog = TabletTrackEditorDialog(track, language="ru")

    assert not dialog.show_description_borders_input.isHidden()
    assert not dialog.show_description_borders_input.isChecked()

    dialog.show_description_borders_input.setChecked(True)
    candidate = dialog._track_from_controls()

    assert candidate.show_description_borders is True
    # The editor works on a copy; the live layout is mutated only after the
    # accepted candidate crosses the TabletController boundary in MainWindow.
    assert track.show_description_borders is False
    dialog.close()


def test_non_description_track_hides_interval_border_toggle(qapp) -> None:
    track = TrackDefinition("curve-track", "ROP", TrackKind.CURVE)
    dialog = TabletTrackEditorDialog(track, language="ru")

    assert dialog.show_description_borders_input.isHidden()
    dialog.close()
