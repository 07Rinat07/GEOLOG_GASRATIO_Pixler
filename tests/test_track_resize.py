from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.tablet.resize import TrackResizeGesture
from geoworkbench.tablet.tablet_view import TabletTrackWidget


def test_resize_gesture_clamps_width() -> None:
    gesture = TrackResizeGesture(initial_width=250, initial_global_x=100)

    assert gesture.width_at(150) == 300
    assert gesture.width_at(-1000) == 80
    assert gesture.width_at(5000) == 2000


def test_track_widget_emits_width_after_dragging_right_edge(qapp) -> None:
    track = TrackDefinition("curve", "Curve", TrackKind.CURVE, width=240)
    widget = TabletTrackWidget(track)
    widget.resize(240, 300)
    widget.show()
    qapp.processEvents()
    requested: list[tuple[str, int]] = []
    widget.width_change_requested.connect(
        lambda track_id, width: requested.append((track_id, width))
    )

    QTest.mousePress(
        widget,
        Qt.MouseButton.LeftButton,
        pos=QPoint(widget.width() - 2, 100),
    )
    QTest.mouseMove(widget, QPoint(298, 100))
    QTest.mouseRelease(
        widget,
        Qt.MouseButton.LeftButton,
        pos=QPoint(298, 100),
    )
    qapp.processEvents()

    assert requested == [("curve", 300)]
    assert widget.width() == 300
    widget.close()
