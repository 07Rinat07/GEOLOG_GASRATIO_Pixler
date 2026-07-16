from __future__ import annotations

from dataclasses import dataclass
from html import escape

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import CanvasObject, CurveData, Dataset, LithologyInterval
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.tablet.lithology_patterns import lithology_brush
from geoworkbench.tablet.lithology_labels import lithology_label_is_visible
from geoworkbench.tablet.models import (
    CurveLineStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)
from geoworkbench.tablet.resize import TrackResizeGesture
from geoworkbench.tablet.sampling import select_visible_samples


@dataclass(slots=True)
class RenderedTrack:
    definition: TrackDefinition
    widget: QWidget
    plot: pg.PlotWidget | None = None
    legend_labels: tuple[str, ...] = ()
    curve_items: dict[str, pg.PlotDataItem] | None = None
    annotation_items: dict[str, pg.InfiniteLine] | None = None
    lithology_items: dict[str, pg.BarGraphItem] | None = None
    lithology_label_items: dict[str, pg.TextItem] | None = None
    lithology_description_items: dict[str, pg.TextItem] | None = None


def curve_legend_label(curve: CurveData) -> str:
    mnemonic = curve.metadata.original_mnemonic
    unit = (curve.metadata.unit or "").strip()
    return f"{mnemonic} [{unit}]" if unit else mnemonic


