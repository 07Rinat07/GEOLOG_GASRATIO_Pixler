from importlib import import_module

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6 import QtWidgets

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


def test_tablet_track_never_constructs_unused_viewbox_menu(qapp, monkeypatch) -> None:
    """Exercise the actual track constructor without allocating a disabled menu."""
    module = import_module("pyqtgraph.graphicsItems.ViewBox.ViewBox")

    def unexpected_menu(*args, **kwargs):
        raise AssertionError("Tablet track must not construct a native ViewBoxMenu")

    monkeypatch.setattr(module, "ViewBoxMenu", unexpected_menu)
    # The former implementation still allocated six QWidgetActions for the
    # disabled Plot Options menu; forbid that native allocation as well.
    with monkeypatch.context() as guard:
        guard.setattr(QtWidgets, "QWidgetAction", unexpected_menu)
        guard.setattr(QtWidgets, "QMenu", unexpected_menu)
        widget = TabletTrackWidget(TrackDefinition("curve", "Curve", TrackKind.CURVE))
    try:
        view_box = widget.plot.getViewBox()
        assert view_box.menu is None
        assert not view_box.menuEnabled()
        item = widget.plot.getPlotItem()
        assert not item.menuEnabled()
        assert item.ctrlMenu is None
        assert item.control_root.parentWidget() is widget.plot
        widget.plot.showGrid(x=True, y=True, alpha=0.5)
        assert item.ctrl.xGridCheck.isChecked() and item.ctrl.yGridCheck.isChecked()
        assert item.ctrl.gridAlphaSlider.value() > 0
        # The application-owned track header context action is independent
        # of the pyqtgraph menu. Mouse navigation must remain enabled.
        assert view_box.state["mouseEnabled"] == [True, True]
        requested: list[tuple[str, QPoint]] = []
        widget.context_requested.connect(
            lambda track_id, point: requested.append((track_id, point))
        )
        widget.resize(240, 300)
        widget.show()
        qapp.processEvents()
        QTest.mouseClick(
            widget.title, Qt.MouseButton.RightButton,
            pos=widget.title.rect().center(),
        )
        assert len(requested) == 1
        assert requested[0][0] == "curve"
    finally:
        widget.close()
