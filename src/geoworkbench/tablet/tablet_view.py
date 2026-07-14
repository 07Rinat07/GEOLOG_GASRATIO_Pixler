from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale


@dataclass(slots=True)
class RenderedTrack:
    definition: TrackDefinition
    widget: QWidget
    plot: pg.PlotWidget | None = None


class TabletTrackWidget(QFrame):
    selected = Signal(str)

    def __init__(self, definition: TrackDefinition) -> None:
        super().__init__()
        self.definition = definition
        self.setObjectName(f"track-{definition.track_id}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(definition.width)
        self.setMaximumWidth(definition.width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.title = QLabel(definition.title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-weight: 600; padding: 5px; border-bottom: 1px solid palette(mid);")

        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.getViewBox().invertY(True)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title)
        layout.addWidget(self.plot)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.selected.emit(self.definition.track_id)
        super().mousePressEvent(event)


class TabletView(QWidget):
    """Многотрековый планшет с общей синхронизированной шкалой глубины."""

    track_selected = Signal(str)
    visible_depth_changed = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        pg.setConfigOptions(antialias=False)
        self._dataset: Dataset | None = None
        self._layout_model = TabletLayout()
        self._rendered: dict[str, RenderedTrack] = {}
        self._sync_guard = False

        self._container = QWidget()
        self._tracks_layout = QHBoxLayout(self._container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(2)
        self._tracks_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._container)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._scroll)

    @property
    def layout_model(self) -> TabletLayout:
        return self._layout_model

    @property
    def rendered_track_ids(self) -> tuple[str, ...]:
        return tuple(self._rendered)

    def set_dataset(self, dataset: Dataset | None) -> None:
        self._dataset = dataset
        self.refresh_view()

    def set_layout_model(self, layout_model: TabletLayout) -> None:
        self._layout_model = layout_model
        self.refresh_view()

    def add_track(self, definition: TrackDefinition) -> None:
        self._layout_model.add_track(definition)
        self.refresh_view()

    def remove_track(self, track_id: str) -> None:
        self._layout_model.remove_track(track_id)
        self.refresh_view()

    def clear(self) -> None:
        while self._tracks_layout.count():
            item = self._tracks_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rendered.clear()

    def refresh_view(self) -> None:
        self.clear()
        if self._dataset is None:
            label = QLabel("Откройте LAS-файл для построения планшета")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tracks_layout.addWidget(label)
            return

        visible = self._layout_model.visible_tracks()
        if not visible:
            label = QLabel("Добавьте трек в планшет")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tracks_layout.addWidget(label)
            return

        master_plot: pg.PlotWidget | None = None
        for definition in visible:
            track = TabletTrackWidget(definition)
            track.selected.connect(self.track_selected)
            self._populate_track(track, definition)
            if master_plot is None:
                master_plot = track.plot
                master_plot.sigYRangeChanged.connect(self._on_master_y_range_changed)
            else:
                track.plot.setYLink(master_plot)
            rendered = RenderedTrack(definition, track, track.plot)
            self._rendered[definition.track_id] = rendered
            self._tracks_layout.addWidget(track)

        self._tracks_layout.addStretch(1)
        depth = np.asarray(self._dataset.depth, dtype=float)
        finite = depth[np.isfinite(depth)]
        if master_plot is not None and finite.size:
            master_plot.setYRange(float(np.min(finite)), float(np.max(finite)), padding=0.01)

    def set_visible_depth(self, top: float, bottom: float) -> None:
        first = next((entry.plot for entry in self._rendered.values() if entry.plot), None)
        if first is not None:
            first.setYRange(top, bottom, padding=0)

    def _populate_track(self, track: TabletTrackWidget, definition: TrackDefinition) -> None:
        assert self._dataset is not None
        depth = np.asarray(self._dataset.depth, dtype=float)

        if definition.kind == TrackKind.DEPTH:
            track.plot.setLabel("left", "Глубина", units="м")
            track.plot.hideAxis("bottom")
            track.plot.setMouseEnabled(x=False, y=True)
            return

        track.plot.setLabel("bottom", definition.title)
        logarithmic = definition.x_scale is XScale.LOGARITHMIC
        track.plot.setLogMode(x=logarithmic, y=False)
        for mnemonic in definition.curve_mnemonics:
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                continue
            values = np.asarray(curve.values, dtype=float)
            valid = np.isfinite(values) & np.isfinite(depth)
            if logarithmic:
                valid &= values > 0
            if np.any(valid):
                track.plot.plot(values[valid], depth[valid], name=mnemonic)
        if definition.x_min is not None and definition.x_max is not None:
            minimum = definition.x_min
            maximum = definition.x_max
            if logarithmic:
                minimum = float(np.log10(minimum))
                maximum = float(np.log10(maximum))
            track.plot.setXRange(minimum, maximum, padding=0)

    def _on_master_y_range_changed(self, _view_box, ranges) -> None:
        if self._sync_guard:
            return
        self._sync_guard = True
        try:
            y_range = ranges[1]
            self.visible_depth_changed.emit(float(y_range[0]), float(y_range[1]))
        finally:
            self._sync_guard = False