class TabletTrackWidget(QFrame):
    selected = Signal(str)
    width_change_requested = Signal(str, int)

    RESIZE_MARGIN = 6

    def __init__(self, definition: TrackDefinition) -> None:
        super().__init__()
        self.definition = definition
        self._resize_gesture: TrackResizeGesture | None = None
        self.setObjectName(f"track-{definition.track_id}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(definition.width)
        self.setMaximumWidth(definition.width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.title = QLabel(definition.title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(
            "font-weight: 600; padding: 5px; border-bottom: 1px solid palette(mid);"
        )

        self.plot = pg.PlotWidget()
        self.plot.showGrid(
            x=definition.grid_x,
            y=definition.grid_y,
            alpha=definition.grid_alpha,
        )
        self.plot.getViewBox().invertY(True)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title)
        layout.addWidget(self.plot)

        for target in (self.title, self.plot, self.plot.viewport()):
            target.setMouseTracking(True)
            target.installEventFilter(self)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._handle_resize_event(event):
            return
        self.selected.emit(self.definition.track_id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._handle_resize_event(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._handle_resize_event(event):
            return
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if isinstance(event, QMouseEvent) and self._handle_resize_event(event, watched):
            return True
        return super().eventFilter(watched, event)

    def _handle_resize_event(self, event: QMouseEvent, watched: QObject | None = None) -> bool:
        event_type = event.type()
        global_position = event.globalPosition().toPoint()
        in_resize_zone = self._in_resize_zone(global_position)
        cursor_target = watched if isinstance(watched, QWidget) else self

        if event_type == QEvent.Type.MouseMove and self._resize_gesture is None:
            cursor = Qt.CursorShape.SizeHorCursor if in_resize_zone else Qt.CursorShape.ArrowCursor
            cursor_target.setCursor(cursor)
            return False
        if (
            event_type == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and in_resize_zone
        ):
            self._resize_gesture = TrackResizeGesture(self.width(), global_position.x())
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return True
        if event_type == QEvent.Type.MouseMove and self._resize_gesture is not None:
            width = self._resize_gesture.width_at(global_position.x())
            self.setFixedWidth(width)
            return True
        if (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._resize_gesture is not None
        ):
            width = self._resize_gesture.width_at(global_position.x())
            self._resize_gesture = None
            self.setFixedWidth(width)
            self.unsetCursor()
            if width != self.definition.width:
                self.width_change_requested.emit(self.definition.track_id, width)
            return True
        return self._resize_gesture is not None

    def _in_resize_zone(self, global_position: QPoint) -> bool:
        local_x = self.mapFromGlobal(global_position).x()
        return self.width() - self.RESIZE_MARGIN <= local_x <= self.width() + self.RESIZE_MARGIN


class TabletView(QWidget):
    """Многотрековый планшет с общей синхронизированной шкалой глубины."""

    track_selected = Signal(str)
    track_width_change_requested = Signal(str, int)
    visible_depth_changed = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        pg.setConfigOptions(antialias=False)
        self._dataset: Dataset | None = None
        self._canvas_objects: tuple[CanvasObject, ...] = ()
        self._lithology: tuple[LithologyInterval, ...] = ()
        self._lithotype_catalog: dict[str, CatalogLithotype] = {}
        self._layout_model = TabletLayout()
        self._rendered: dict[str, RenderedTrack] = {}
        self._sync_guard = False
        self._depth_range_guard = False

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

    def legend_labels(self, track_id: str) -> tuple[str, ...]:
        try:
            return self._rendered[track_id].legend_labels
        except KeyError as exc:
            raise KeyError(f"Трек не отрисован: {track_id}") from exc

    def rendered_curve_point_count(self, track_id: str, mnemonic: str) -> int:
        rendered = self._rendered.get(track_id)
        if rendered is None or rendered.curve_items is None or mnemonic not in rendered.curve_items:
            raise KeyError(f"Кривая не отрисована: {track_id}/{mnemonic}")
        x_values, _ = rendered.curve_items[mnemonic].getData()
        return 0 if x_values is None else len(x_values)

    def rendered_annotation_ids(self, track_id: str) -> tuple[str, ...]:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        return tuple((rendered.annotation_items or {}).keys())

    def rendered_lithology_ids(self, track_id: str) -> tuple[str, ...]:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        return tuple((rendered.lithology_items or {}).keys())

    def rendered_lithology_codes(self, track_id: str) -> tuple[str, ...]:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        return tuple(item.toPlainText() for item in (rendered.lithology_label_items or {}).values())

    def rendered_lithology_descriptions(self, track_id: str) -> tuple[str, ...]:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        return tuple(
            item.toPlainText()
            for item in (rendered.lithology_description_items or {}).values()
        )

    def visible_lithology_text_ids(self, track_id: str) -> tuple[str, ...]:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        items = rendered.lithology_label_items or rendered.lithology_description_items or {}
        return tuple(interval_id for interval_id, item in items.items() if item.isVisible())

    @property
    def visible_depth_range(self) -> tuple[float, float] | None:
        first = next((entry.plot for entry in self._rendered.values() if entry.plot), None)
        if first is None:
            return None
        y_range = first.getViewBox().viewRange()[1]
        top, bottom = sorted((float(y_range[0]), float(y_range[1])))
        return top, bottom

    def track_depth_range(self, track_id: str) -> tuple[float, float]:
        rendered = self._rendered.get(track_id)
        if rendered is None or rendered.plot is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        y_range = rendered.plot.getViewBox().viewRange()[1]
        top, bottom = sorted((float(y_range[0]), float(y_range[1])))
        return top, bottom

    def set_dataset(self, dataset: Dataset | None) -> None:
        self._dataset = dataset
        self.refresh_view()

    def set_canvas_objects(self, canvas_objects: list[CanvasObject]) -> None:
        self._canvas_objects = tuple(canvas_objects)
        self.refresh_view()

    def set_lithology(
        self,
        intervals: list[LithologyInterval],
        catalog: tuple[CatalogLithotype, ...],
    ) -> None:
        self._lithology = tuple(intervals)
        self._lithotype_catalog = {item.lithotype_id: item for item in catalog}
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

        depth = np.asarray(self._dataset.depth, dtype=float)
        finite_depth = depth[np.isfinite(depth)]
        visible_top = self._layout_model.visible_depth_top
        visible_bottom = self._layout_model.visible_depth_bottom
        if finite_depth.size and (visible_top is None or visible_bottom is None):
            visible_top = float(np.min(finite_depth))
            visible_bottom = float(np.max(finite_depth))

        master_plot: pg.PlotWidget | None = None
        for definition in visible:
            track = TabletTrackWidget(definition)
            track.selected.connect(self.track_selected)
            track.width_change_requested.connect(self.track_width_change_requested)
            legend_labels, curve_items = self._populate_track(
                track,
                definition,
                visible_top,
                visible_bottom,
            )
            annotation_items = self._populate_annotations(track)
            lithology_items = self._populate_lithology(track, definition)
            lithology_label_items = self._populate_lithology_labels(track, definition)
            lithology_description_items = self._populate_lithology_descriptions(
                track, definition
            )
            if master_plot is None:
                master_plot = track.plot
            track.plot.sigYRangeChanged.connect(self._on_depth_range_changed)
            track.plot.getViewBox().disableAutoRange(axis=pg.ViewBox.YAxis)
            rendered = RenderedTrack(
                definition,
                track,
                track.plot,
                legend_labels,
                curve_items,
                annotation_items,
                lithology_items,
                lithology_label_items,
                lithology_description_items,
            )
            self._rendered[definition.track_id] = rendered
            self._tracks_layout.addWidget(track)

        self._tracks_layout.addStretch(1)
        if master_plot is not None and visible_top is not None and visible_bottom is not None:
            self._synchronize_depth_ranges(visible_top, visible_bottom)
            self._update_lithology_text_visibility(visible_top, visible_bottom)

    def set_visible_depth(self, top: float, bottom: float) -> None:
        first = next((entry.plot for entry in self._rendered.values() if entry.plot), None)
        if first is not None:
            self._depth_range_guard = True
            try:
                for rendered in self._rendered.values():
                    if rendered.plot is not None:
                        rendered.plot.setYRange(top, bottom, padding=0)
                self._update_visible_curve_data(top, bottom)
                self._update_lithology_text_visibility(top, bottom)
            finally:
                self._depth_range_guard = False

    def _populate_track(
        self,
        track: TabletTrackWidget,
        definition: TrackDefinition,
        visible_top: float | None,
        visible_bottom: float | None,
    ) -> tuple[tuple[str, ...], dict[str, pg.PlotDataItem]]:
        assert self._dataset is not None
        depth = np.asarray(self._dataset.depth, dtype=float)

        if definition.kind == TrackKind.DEPTH:
            track.plot.setLabel("left", "Глубина", units="м")
            track.plot.hideAxis("bottom")
            track.plot.setMouseEnabled(x=False, y=True)
            return (), {}

        if definition.kind in (TrackKind.LITHOLOGY, TrackKind.TEXT):
            track.plot.hideAxis("bottom")
            track.plot.setXRange(0.0, 1.0, padding=0)
            track.plot.setMouseEnabled(x=False, y=True)
            return (), {}

        track.plot.setLabel("bottom", definition.title)
        logarithmic = definition.x_scale is XScale.LOGARITHMIC
        track.plot.setLogMode(x=logarithmic, y=False)
        legend_labels: list[str] = []
        curve_items: dict[str, pg.PlotDataItem] = {}
        legend_created = False
        for index, mnemonic in enumerate(definition.curve_mnemonics):
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                continue
            values = np.asarray(curve.values, dtype=float)
            valid = np.isfinite(values) & np.isfinite(depth)
            if logarithmic:
                valid &= values > 0
            if np.any(valid):
                if not legend_created:
                    track.plot.addLegend(offset=(5, 5))
                    legend_created = True
                label = curve_legend_label(curve)
                style = definition.curve_style(mnemonic)
                pen = (
                    pg.mkPen(
                        style.color,
                        width=style.width,
                        style={
                            CurveLineStyle.SOLID: Qt.PenStyle.SolidLine,
                            CurveLineStyle.DASH: Qt.PenStyle.DashLine,
                            CurveLineStyle.DOT: Qt.PenStyle.DotLine,
                            CurveLineStyle.DASH_DOT: Qt.PenStyle.DashDotLine,
                        }[style.line_style],
                    )
                    if style is not None
                    else pg.mkPen(
                        pg.intColor(
                            index, hues=max(1, len(definition.curve_mnemonics))
                        )
                    )
                )
                if visible_top is None or visible_bottom is None:
                    visible_values = np.array([], dtype=np.float64)
                    visible_depth = np.array([], dtype=np.float64)
                else:
                    visible_values, visible_depth = select_visible_samples(
                        depth,
                        values,
                        visible_top,
                        visible_bottom,
                        positive_values_only=logarithmic,
                    )
                item = track.plot.plot(visible_values, visible_depth, pen=pen, name=label)
                curve_items[mnemonic] = item
                legend_labels.append(label)
        if definition.x_min is not None and definition.x_max is not None:
            minimum = definition.x_min
            maximum = definition.x_max
            if logarithmic:
                minimum = float(np.log10(minimum))
                maximum = float(np.log10(maximum))
            track.plot.setXRange(minimum, maximum, padding=0)
        return tuple(legend_labels), curve_items

    def _populate_lithology(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, pg.BarGraphItem]:
        if definition.kind is not TrackKind.LITHOLOGY:
            return {}
        rendered: dict[str, pg.BarGraphItem] = {}
        for interval in self._lithology:
            lithotype = self._lithotype_catalog.get(interval.lithotype_id)
            color = lithotype.color if lithotype is not None else "#b0b0b0"
            pattern = lithotype.pattern_key if lithotype is not None else "solid"
            item = pg.BarGraphItem(
                x=[0.5],
                y=[(interval.top_depth + interval.bottom_depth) / 2.0],
                width=1.0,
                height=interval.bottom_depth - interval.top_depth,
                brush=lithology_brush(color, pattern),
                pen=pg.mkPen("#303030", width=0.7),
            )
            track.plot.addItem(item)
            rendered[interval.interval_id] = item
        return rendered

    def _populate_lithology_descriptions(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, pg.TextItem]:
        if definition.kind is not TrackKind.TEXT:
            return {}
        rendered: dict[str, pg.TextItem] = {}
        text_width = max(80, definition.width - 30)
        for interval in self._lithology:
            lithotype = self._lithotype_catalog.get(interval.lithotype_id)
            fallback = lithotype.name_ru if lithotype is not None else interval.lithotype_id
            description = (interval.description or "").strip() or fallback
            label = pg.TextItem(anchor=(0.0, 0.5))
            label.setHtml(
                f'<div style="width:{text_width}px; color:#202020">'
                f"{escape(description)}</div>"
            )
            label.setPos(0.02, (interval.top_depth + interval.bottom_depth) / 2.0)
            track.plot.addItem(label)
            rendered[interval.interval_id] = label
        return rendered

    def _populate_lithology_labels(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, pg.TextItem]:
        if definition.kind is not TrackKind.LITHOLOGY:
            return {}
        rendered: dict[str, pg.TextItem] = {}
        for interval in self._lithology:
            lithotype = self._lithotype_catalog.get(interval.lithotype_id)
            code = lithotype.code if lithotype is not None else interval.lithotype_id
            label = pg.TextItem(code, color="#202020", anchor=(0.5, 0.5))
            label.setPos(0.5, (interval.top_depth + interval.bottom_depth) / 2.0)
            track.plot.addItem(label)
            rendered[interval.interval_id] = label
        return rendered

    def _populate_annotations(self, track: TabletTrackWidget) -> dict[str, pg.InfiniteLine]:
        rendered: dict[str, pg.InfiniteLine] = {}
        for item in self._canvas_objects:
            if item.object_type != "depth_annotation" or item.anchor_type != "depth":
                continue
            depth = item.top_depth if item.top_depth is not None else item.y
            if not np.isfinite(depth):
                continue
            line = pg.InfiniteLine(
                pos=float(depth),
                angle=0,
                movable=False,
                pen=pg.mkPen("#d97706", width=1, style=Qt.PenStyle.DashLine),
            )
            text = str(item.properties.get("text", "")).strip()
            if text:
                pg.InfLineLabel(
                    line,
                    text=text,
                    position=0.02,
                    rotateAxis=(1, 0),
                    anchor=(0, 1),
                )
            track.plot.addItem(line)
            rendered[item.object_id] = line
        return rendered

    def _update_visible_curve_data(self, top: float, bottom: float) -> None:
        if self._dataset is None:
            return
        depth = np.asarray(self._dataset.depth, dtype=float)
        for rendered in self._rendered.values():
            logarithmic = rendered.definition.x_scale is XScale.LOGARITHMIC
            for mnemonic, item in (rendered.curve_items or {}).items():
                curve = self._dataset.curve_by_mnemonic(mnemonic)
                if curve is None:
                    item.setData([], [])
                    continue
                values, visible_depth = select_visible_samples(
                    depth,
                    np.asarray(curve.values, dtype=float),
                    top,
                    bottom,
                    positive_values_only=logarithmic,
                )
                item.setData(values, visible_depth)

    def _update_lithology_text_visibility(self, top: float, bottom: float) -> None:
        intervals = {item.interval_id: item for item in self._lithology}
        for rendered in self._rendered.values():
            if rendered.plot is None:
                continue
            viewport_height = rendered.plot.viewport().height()
            for items, minimum_pixels in (
                (rendered.lithology_label_items or {}, 16),
                (rendered.lithology_description_items or {}, 34),
            ):
                for interval_id, text_item in items.items():
                    interval = intervals.get(interval_id)
                    visible = interval is not None and lithology_label_is_visible(
                        interval.top_depth,
                        interval.bottom_depth,
                        top,
                        bottom,
                        viewport_height,
                        minimum_pixels=minimum_pixels,
                    )
                    text_item.setVisible(visible)

    def _synchronize_depth_ranges(self, top: float, bottom: float) -> None:
        self._depth_range_guard = True
        try:
            for rendered in self._rendered.values():
                if rendered.plot is not None:
                    rendered.plot.setYRange(top, bottom, padding=0)
        finally:
            self._depth_range_guard = False

    def _on_depth_range_changed(self, _view_box, y_range) -> None:
        if self._sync_guard or self._depth_range_guard:
            return
        self._sync_guard = True
        try:
            top, bottom = sorted((float(y_range[0]), float(y_range[1])))
            self._update_visible_curve_data(top, bottom)
            self._synchronize_depth_ranges(top, bottom)
            self._update_lithology_text_visibility(top, bottom)
            self.visible_depth_changed.emit(top, bottom)
        finally:
            self._sync_guard = False
