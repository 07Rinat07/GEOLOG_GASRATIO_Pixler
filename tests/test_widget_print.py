from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter
from PySide6.QtWidgets import QLabel
import pytest

from geoworkbench.printing.widget_print import WidgetPrintError, render_widget_to_printer


def _pdf_writer(path) -> QPdfWriter:
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Portrait)
    return writer


def test_widget_print_renderer_writes_pdf_writer_output(qapp, tmp_path) -> None:
    widget = QLabel("Print preview")
    widget.resize(640, 360)
    widget.show()
    qapp.processEvents()
    target = tmp_path / "preview.pdf"
    writer = _pdf_writer(target)

    render_widget_to_printer(widget, writer)
    del writer

    payload = target.read_bytes()
    assert payload.startswith(b"%PDF-")
    assert b"%%EOF" in payload[-1024:]
    widget.close()


def test_widget_print_renderer_rejects_zero_sized_widget(qapp, tmp_path) -> None:
    widget = QLabel("Hidden")
    widget.resize(0, 0)
    writer = _pdf_writer(tmp_path / "zero-sized.pdf")

    with pytest.raises(WidgetPrintError, match="размера"):
        render_widget_to_printer(widget, writer)
    del writer


def test_tablet_print_renderer_includes_all_tracks_and_restores_screen_widths(
    qapp, tmp_path
) -> None:
    import numpy as np

    from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
    from geoworkbench.printing.page_settings import PrintOrientation, PrintPageSettings
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
    from geoworkbench.tablet.tablet_view import TabletView

    dataset = Dataset(
        "dataset-print",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0]),
    )
    view = TabletView()
    view.resize(900, 620)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition("one", "One", TrackKind.CURVE, width=420),
                TrackDefinition("two", "Two", TrackKind.CURVE, width=360),
                TrackDefinition("three", "Three", TrackKind.TEXT, width=520),
            ]
        )
    )
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()
    original_widths = tuple(item.widget.width() for item in view.printable_tracks())

    target = tmp_path / "tablet-a4.pdf"
    writer = _pdf_writer(target)
    settings = PrintPageSettings(orientation=PrintOrientation.PORTRAIT)
    writer.setPageSize(settings.qt_page_size)
    writer.setPageOrientation(settings.qt_orientation)

    render_widget_to_printer(view, writer, fit_form_columns=True)
    del writer

    assert target.read_bytes().startswith(b"%PDF-")
    assert len(view.printable_tracks()) == 4
    assert tuple(item.widget.width() for item in view.printable_tracks()) == original_widths
    view.close()


def test_tablet_snapshot_filters_tracks_and_restores_print_grid_state(qapp, monkeypatch) -> None:
    import numpy as np

    from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
    from geoworkbench.printing.tablet_print import capture_tablet_print_snapshot
    from geoworkbench.tablet.grid_renderer import TabletGridOverlay, TabletGridRenderer
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
    from geoworkbench.tablet.tablet_view import TabletView

    dataset = Dataset(
        "dataset-snapshot-grid",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([47.0, 72.0, 97.0]),
    )
    view = TabletView()
    view.resize(700, 520)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition("one", "One", TrackKind.CURVE, width=360),
            ]
        )
    )
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()
    rendered = view.printable_tracks()
    target = next(item for item in rendered if item.definition.track_id == "one")
    target_overlay = TabletGridRenderer.overlay_for(target.widget.plot)
    assert target_overlay is not None
    original_widths = tuple(item.widget.width() for item in rendered)

    suppression_calls: list[tuple[TabletGridOverlay, bool]] = []
    print_mode_calls: list[tuple[TabletGridOverlay, bool]] = []
    original_set_suppressed = TabletGridOverlay.set_print_suppressed
    original_set_print_mode = TabletGridOverlay.set_print_mode

    def record_suppressed(self: TabletGridOverlay, suppressed: bool) -> None:
        suppression_calls.append((self, suppressed))
        original_set_suppressed(self, suppressed)

    def record_print_mode(self: TabletGridOverlay, enabled: bool) -> None:
        print_mode_calls.append((self, enabled))
        original_set_print_mode(self, enabled)

    monkeypatch.setattr(TabletGridOverlay, "set_print_suppressed", record_suppressed)
    monkeypatch.setattr(TabletGridOverlay, "set_print_mode", record_print_mode)

    snapshot = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        included_track_ids=("one",),
        grid_print_overrides={"one": False},
    )

    assert len(snapshot.pixmaps) == 1
    assert len(snapshot.layout.widths) == 1
    assert suppression_calls == [(target_overlay, True), (target_overlay, False)]
    assert print_mode_calls == [(target_overlay, True), (target_overlay, False)]
    assert target_overlay.print_suppressed is False
    assert target_overlay.print_mode is False
    assert tuple(item.widget.width() for item in rendered) == original_widths
    view.close()
