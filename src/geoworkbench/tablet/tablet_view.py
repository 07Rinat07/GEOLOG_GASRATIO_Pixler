from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import cast

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QBrush, QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import (
    CanvasObject,
    CurveData,
    CuttingsSample,
    Dataset,
    DatasetIndex,
    IndexRole,
    IndexType,
    LithologyInterval,
    StratigraphyInterval,
    WellInterpretation,
)
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.project.stratigraphy_controller import stratigraphy_rank_order
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.camera import TabletCamera
from geoworkbench.tablet.geometry_cache import CurveGeometryCache, CurveGeometryKey, GeometryCacheStats
from geoworkbench.tablet.render_invalidation import DirtyReason, DirtyRenderStats, TrackDirtyRegistry
from geoworkbench.tablet.static_layer_cache import StaticLayerCache, StaticLayerCacheStats, StaticLayerKey
from geoworkbench.tablet.overlay_layers import (
    OverlayLayerKind,
    OverlayLayerManager,
    OverlayLayerStats,
)
from geoworkbench.tablet.interval_interaction import (
    IntervalDragResult,
    IntervalEditMode,
    choose_resize_edge,
    normalize_drag_range,
    resize_interval_range,
    snap_depth_to_samples,
)
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
from geoworkbench.tablet.selection_interaction import (
    CommandStack,
    SelectableKind,
    SelectionManager,
    SelectionRef,
    SelectionSnapshot,
)


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
    cuttings_items: dict[str, tuple[pg.BarGraphItem, ...]] | None = None
    analysis_items: dict[str, tuple[object, ...]] | None = None
    stratigraphy_items: dict[str, tuple[object, ...]] | None = None
    interpretation_items: dict[str, tuple[object, ...]] | None = None
    interpretation_lanes: dict[str, int] | None = None
    cursor_line: pg.InfiniteLine | None = None
    interpretation_preview: pg.BarGraphItem | None = None
    selection_highlight: pg.BarGraphItem | None = None
    curve_render_keys: dict[str, CurveGeometryKey] | None = None


@dataclass(slots=True)
class _IntervalGesture:
    track_id: str
    interpretation_id: str
    mode: IntervalEditMode
    lane: int
    interval_type: str
    start_depth: float
    current_depth: float
    interval_id: str | None = None
    edge: str | None = None
    original_top: float | None = None
    original_bottom: float | None = None


def curve_legend_label(curve: CurveData) -> str:
    mnemonic = curve.metadata.original_mnemonic
    unit = (curve.metadata.unit or "").strip()
    return f"{mnemonic} [{unit}]" if unit else mnemonic


@dataclass(frozen=True, slots=True)
class VerticalAxisDescriptor:
    index_id: str
    label: str
    unit: str
    role: IndexRole
    index_type: IndexType

    @property
    def is_datetime(self) -> bool:
        return self.index_type is IndexType.DATETIME

    @property
    def is_time(self) -> bool:
        return self.role is IndexRole.TIME


class TabletVerticalAxisItem(pg.AxisItem):
    """Readable vertical labels for depth, relative time and absolute timestamps."""

    def __init__(self, descriptor: VerticalAxisDescriptor) -> None:
        super().__init__(orientation="left")
        self.descriptor = descriptor

    def tickStrings(self, values, scale, spacing):  # type: ignore[override]
        if self.descriptor.is_datetime:
            return [self._format_datetime(float(value), float(spacing)) for value in values]
        if self.descriptor.is_time:
            return [self._format_relative_time(float(value)) for value in values]
        return [f"{float(value):g}" for value in values]

    @staticmethod
    def _format_datetime(value: float, spacing: float) -> str:
        if not np.isfinite(value):
            return ""
        try:
            moment = datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return ""
        absolute_spacing = abs(spacing)
        if absolute_spacing >= 86_400:
            return moment.strftime("%d.%m.%Y")
        if absolute_spacing >= 60:
            return moment.strftime("%d.%m %H:%M")
        return moment.strftime("%H:%M:%S")

    def _format_relative_time(self, value: float) -> str:
        if not np.isfinite(value):
            return ""
        unit = self.descriptor.unit.casefold()
        seconds = value
        if unit in {"ms", "msec", "millisecond", "milliseconds"}:
            seconds = value / 1_000.0
        elif unit in {"min", "minute", "minutes", "мин"}:
            seconds = value * 60.0
        elif unit in {"h", "hr", "hour", "hours", "ч"}:
            seconds = value * 3_600.0
        sign = "-" if seconds < 0 else ""
        seconds = abs(seconds)
        if seconds >= 3_600:
            hours = int(seconds // 3_600)
            minutes = int((seconds % 3_600) // 60)
            return f"{sign}{hours:d}:{minutes:02d}"
        if seconds >= 60:
            minutes = int(seconds // 60)
            remain = int(seconds % 60)
            return f"{sign}{minutes:d}:{remain:02d}"
        return f"{value:g}"


class TabletTrackWidget(QFrame):
    selected = Signal(str)
    width_change_requested = Signal(str, int)

    RESIZE_MARGIN = 6

    def __init__(
        self,
        definition: TrackDefinition,
        navigation_hint: str = "",
        vertical_axis: VerticalAxisDescriptor | None = None,
    ) -> None:
        super().__init__()
        self.definition = definition
        self._resize_gesture: TrackResizeGesture | None = None
        self.setObjectName(f"track-{definition.track_id}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #ffffff; border: 1px solid #cbd5e1; } "
            "QLabel { background: #f8fafc; color: #0f172a; }"
        )
        display_width = definition.width
        if definition.kind is TrackKind.DEPTH and vertical_axis is not None:
            if vertical_axis.is_datetime:
                display_width = max(display_width, 210)
            elif vertical_axis.is_time:
                display_width = max(display_width, 150)
        self.setMinimumWidth(display_width)
        self.setMaximumWidth(display_width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.title = QLabel(definition.title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(
            "font-weight: 600; padding: 6px; "
            "background: #f8fafc; color: #0f172a; "
            "border-bottom: 1px solid #cbd5e1;"
        )

        axis_items = (
            {"left": TabletVerticalAxisItem(vertical_axis)} if vertical_axis is not None else None
        )
        self.plot = pg.PlotWidget(axisItems=axis_items)
        self.plot.setBackground("#ffffff")
        for axis_name in ("left", "bottom"):
            axis = self.plot.getAxis(axis_name)
            axis.setPen(pg.mkPen("#475569"))
            axis.setTextPen(pg.mkPen("#334155"))
        self.plot.showGrid(
            x=definition.grid_x,
            y=definition.grid_y,
            alpha=definition.grid_alpha,
        )
        self.plot.setLabel("bottom", definition.x_axis_label)
        self.plot.getAxis("left").enableAutoSIPrefix(False)
        self.plot.hideAxis("left")
        self.plot.getViewBox().invertY(True)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.setToolTip(navigation_hint)
        self.plot.viewport().setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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




class TabletMiniMap(QWidget):
    """Compact full-domain navigator with draggable visible-window indicator."""

    range_requested = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(34)
        self.setMinimumHeight(120)
        self._domain = (0.0, 1.0)
        self._visible = (0.0, 1.0)
        self._drag_offset = 0.0
        self._dragging = False

    def set_ranges(self, domain: tuple[float, float], visible: tuple[float, float]) -> None:
        self._domain = domain
        self._visible = visible
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self.rect().adjusted(8, 6, -8, -6)
        painter.fillRect(rect, QBrush(Qt.GlobalColor.white))
        painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))
        painter.drawRect(rect)
        top, bottom = self._domain
        vtop, vbottom = self._visible
        span = max(bottom - top, 1e-12)
        y1 = rect.top() + int((vtop - top) / span * rect.height())
        y2 = rect.top() + int((vbottom - top) / span * rect.height())
        y1, y2 = sorted((max(rect.top(), y1), min(rect.bottom(), y2)))
        if y2 - y1 < 8:
            y2 = min(rect.bottom(), y1 + 8)
        window = rect.adjusted(2, 0, -2, 0)
        window.setTop(y1)
        window.setBottom(y2)
        painter.fillRect(window, QBrush(Qt.GlobalColor.lightGray))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRect(window)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        value = self._value_at(event.position().y())
        vtop, vbottom = self._visible
        if vtop <= value <= vbottom:
            self._drag_offset = value - vtop
        else:
            self._drag_offset = (vbottom - vtop) / 2.0
            self._emit_centered(value)
        self._dragging = True

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            value = self._value_at(event.position().y())
            span = self._visible[1] - self._visible[0]
            self.range_requested.emit(value - self._drag_offset, value - self._drag_offset + span)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def _emit_centered(self, value: float) -> None:
        span = self._visible[1] - self._visible[0]
        self.range_requested.emit(value - span / 2.0, value + span / 2.0)

    def _value_at(self, y: float) -> float:
        rect = self.rect().adjusted(8, 6, -8, -6)
        fraction = (float(y) - rect.top()) / max(rect.height(), 1)
        fraction = max(0.0, min(1.0, fraction))
        return self._domain[0] + fraction * (self._domain[1] - self._domain[0])


class TabletView(QWidget):
    """Многотрековый планшет с общей синхронизированной шкалой глубины."""

    track_selected = Signal(str)
    selection_changed = Signal(object)
    track_width_change_requested = Signal(str, int)
    visible_depth_changed = Signal(float, float)
    vertical_index_changed = Signal(str)
    cursor_changed = Signal(float, str)
    interpretation_selected = Signal(str)
    interval_selected = Signal(str, str)
    interval_selection_cleared = Signal()
    interval_create_requested = Signal(str, float, float, str)
    interval_resize_requested = Signal(str, str, float, float)
    interval_interaction_cancelled = Signal()

    def __init__(self, *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__()
        pg.setConfigOptions(antialias=False)
        self._localizer = Localizer.create(language)
        self._navigation_hint = self._localizer.text("tablet.depth_navigation_hint")
        self._dataset: Dataset | None = None
        self._canvas_objects: tuple[CanvasObject, ...] = ()
        self._lithology: tuple[LithologyInterval, ...] = ()
        self._cuttings: tuple[CuttingsSample, ...] = ()
        self._stratigraphy: tuple[StratigraphyInterval, ...] = ()
        self._interpretations: tuple[WellInterpretation, ...] = ()
        self._selected_interpretation_id: str | None = None
        self._selected_interval_id: str | None = None
        self._lithotype_catalog: dict[str, CatalogLithotype] = {}
        self._layout_model = TabletLayout()
        self._rendered: dict[str, RenderedTrack] = {}
        self._sync_guard = False
        self._depth_range_guard = False
        self._cursor_enabled = False
        self._cursor_depth: float | None = None
        self._cursor_guard = False
        self._cursor_color = "#dc2626"
        self._cursor_width = 2.0
        self._depth_viewports: dict[QObject, pg.PlotWidget] = {}
        self._interpretation_viewports: dict[QObject, RenderedTrack] = {}
        self._interval_edit_mode = IntervalEditMode.SELECT
        self._interval_creation_type = self._localizer.text("interpretations.default_type")
        self._interval_gesture: _IntervalGesture | None = None
        self._axis_combo_guard = False
        self._scrollbar_guard = False
        self._camera = TabletCamera()
        self._pan_viewport: QObject | None = None
        self._pan_last_position: QPointF | None = None
        self._space_pressed = False
        self._geometry_cache = CurveGeometryCache(max_entries=512)
        self._static_layer_cache = StaticLayerCache(max_entries=512)
        self._dirty_registry = TrackDirtyRegistry()
        self._overlay_layers = OverlayLayerManager()
        self._selection = SelectionManager()
        self._interaction_history = CommandStack()
        self._tooltip_items: dict[str, pg.TextItem] = {}
        self._rubber_band_items: dict[str, pg.BarGraphItem] = {}

        self._pinned_container = QWidget()
        self._pinned_layout = QHBoxLayout(self._pinned_container)
        self._pinned_layout.setContentsMargins(0, 0, 0, 0)
        self._pinned_layout.setSpacing(2)

        self._container = QWidget()
        self._tracks_layout = QHBoxLayout(self._container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(2)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setWidget(self._container)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._axis_combo = QComboBox()
        self._axis_combo.setMinimumWidth(220)
        self._axis_combo.currentIndexChanged.connect(self._axis_combo_changed)
        self._range_label = QLabel("—")
        self._range_label.setMinimumWidth(220)
        self._goto_value = QLineEdit()
        self._goto_value.setMaximumWidth(190)
        self._goto_value.returnPressed.connect(self._go_to_axis_value)
        self._goto_button = QPushButton(self._localizer.text("tablet.goto"))
        self._goto_button.clicked.connect(self._go_to_axis_value)
        self._zoom_in_button = QToolButton()
        self._zoom_in_button.setText("+")
        self._zoom_in_button.setToolTip(self._localizer.text("tablet.zoom_in"))
        self._zoom_in_button.clicked.connect(lambda: self.zoom_depth(0.8))
        self._zoom_out_button = QToolButton()
        self._zoom_out_button.setText("−")
        self._zoom_out_button.setToolTip(self._localizer.text("tablet.zoom_out"))
        self._zoom_out_button.clicked.connect(lambda: self.zoom_depth(1.25))
        self._full_range_button = QPushButton(self._localizer.text("tablet.full_range"))
        self._full_range_button.clicked.connect(self.show_full_vertical_range)

        navigation = QHBoxLayout()
        navigation.setContentsMargins(6, 4, 6, 4)
        navigation.addWidget(QLabel(self._localizer.text("tablet.vertical_axis")))
        navigation.addWidget(self._axis_combo)
        navigation.addWidget(self._range_label, 1)
        navigation.addWidget(self._goto_value)
        navigation.addWidget(self._goto_button)
        navigation.addWidget(self._zoom_in_button)
        navigation.addWidget(self._zoom_out_button)
        navigation.addWidget(self._full_range_button)

        self._vertical_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self._vertical_scrollbar.setRange(0, 0)
        self._vertical_scrollbar.valueChanged.connect(self._vertical_scrollbar_changed)
        self._mini_map = TabletMiniMap()
        self._mini_map.range_requested.connect(
            lambda top, bottom: self._apply_visible_depth(top, bottom, emit_change=True)
        )
        charts = QHBoxLayout()
        charts.setContentsMargins(0, 0, 0, 0)
        charts.setSpacing(0)
        charts.addWidget(self._pinned_container, 0)
        charts.addWidget(self._scroll, 1)
        charts.addWidget(self._mini_map, 0)
        charts.addWidget(self._vertical_scrollbar)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(navigation)
        root.addLayout(charts, 1)

    @property
    def layout_model(self) -> TabletLayout:
        return self._layout_model

    @property
    def vertical_index_id(self) -> str | None:
        index = self._vertical_index()
        return index.index_id if index is not None else None

    @property
    def vertical_axis_is_time(self) -> bool:
        index = self._vertical_index()
        return index is not None and index.role is IndexRole.TIME

    def geometry_cache_stats(self) -> GeometryCacheStats:
        return self._geometry_cache.stats()

    def static_layer_cache_stats(self) -> StaticLayerCacheStats:
        return self._static_layer_cache.stats()

    def dirty_render_stats(self) -> DirtyRenderStats:
        return self._dirty_registry.stats()

    def overlay_layer_stats(self) -> OverlayLayerStats:
        return self._overlay_layers.stats()

    def overlay_dirty_layers(self) -> tuple[OverlayLayerKind, ...]:
        return self._overlay_layers.dirty_layers()

    def set_overlay_visible(self, kind: OverlayLayerKind, visible: bool) -> bool:
        return self._overlay_layers.set_visible(kind, visible)

    def overlay_visible(self, kind: OverlayLayerKind) -> bool:
        return self._overlay_layers.is_visible(kind)

    def set_overlay_z_value(self, kind: OverlayLayerKind, z_value: float) -> bool:
        return self._overlay_layers.set_z_value(kind, z_value)

    def invalidate_track(self, track_id: str, reason: DirtyReason) -> None:
        if track_id not in self._rendered:
            return
        self._dirty_registry.mark(track_id, reason)
        if reason & (DirtyReason.DATA | DirtyReason.LAYOUT):
            rendered = self._rendered[track_id]
            for mnemonic in (rendered.curve_items or {}):
                self._geometry_cache.invalidate_curve(mnemonic)
        if reason & (DirtyReason.STATIC | DirtyReason.LAYOUT):
            self._static_layer_cache.invalidate_track(track_id)

    def refresh_dirty_tracks(self) -> int:
        dirty = self._dirty_registry.consume()
        updated = 0
        for track_id, reasons in dirty.items():
            rendered = self._rendered.get(track_id)
            if rendered is None:
                continue
            if reasons & DirtyReason.LAYOUT:
                # Topology/order changes still require a complete rebuild.
                self.refresh_view()
                return len(self._rendered)
            self._refresh_rendered_track(rendered, reasons)
            updated += 1
        self._dirty_registry.record_partial_update(updated)
        return updated

    def refresh_track(self, track_id: str, reason: DirtyReason) -> bool:
        if track_id not in self._rendered:
            return False
        self.invalidate_track(track_id, reason)
        return self.refresh_dirty_tracks() == 1

    def available_vertical_indexes(self) -> tuple[str, ...]:
        if self._dataset is None:
            return ()
        return tuple(
            index.index_id
            for index in self._dataset.indexes.values()
            if index.role in {IndexRole.DEPTH, IndexRole.TIME}
            and np.count_nonzero(np.isfinite(self._index_numeric_values(index))) >= 2
        )

    def set_vertical_index(self, index_id: str, *, emit_signal: bool = False) -> bool:
        if self._dataset is None or index_id not in self._dataset.indexes:
            return False
        index = self._dataset.indexes[index_id]
        if index.role not in {IndexRole.DEPTH, IndexRole.TIME}:
            return False
        changed = self._layout_model.set_vertical_index(index_id)
        if not changed:
            return False
        self._cursor_depth = None
        self.refresh_view()
        if emit_signal:
            self.vertical_index_changed.emit(index_id)
        return True

    def format_vertical_value(self, value: float) -> str:
        return self._format_axis_value(value)

    def show_full_vertical_range(self) -> bool:
        bounds = self._axis_bounds()
        if bounds is None:
            return False
        return self._apply_visible_depth(*bounds, emit_change=True)

    def go_to_vertical_value(self, value: float) -> bool:
        bounds = self._axis_bounds()
        current = self.visible_depth_range
        if bounds is None or not np.isfinite(value):
            return False
        data_top, data_bottom = bounds
        bounded = min(max(float(value), data_top), data_bottom)
        data_span = data_bottom - data_top
        if current is None or current[1] - current[0] >= data_span * 0.999999:
            span = max(data_span * 0.2, data_span / 100_000.0)
        else:
            span = current[1] - current[0]
        return self._apply_visible_depth(
            bounded - span / 2.0, bounded + span / 2.0, emit_change=True
        )

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
            item.toPlainText() for item in (rendered.lithology_description_items or {}).values()
        )

    def visible_lithology_text_ids(self, track_id: str) -> tuple[str, ...]:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        items = rendered.lithology_label_items or rendered.lithology_description_items or {}
        return tuple(interval_id for interval_id, item in items.items() if item.isVisible())


    @property
    def interval_edit_mode(self) -> IntervalEditMode:
        return self._interval_edit_mode

    @property
    def interval_preview_range(self) -> tuple[float, float] | None:
        preview = self._gesture_result()
        if preview is None:
            return None
        return preview.top_depth, preview.bottom_depth

    def set_interval_edit_mode(self, mode: IntervalEditMode | str) -> None:
        requested = IntervalEditMode(mode)
        if requested is self._interval_edit_mode:
            return
        self.cancel_interval_interaction()
        self._interval_edit_mode = requested
        for rendered in self._rendered.values():
            if rendered.definition.kind is TrackKind.INTERPRETATION and rendered.plot is not None:
                cursor = (
                    Qt.CursorShape.CrossCursor
                    if requested is IntervalEditMode.CREATE
                    else Qt.CursorShape.SizeVerCursor
                    if requested is IntervalEditMode.RESIZE
                    else Qt.CursorShape.ArrowCursor
                )
                rendered.plot.viewport().setCursor(cursor)

    def set_interval_creation_type(self, interval_type: str) -> None:
        normalized = interval_type.strip()
        if normalized:
            self._interval_creation_type = normalized

    @property
    def selected_interpretation_id(self) -> str | None:
        return self._selected_interpretation_id

    @property
    def selected_interval_id(self) -> str | None:
        return self._selected_interval_id

    def rendered_interpretation_ids(self, track_id: str) -> tuple[str, ...]:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        return tuple((rendered.interpretation_items or {}).keys())

    def set_interpretations(
        self,
        interpretations: list[WellInterpretation],
        selected_interpretation_id: str | None = None,
    ) -> None:
        self._interpretations = tuple(interpretations)
        available_ids = {item.interpretation_id for item in self._interpretations}
        requested = selected_interpretation_id or self._selected_interpretation_id
        if requested not in available_ids:
            requested = self._interpretations[0].interpretation_id if self._interpretations else None
        self._selected_interpretation_id = requested
        current = self._current_interpretation()
        if current is None or not any(
            item.interval_id == self._selected_interval_id for item in current.intervals
        ):
            self._selected_interval_id = None
        self.refresh_view()

    def set_selected_interpretation(
        self, interpretation_id: str | None, *, emit_signal: bool = False
    ) -> bool:
        if interpretation_id is not None and not any(
            item.interpretation_id == interpretation_id for item in self._interpretations
        ):
            return False
        changed = self._selected_interpretation_id != interpretation_id
        self._selected_interpretation_id = interpretation_id
        current = self._current_interpretation()
        if current is None or not any(
            item.interval_id == self._selected_interval_id for item in current.intervals
        ):
            self._selected_interval_id = None
        if changed:
            self.refresh_view()
            if emit_signal and interpretation_id is not None:
                self.interpretation_selected.emit(interpretation_id)
        return changed

    def set_selected_interval(
        self,
        interpretation_id: str,
        interval_id: str,
        *,
        emit_signal: bool = False,
    ) -> bool:
        interpretation = next(
            (item for item in self._interpretations if item.interpretation_id == interpretation_id),
            None,
        )
        if interpretation is None or not any(
            item.interval_id == interval_id for item in interpretation.intervals
        ):
            return False
        interpretation_changed = self._selected_interpretation_id != interpretation_id
        interval_changed = self._selected_interval_id != interval_id
        self._selected_interpretation_id = interpretation_id
        self._selected_interval_id = interval_id
        generic_changed = self._selection.select(
            SelectionRef(SelectableKind.INTERVAL, interval_id),
            additive=False,
        )
        if generic_changed:
            self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
            self.selection_changed.emit(self._selection.snapshot())
        if interpretation_changed:
            self.refresh_view()
        else:
            self._apply_interpretation_selection_style()
        if emit_signal and (interpretation_changed or interval_changed):
            self.interval_selected.emit(interpretation_id, interval_id)
        return interpretation_changed or interval_changed

    def clear_interval_selection(self, *, emit_signal: bool = False) -> bool:
        if self._selected_interval_id is None:
            return False
        self._selected_interval_id = None
        self._selection.clear(kind=SelectableKind.INTERVAL)
        self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
        self.selection_changed.emit(self._selection.snapshot())
        self._apply_interpretation_selection_style()
        if emit_signal:
            self.interval_selection_cleared.emit()
        return True

    def _current_interpretation(self) -> WellInterpretation | None:
        return next(
            (
                item
                for item in self._interpretations
                if item.interpretation_id == self._selected_interpretation_id
            ),
            None,
        )

    @property
    def selection_snapshot(self) -> SelectionSnapshot:
        return self._selection.snapshot()

    def select_track(
        self,
        track_id: str,
        *,
        additive: bool = False,
        toggle: bool = False,
        emit_signal: bool = True,
    ) -> bool:
        if track_id not in {track.track_id for track in self._layout_model.tracks}:
            return False
        changed = self._selection.select(
            SelectionRef(SelectableKind.TRACK, track_id, track_id),
            additive=additive,
            toggle=toggle,
        )
        if changed:
            self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
            self._apply_track_selection_style()
            if emit_signal:
                self.selection_changed.emit(self._selection.snapshot())
                self.track_selected.emit(track_id)
        return changed

    def clear_selection(self, *, emit_signal: bool = True) -> bool:
        changed = self._selection.clear()
        interval_changed = self._selected_interval_id is not None
        self._selected_interval_id = None
        if changed or interval_changed:
            self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
            self._apply_track_selection_style()
            self._apply_interpretation_selection_style()
            if emit_signal:
                self.selection_changed.emit(self._selection.snapshot())
        return changed or interval_changed

    def _track_selected_from_widget(self, track_id: str) -> None:
        self.select_track(track_id, emit_signal=True)

    def _apply_track_selection_style(self) -> None:
        selected = {
            item.object_id
            for item in self._selection.snapshot().items
            if item.kind is SelectableKind.TRACK
        }
        for track_id, rendered in self._rendered.items():
            frame = rendered.widget
            if track_id in selected:
                frame.setStyleSheet(
                    "QFrame { background: #ffffff; border: 2px solid #2563eb; } "
                    "QLabel { background: #eff6ff; color: #0f172a; }"
                )
            else:
                frame.setStyleSheet(
                    "QFrame { background: #ffffff; border: 1px solid #cbd5e1; } "
                    "QLabel { background: #f8fafc; color: #0f172a; }"
                )

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
        self._geometry_cache.clear()
        self._static_layer_cache.clear()
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

    def set_cuttings(self, samples: list[CuttingsSample]) -> None:
        self._cuttings = tuple(samples)
        self.refresh_view()

    def set_stratigraphy(self, intervals: list[StratigraphyInterval]) -> None:
        self._stratigraphy = tuple(intervals)
        self.refresh_view()

    def set_layout_model(self, layout_model: TabletLayout) -> None:
        self._layout_model = layout_model
        self._cursor_depth = layout_model.cursor_depth
        self.refresh_view()
        if self._cursor_depth is not None and self._dataset is not None:
            self.set_cursor_depth(self._cursor_depth)

    @property
    def cursor_depth(self) -> float | None:
        return self._cursor_depth

    def set_cursor_enabled(self, enabled: bool) -> None:
        self._cursor_enabled = enabled
        self._overlay_layers.set_visible(OverlayLayerKind.CURSOR, enabled)
        for rendered in self._rendered.values():
            if rendered.cursor_line is not None:
                rendered.cursor_line.setVisible(enabled)
        if enabled and self._cursor_depth is None:
            depth_range = self.visible_depth_range
            if depth_range is not None:
                self.set_cursor_depth(sum(depth_range) / 2.0)

    def set_cursor_depth(self, depth: float) -> None:
        if self._dataset is None or not np.isfinite(depth):
            return
        finite = self._axis_values()
        finite = finite[np.isfinite(finite)]
        if not finite.size:
            return
        bounded = min(max(float(depth), float(np.min(finite))), float(np.max(finite)))
        self._cursor_depth = bounded
        self._overlay_layers.mark_dirty(OverlayLayerKind.CURSOR)
        self._cursor_guard = True
        try:
            for rendered in self._rendered.values():
                if rendered.cursor_line is not None:
                    rendered.cursor_line.setPos(bounded)
                    rendered.cursor_line.setVisible(self._cursor_enabled)
        finally:
            self._cursor_guard = False
        self.cursor_changed.emit(bounded, self.cursor_summary(bounded))

    def set_cursor_style(self, color: str, width: float) -> None:
        if not pg.mkColor(color).isValid():
            raise ValueError("Некорректный цвет визирной линии")
        if not np.isfinite(width) or not 0.5 <= width <= 10.0:
            raise ValueError("Толщина визирной линии должна быть от 0.5 до 10 px")
        self._cursor_color = color
        self._cursor_width = float(width)
        for rendered in self._rendered.values():
            if rendered.cursor_line is not None:
                rendered.cursor_line.setPen(pg.mkPen(self._cursor_color, width=self._cursor_width))

    def cursor_summary(self, depth: float) -> str:
        if self._dataset is None:
            return ""
        axis_values = self._axis_values()
        valid_axis = np.flatnonzero(np.isfinite(axis_values))
        if not valid_axis.size:
            return ""
        index = int(valid_axis[np.argmin(np.abs(axis_values[valid_axis] - depth))])
        depths = np.asarray(self._dataset.depth, dtype=float)
        sample_depth = float(depths[index])
        values = [f"Глубина: {sample_depth:g} м"]
        descriptor = self._axis_descriptor()
        if descriptor is not None and descriptor.is_time:
            values.insert(0, f"Время: {self._format_axis_value(float(axis_values[index]))}")
        interval = next(
            (
                item
                for item in self._lithology
                if item.top_depth <= sample_depth <= item.bottom_depth
            ),
            None,
        )
        if interval is not None:
            lithotype = self._lithotype_catalog.get(interval.lithotype_id)
            rock = lithotype.name_ru if lithotype is not None else interval.lithotype_id
            interval_text = (
                f"Литология: {rock} ({interval.top_depth:g}–{interval.bottom_depth:g} м)"
            )
            if interval.description:
                interval_text += f" — {interval.description}"
            values.append(interval_text)
        active_stratigraphy = sorted(
            (
                item
                for item in self._stratigraphy
                if item.top_depth <= sample_depth <= item.bottom_depth
            ),
            key=lambda item: (stratigraphy_rank_order(item.rank), item.top_depth),
        )
        for stratigraphy in active_stratigraphy:
            label = " / ".join(
                value
                for value in (stratigraphy.rank, stratigraphy.code, stratigraphy.name)
                if value
            )
            values.append(
                f"Стратиграфия: {label} "
                f"({stratigraphy.top_depth:g}–{stratigraphy.bottom_depth:g} м)"
                + (f" — {stratigraphy.description}" if stratigraphy.description else "")
            )
        interpretation = self._current_interpretation()
        if interpretation is not None:
            for interpretation_interval in interpretation.intervals:
                if (
                    interpretation_interval.top_depth
                    <= sample_depth
                    <= interpretation_interval.bottom_depth
                ):
                    interval_text = (
                        f"Интерпретация «{interpretation.name}»: "
                        f"{interpretation_interval.interval_type} / "
                        f"{interpretation_interval.label} "
                        f"({interpretation_interval.top_depth:g}–"
                        f"{interpretation_interval.bottom_depth:g} м)"
                    )
                    if interpretation_interval.comment:
                        interval_text += f" — {interpretation_interval.comment}"
                    values.append(interval_text)
        sample = next(
            (
                item
                for item in self._cuttings
                if item.top_depth <= sample_depth <= item.bottom_depth
            ),
            None,
        )
        if sample is not None:
            parts = []
            for component in sample.components:
                lithotype = self._lithotype_catalog.get(component.lithotype_id)
                name = lithotype.name_ru if lithotype is not None else component.lithotype_id
                parts.append(f"{name}: {component.percentage:g}%")
            if parts:
                values.append(
                    f"Шлам {sample.top_depth:g}–{sample.bottom_depth:g} м: " + "; ".join(parts)
                )
            if sample.calcite_percent is not None or sample.dolomite_percent is not None:
                residue = sample.insoluble_residue_percent
                values.append(
                    "Кальциметрия: "
                    f"CaCO₃ {sample.calcite_percent or 0.0:g}%; "
                    f"CaMg(CO₃)₂ {sample.dolomite_percent or 0.0:g}%"
                    + (f"; нераств. остаток {residue:g}%" if residue is not None else "")
                )
            lba = [
                f"G={sample.lba_group}" if sample.lba_group is not None else None,
                sample.lba_type_id,
                f"I={sample.lba_intensity}" if sample.lba_intensity is not None else None,
                sample.lba_color,
                sample.lba_distribution,
                sample.lba_cut,
                sample.lba_cut_speed,
                sample.lba_cut_color,
                sample.lba_residue_type,
                sample.lba_residue_color,
                sample.lba_odour,
                sample.lba_stain,
                sample.lba_description,
            ]
            if any(lba):
                values.append("ЛБА: " + "; ".join(value for value in lba if value))
            if sample.analysis_interpretation:
                values.append("Интерпретация геолога: " + sample.analysis_interpretation)
        seen: set[str] = set()
        for definition in self._layout_model.visible_tracks():
            for mnemonic in definition.curve_mnemonics:
                if mnemonic in seen:
                    continue
                curve = self._dataset.curve_by_mnemonic(mnemonic)
                if curve is None or index >= curve.values.size:
                    continue
                value = float(curve.values[index])
                if not np.isfinite(value):
                    continue
                unit = (curve.metadata.unit or "").strip()
                values.append(f"{mnemonic}: {value:g}{f' {unit}' if unit else ''}")
                seen.add(mnemonic)
        return " | ".join(values)

    def add_track(self, definition: TrackDefinition) -> None:
        self._layout_model.add_track(definition)
        self.refresh_view()

    def remove_track(self, track_id: str) -> None:
        self._layout_model.remove_track(track_id)
        self.refresh_view()

    def clear(self) -> None:
        self.cancel_interval_interaction(emit_signal=False)
        self._dirty_registry.clear()
        self._overlay_layers.clear()
        self._tooltip_items.clear()
        self._rubber_band_items.clear()
        self._depth_viewports.clear()
        self._interpretation_viewports.clear()
        for layout in (self._pinned_layout, self._tracks_layout):
            while layout.count():
                item = layout.takeAt(0)
                if item is None:
                    continue
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._rendered.clear()

    def refresh_view(self) -> None:
        self.clear()
        self._dirty_registry.record_full_update()
        self._refresh_axis_selector()
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

        depth = self._axis_values()
        finite_depth = depth[np.isfinite(depth)]
        visible_top = self._layout_model.visible_depth_top
        visible_bottom = self._layout_model.visible_depth_bottom
        if finite_depth.size and (visible_top is None or visible_bottom is None):
            visible_top = float(np.min(finite_depth))
            visible_bottom = float(np.max(finite_depth))
        elif visible_top is not None and visible_bottom is not None:
            visible_top, visible_bottom = self._normalize_depth_window(
                visible_top, visible_bottom
            )
            self._layout_model.set_visible_depth(visible_top, visible_bottom)

        master_plot: pg.PlotWidget | None = None
        axis_descriptor = self._axis_descriptor()
        for definition in visible:
            track = TabletTrackWidget(definition, self._navigation_hint, axis_descriptor)
            track.selected.connect(self._track_selected_from_widget)
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
            lithology_description_items = self._populate_lithology_descriptions(track, definition)
            cuttings_items = self._populate_cuttings(track, definition)
            analysis_items = self._populate_sample_analysis(track, definition)
            stratigraphy_items = self._populate_stratigraphy(track, definition)
            interpretation_items, interpretation_lanes = self._populate_interpretation(
                track, definition
            )
            if master_plot is None:
                master_plot = track.plot
            view_box = track.plot.getViewBox()
            view_box.disableAutoRange(axis=pg.ViewBox.YAxis)
            self._apply_depth_limits(view_box)
            track.plot.sigYRangeChanged.connect(self._on_depth_range_changed)
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
                cuttings_items,
                analysis_items,
                stratigraphy_items,
                interpretation_items,
                interpretation_lanes,
                curve_render_keys={},
            )
            self._rendered[definition.track_id] = rendered
            self._register_track_overlays(rendered)
            self._install_cursor(rendered)
            if definition.kind is TrackKind.INTERPRETATION:
                track.plot.scene().sigMouseClicked.connect(
                    lambda event, entry=rendered: self._interpretation_plot_clicked(entry, event)
                )
            viewport = track.plot.viewport()
            viewport.installEventFilter(self)
            self._depth_viewports[viewport] = track.plot
            if definition.kind is TrackKind.INTERPRETATION:
                self._interpretation_viewports[viewport] = rendered
                cursor = (
                    Qt.CursorShape.CrossCursor
                    if self._interval_edit_mode is IntervalEditMode.CREATE
                    else Qt.CursorShape.SizeVerCursor
                    if self._interval_edit_mode is IntervalEditMode.RESIZE
                    else Qt.CursorShape.ArrowCursor
                )
                viewport.setCursor(cursor)
            target_layout = self._pinned_layout if definition.kind is TrackKind.DEPTH else self._tracks_layout
            target_layout.addWidget(track)

        total_width = sum(
            track.width + 2 for track in visible if track.kind is not TrackKind.DEPTH
        )
        self._container.setFixedWidth(max(total_width, 1))
        self._container.setMinimumHeight(max(self._scroll.viewport().height(), 120))
        if master_plot is not None and visible_top is not None and visible_bottom is not None:
            self._synchronize_depth_ranges(visible_top, visible_bottom)
            self._update_lithology_text_visibility(visible_top, visible_bottom)
            self._update_stratigraphy_text_visibility(visible_top, visible_bottom)
            self._apply_interpretation_selection_style()
        self._update_navigation_controls()

    def _register_track_overlays(self, rendered: RenderedTrack) -> None:
        track_id = rendered.definition.track_id
        for item in (rendered.annotation_items or {}).values():
            self._overlay_layers.register(OverlayLayerKind.MARKER, track_id, item)
        for item in (rendered.lithology_label_items or {}).values():
            self._overlay_layers.register(OverlayLayerKind.ANNOTATION, track_id, item)
        for item in (rendered.lithology_description_items or {}).values():
            self._overlay_layers.register(OverlayLayerKind.ANNOTATION, track_id, item)
        for items in (rendered.stratigraphy_items or {}).values():
            for item in items:
                if hasattr(item, "setZValue") and hasattr(item, "setVisible"):
                    kind = (
                        OverlayLayerKind.ANNOTATION
                        if isinstance(item, pg.TextItem)
                        else OverlayLayerKind.MARKER
                    )
                    self._overlay_layers.register(kind, track_id, item)
        for items in (rendered.interpretation_items or {}).values():
            for item in items:
                if hasattr(item, "setZValue") and hasattr(item, "setVisible"):
                    kind = (
                        OverlayLayerKind.ANNOTATION
                        if isinstance(item, pg.TextItem)
                        else OverlayLayerKind.MARKER
                    )
                    self._overlay_layers.register(kind, track_id, item)

    def _install_cursor(self, rendered: RenderedTrack) -> None:
        if rendered.plot is None:
            return
        line = pg.InfiniteLine(
            pos=self._cursor_depth or 0.0,
            angle=0,
            movable=True,
            pen=pg.mkPen(self._cursor_color, width=self._cursor_width),
            hoverPen=pg.mkPen("#ef4444", width=3),
        )
        line.setVisible(self._cursor_enabled and self._cursor_depth is not None)
        line.sigPositionChanged.connect(lambda source: self._cursor_line_moved(source))
        rendered.plot.addItem(line)
        rendered.cursor_line = line
        self._overlay_layers.register(OverlayLayerKind.CURSOR, rendered.definition.track_id, line)
        rendered.plot.scene().sigMouseClicked.connect(
            lambda event, entry=rendered: self._cursor_plot_clicked(entry, event)
        )

    def _cursor_plot_clicked(self, rendered: RenderedTrack, event: object) -> None:
        if not self._cursor_enabled or rendered.plot is None:
            return
        scene_position = event.scenePos()  # type: ignore[attr-defined]
        if not rendered.plot.sceneBoundingRect().contains(scene_position):
            return
        point = rendered.plot.getViewBox().mapSceneToView(scene_position)
        self.set_cursor_depth(float(point.y()))

    def _cursor_line_moved(self, line: pg.InfiniteLine) -> None:
        if not self._cursor_enabled or self._cursor_guard:
            return
        self.set_cursor_depth(float(line.value()))

    def _refresh_axis_selector(self) -> None:
        self._axis_combo_guard = True
        try:
            self._axis_combo.clear()
            if self._dataset is None:
                self._axis_combo.setEnabled(False)
                return
            selected = self.vertical_index_id
            selected_row = -1
            for index in self._dataset.indexes.values():
                values = self._index_numeric_values(index)
                if (
                    index.role not in {IndexRole.DEPTH, IndexRole.TIME}
                    or np.count_nonzero(np.isfinite(values)) < 2
                ):
                    continue
                if index.role is IndexRole.DEPTH:
                    prefix = self._localizer.text("tablet.depth_axis")
                elif index.index_type is IndexType.DATETIME:
                    prefix = self._localizer.text("tablet.datetime_axis")
                else:
                    prefix = self._localizer.text("tablet.time_axis")
                unit = f" [{index.unit}]" if index.unit else ""
                self._axis_combo.addItem(f"{prefix}: {index.mnemonic}{unit}", index.index_id)
                if index.index_id == selected:
                    selected_row = self._axis_combo.count() - 1
            if selected_row < 0 and self._axis_combo.count():
                selected_row = 0
                first = self._axis_combo.itemData(0)
                if isinstance(first, str):
                    self._layout_model.vertical_index_id = first
            self._axis_combo.setCurrentIndex(selected_row)
            self._axis_combo.setEnabled(self._axis_combo.count() > 1)
        finally:
            self._axis_combo_guard = False

    def _axis_combo_changed(self, row: int) -> None:
        if self._axis_combo_guard or row < 0:
            return
        index_id = self._axis_combo.itemData(row)
        if isinstance(index_id, str):
            self.vertical_index_changed.emit(index_id)
            # Signals are synchronous in the main application. If the view is
            # used standalone and nobody handled the request, still switch the
            # local layout so the control remains functional.
            if self._layout_model.vertical_index_id != index_id:
                self.set_vertical_index(index_id)

    def horizontal_scroll_range(self) -> tuple[int, int]:
        bar = self._scroll.horizontalScrollBar()
        return bar.minimum(), bar.maximum()

    @property
    def pinned_track_ids(self) -> tuple[str, ...]:
        return tuple(
            track_id for track_id, rendered in self._rendered.items()
            if rendered.definition.kind is TrackKind.DEPTH
        )

    def _update_navigation_controls(self) -> None:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        enabled = current is not None and bounds is not None
        for widget in (
            self._goto_value,
            self._goto_button,
            self._zoom_in_button,
            self._zoom_out_button,
            self._full_range_button,
            self._vertical_scrollbar,
        ):
            widget.setEnabled(enabled)
        if not enabled or current is None or bounds is None:
            self._range_label.setText("—")
            self._vertical_scrollbar.setRange(0, 0)
            return
        top, bottom = current
        data_top, data_bottom = bounds
        self._range_label.setText(
            self._localizer.text(
                "tablet.visible_range",
                top=self._format_axis_value(top),
                bottom=self._format_axis_value(bottom),
            )
        )
        descriptor = self._axis_descriptor()
        self._goto_value.setPlaceholderText(
            self._localizer.text(
                "tablet.goto_time_placeholder"
                if descriptor is not None and descriptor.is_datetime
                else "tablet.goto_value_placeholder"
            )
        )
        data_span = data_bottom - data_top
        visible_span = bottom - top
        self._scrollbar_guard = True
        try:
            if visible_span >= data_span * 0.999999:
                self._vertical_scrollbar.setRange(0, 0)
                self._vertical_scrollbar.setPageStep(1)
                self._vertical_scrollbar.setValue(0)
            else:
                maximum = 1_000_000
                travel = max(data_span - visible_span, np.finfo(float).eps)
                value = int(round((top - data_top) / travel * maximum))
                page = max(1, int(round(visible_span / data_span * maximum)))
                self._vertical_scrollbar.setRange(0, maximum)
                self._vertical_scrollbar.setPageStep(page)
                self._vertical_scrollbar.setSingleStep(max(1, page // 10))
                self._vertical_scrollbar.setValue(max(0, min(maximum, value)))
        finally:
            self._scrollbar_guard = False

    def _vertical_scrollbar_changed(self, value: int) -> None:
        if self._scrollbar_guard:
            return
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        maximum = self._vertical_scrollbar.maximum()
        if current is None or bounds is None or maximum <= 0:
            return
        span = current[1] - current[0]
        data_top, data_bottom = bounds
        travel = max((data_bottom - data_top) - span, 0.0)
        top = data_top + travel * float(value) / float(maximum)
        self._apply_visible_depth(top, top + span, emit_change=True)

    def _go_to_axis_value(self) -> None:
        text = self._goto_value.text().strip()
        if not text:
            return
        value = self._parse_axis_value(text)
        if value is None:
            self._goto_value.setStyleSheet("border: 1px solid #dc2626;")
            return
        self._goto_value.setStyleSheet("")
        self.go_to_vertical_value(value)

    def _parse_axis_value(self, text: str) -> float | None:
        descriptor = self._axis_descriptor()
        if descriptor is not None and descriptor.is_datetime:
            try:
                normalized = text.replace("Z", "+00:00")
                moment = datetime.fromisoformat(normalized)
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=timezone.utc)
                return float(moment.timestamp())
            except ValueError:
                try:
                    parsed = np.datetime64(text, "ns")
                    if np.isnat(parsed):
                        return None
                    return float(parsed.astype(np.int64)) / 1_000_000_000.0
                except (TypeError, ValueError):
                    return None
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None

    def set_visible_depth(self, top: float, bottom: float) -> None:
        self._apply_visible_depth(top, bottom, emit_change=False)

    def scroll_depth(self, steps: float) -> bool:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        if current is None or bounds is None or not np.isfinite(steps) or steps == 0:
            return False
        self._sync_camera(bounds, current)
        top, bottom = self._camera.pan_fraction(0.12 * float(steps))
        return self._apply_visible_depth(top, bottom, emit_change=True)

    def zoom_depth(self, factor: float, anchor: float | None = None) -> bool:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        if (
            current is None
            or bounds is None
            or not np.isfinite(factor)
            or factor <= 0
        ):
            return False
        self._sync_camera(bounds, current)
        top, bottom = self._camera.zoom(float(factor), anchor=anchor)
        return self._apply_visible_depth(top, bottom, emit_change=True)

    def _sync_camera(
        self, bounds: tuple[float, float], current: tuple[float, float]
    ) -> None:
        self._camera.set_domain(*bounds, preserve_window=False)
        self._camera.set_visible_range(*current)

    def _axis_value_at_event(
        self, plot: pg.PlotWidget, event: QMouseEvent | QWheelEvent
    ) -> float | None:
        try:
            scene_position = plot.mapToScene(event.position().toPoint())
            value = float(plot.getViewBox().mapSceneToView(scene_position).y())
        except (AttributeError, TypeError, ValueError):
            return None
        return value if np.isfinite(value) else None

    def _keyboard_navigation(self, event: QKeyEvent) -> bool:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        if current is None or bounds is None:
            return False
        self._sync_camera(bounds, current)
        key = event.key()
        if key == Qt.Key.Key_Home:
            target = self._camera.home()
        elif key == Qt.Key.Key_End:
            target = self._camera.end()
        elif key == Qt.Key.Key_PageUp:
            target = self._camera.pan_fraction(-0.9)
        elif key == Qt.Key.Key_PageDown:
            target = self._camera.pan_fraction(0.9)
        elif key == Qt.Key.Key_Up:
            target = self._camera.pan_fraction(-0.1)
        elif key == Qt.Key.Key_Down:
            target = self._camera.pan_fraction(0.1)
        else:
            return False
        self._apply_visible_depth(*target, emit_change=True)
        return True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        plot = self._depth_viewports.get(watched)
        if plot is not None and isinstance(event, QWheelEvent):
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.pixelDelta().y()
            steps = float(delta) / 120.0
            if steps:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    anchor = self._axis_value_at_event(plot, event)
                    self.zoom_depth(0.8**steps, anchor=anchor)
                else:
                    self.scroll_depth(-steps)
            event.accept()
            return True
        if plot is not None and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:
                self._space_pressed = True
                event.accept()
                return True
            if event.type() == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Space:
                self._space_pressed = False
                self._pan_viewport = None
                self._pan_last_position = None
                event.accept()
                return True
            if event.type() == QEvent.Type.KeyPress and self._keyboard_navigation(event):
                event.accept()
                return True
        if plot is not None and isinstance(event, QMouseEvent):
            pan_button = event.button() == Qt.MouseButton.MiddleButton or (
                event.button() == Qt.MouseButton.LeftButton and self._space_pressed
            )
            if event.type() == QEvent.Type.MouseButtonPress and pan_button:
                self._pan_viewport = watched
                self._pan_last_position = event.position()
                watched.setProperty("tablet_pan_active", True)
                event.accept()
                return True
            if (
                event.type() == QEvent.Type.MouseMove
                and self._pan_viewport is watched
                and self._pan_last_position is not None
            ):
                previous = self._pan_last_position
                self._pan_last_position = event.position()
                previous_scene = plot.mapToScene(previous.toPoint())
                current_scene = plot.mapToScene(event.position().toPoint())
                previous_axis = plot.getViewBox().mapSceneToView(previous_scene).y()
                current_axis = plot.getViewBox().mapSceneToView(current_scene).y()
                self._apply_pan_delta(float(previous_axis - current_axis))
                event.accept()
                return True
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and self._pan_viewport is watched
            ):
                self._pan_viewport = None
                self._pan_last_position = None
                watched.setProperty("tablet_pan_active", False)
                event.accept()
                return True
        rendered = self._interpretation_viewports.get(watched)
        if rendered is not None and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Escape and self._interval_gesture is not None:
                self.cancel_interval_interaction()
                event.accept()
                return True
        if rendered is not None and isinstance(event, QMouseEvent):
            if self._handle_interpretation_mouse_event(rendered, event):
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _apply_pan_delta(self, delta: float) -> bool:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        if current is None or bounds is None or not np.isfinite(delta):
            return False
        self._sync_camera(bounds, current)
        top, bottom = self._camera.pan(float(delta))
        return self._apply_visible_depth(top, bottom, emit_change=True)

    def _apply_visible_depth(self, top: float, bottom: float, *, emit_change: bool) -> bool:
        first = next((entry.plot for entry in self._rendered.values() if entry.plot), None)
        if first is None or not np.isfinite(top) or not np.isfinite(bottom) or top == bottom:
            return False
        normalized_top, normalized_bottom = self._normalize_depth_window(top, bottom)
        current = self.visible_depth_range
        changed = current is None or not np.allclose(
            current, (normalized_top, normalized_bottom), rtol=0.0, atol=1e-9
        )
        self._depth_range_guard = True
        try:
            for rendered in self._rendered.values():
                if rendered.plot is not None:
                    rendered.plot.setYRange(normalized_top, normalized_bottom, padding=0)
            self._update_visible_curve_data(normalized_top, normalized_bottom)
            self._update_lithology_text_visibility(normalized_top, normalized_bottom)
            self._update_stratigraphy_text_visibility(normalized_top, normalized_bottom)
        finally:
            self._depth_range_guard = False
        self._update_navigation_controls()
        if changed and emit_change:
            self.visible_depth_changed.emit(normalized_top, normalized_bottom)
        return changed

    def _vertical_index(self) -> DatasetIndex | None:
        if self._dataset is None:
            return None
        requested = self._layout_model.vertical_index_id
        if requested in self._dataset.indexes:
            index = self._dataset.indexes[requested]
            if index.role in {IndexRole.DEPTH, IndexRole.TIME}:
                return index
        active = self._dataset.active_index
        if active.role in {IndexRole.DEPTH, IndexRole.TIME}:
            return active
        return next(
            (
                index
                for index in self._dataset.indexes.values()
                if index.role in {IndexRole.DEPTH, IndexRole.TIME}
            ),
            None,
        )

    @staticmethod
    def _index_numeric_values(index: DatasetIndex) -> np.ndarray:
        raw = np.asarray(index.values)
        if index.index_type is IndexType.DATETIME:
            dates = raw.astype("datetime64[ns]")
            values = dates.astype(np.int64).astype(np.float64) / 1_000_000_000.0
            values[np.isnat(dates)] = np.nan
            return values
        try:
            return raw.astype(np.float64)
        except (TypeError, ValueError):
            return np.full(raw.shape, np.nan, dtype=np.float64)

    def _axis_values(self) -> np.ndarray:
        index = self._vertical_index()
        if index is None:
            return np.array([], dtype=np.float64)
        return self._index_numeric_values(index)

    def _axis_descriptor(self) -> VerticalAxisDescriptor | None:
        index = self._vertical_index()
        if index is None:
            return None
        if index.role is IndexRole.DEPTH:
            label = self._localizer.text("tablet.depth_axis")
        elif index.index_type is IndexType.DATETIME:
            label = self._localizer.text("tablet.datetime_axis")
        else:
            label = self._localizer.text("tablet.time_axis")
        return VerticalAxisDescriptor(
            index.index_id,
            label,
            (index.unit or "").strip(),
            index.role,
            index.index_type,
        )

    def _axis_bounds(self) -> tuple[float, float] | None:
        finite = self._axis_values()
        finite = finite[np.isfinite(finite)]
        if finite.size < 2:
            return None
        minimum = float(np.min(finite))
        maximum = float(np.max(finite))
        if minimum == maximum:
            return None
        return minimum, maximum

    def _depth_bounds(self) -> tuple[float, float] | None:
        # Legacy method name retained for existing code/tests. The returned
        # interval belongs to the active vertical index (depth or time).
        return self._axis_bounds()

    def _depth_to_axis_value(self, depth: float) -> float:
        if self._dataset is None:
            return float(depth)
        axis = self._axis_values()
        source_depth = np.asarray(self._dataset.depth, dtype=float)
        valid = np.isfinite(source_depth) & np.isfinite(axis)
        if not np.any(valid):
            return float(depth)
        x = source_depth[valid]
        y = axis[valid]
        order = np.argsort(x, kind="stable")
        x = x[order]
        y = y[order]
        unique_x, unique_positions = np.unique(x, return_index=True)
        unique_y = y[unique_positions]
        if unique_x.size == 1:
            return float(unique_y[0])
        return float(np.interp(float(depth), unique_x, unique_y))

    def _axis_to_depth_value(self, value: float) -> float:
        if self._dataset is None:
            return float(value)
        axis = self._axis_values()
        source_depth = np.asarray(self._dataset.depth, dtype=float)
        valid = np.isfinite(source_depth) & np.isfinite(axis)
        if not np.any(valid):
            return float(value)
        positions = np.flatnonzero(valid)
        nearest = positions[int(np.argmin(np.abs(axis[positions] - float(value))))]
        return float(source_depth[nearest])

    def _depth_interval_to_axis(self, top: float, bottom: float) -> tuple[float, float]:
        first = self._depth_to_axis_value(top)
        second = self._depth_to_axis_value(bottom)
        return (first, second) if first <= second else (second, first)

    def _format_axis_value(self, value: float) -> str:
        descriptor = self._axis_descriptor()
        if descriptor is None or not np.isfinite(value):
            return "—"
        if descriptor.is_datetime:
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%d.%m.%Y %H:%M:%S")
            except (OverflowError, OSError, ValueError):
                return "—"
        suffix = f" {descriptor.unit}" if descriptor.unit else ""
        return f"{value:g}{suffix}"

    def _normalize_depth_window(self, top: float, bottom: float) -> tuple[float, float]:
        requested_top, requested_bottom = sorted((float(top), float(bottom)))
        bounds = self._depth_bounds()
        if bounds is None:
            return requested_top, requested_bottom
        data_top, data_bottom = bounds
        data_span = data_bottom - data_top
        requested_span = requested_bottom - requested_top
        if requested_span >= data_span:
            return data_top, data_bottom
        minimum_span = max(data_span / 100_000.0, np.finfo(float).eps)
        span = max(requested_span, minimum_span)
        normalized_top = requested_top
        normalized_bottom = requested_top + span
        if normalized_top < data_top:
            normalized_top = data_top
            normalized_bottom = data_top + span
        if normalized_bottom > data_bottom:
            normalized_bottom = data_bottom
            normalized_top = data_bottom - span
        return normalized_top, normalized_bottom

    def _apply_depth_limits(self, view_box: pg.ViewBox) -> None:
        bounds = self._depth_bounds()
        if bounds is None:
            return
        top, bottom = bounds
        span = bottom - top
        view_box.setLimits(
            yMin=top,
            yMax=bottom,
            minYRange=max(span / 100_000.0, np.finfo(float).eps),
            maxYRange=span,
        )

    @staticmethod
    def _lod_point_budget(viewport_height: int) -> int:
        """Return a pixel-aware point budget for peak-preserving curve LOD."""
        return max(5_000, min(20_000, max(int(viewport_height), 1) * 4))

    def _track_static_descriptor(
        self, definition: TrackDefinition
    ) -> tuple[str, int, bool, bool, float, str]:
        key = StaticLayerKey(
            track_id=definition.track_id,
            layer="frame-grid-axis",
            signature=(
                definition.title,
                definition.width,
                definition.grid_x,
                definition.grid_y,
                round(float(definition.grid_alpha), 6),
                definition.x_axis_label,
            ),
        )
        return cast(
            tuple[str, int, bool, bool, float, str],
            self._static_layer_cache.get_or_build(
                key,
                lambda: (
                    definition.title,
                    int(definition.width),
                    bool(definition.grid_x),
                    bool(definition.grid_y),
                    float(definition.grid_alpha),
                    definition.x_axis_label,
                ),
            ),
        )

    def _apply_static_track_configuration(
        self, rendered: RenderedTrack, definition: TrackDefinition
    ) -> None:
        title, width, grid_x, grid_y, grid_alpha, x_axis_label = (
            self._track_static_descriptor(definition)
        )
        if isinstance(rendered.widget, TabletTrackWidget):
            rendered.widget.definition = definition
            rendered.widget.title.setText(str(title))
            rendered.widget.setFixedWidth(int(width))
        if rendered.plot is not None:
            rendered.plot.showGrid(
                x=bool(grid_x), y=bool(grid_y), alpha=float(grid_alpha)
            )
            rendered.plot.setLabel("bottom", str(x_axis_label))

    def _apply_curve_styles(
        self, rendered: RenderedTrack, definition: TrackDefinition
    ) -> None:
        logarithmic = definition.x_scale is XScale.LOGARITHMIC
        if rendered.plot is not None:
            rendered.plot.setLogMode(x=logarithmic, y=False)
        for index, (mnemonic, item) in enumerate((rendered.curve_items or {}).items()):
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
                    pg.intColor(index, hues=max(1, len(definition.curve_mnemonics)))
                )
            )
            item.setPen(pen)
        if rendered.plot is None:
            return
        if definition.x_min is not None and definition.x_max is not None:
            minimum, maximum = definition.x_min, definition.x_max
            if logarithmic:
                minimum, maximum = float(np.log10(minimum)), float(np.log10(maximum))
            rendered.plot.setXRange(minimum, maximum, padding=0)
        elif rendered.curve_items:
            automatic = self._automatic_track_x_range(definition, logarithmic)
            if automatic is not None:
                rendered.plot.setXRange(*automatic, padding=0)

    def _refresh_rendered_track(
        self, rendered: RenderedTrack, reasons: DirtyReason
    ) -> None:
        try:
            definition = self._layout_model.track_by_id(rendered.definition.track_id)
        except KeyError:
            return
        rendered.definition = definition
        if reasons & (DirtyReason.STATIC | DirtyReason.STYLE):
            self._apply_static_track_configuration(rendered, definition)
        if reasons & DirtyReason.STYLE:
            self._apply_curve_styles(rendered, definition)
        if reasons & (DirtyReason.DATA | DirtyReason.VIEWPORT | DirtyReason.STYLE):
            visible = self.visible_depth_range
            if visible is not None:
                self._update_rendered_track_curve_data(rendered, *visible)
        if rendered.plot is not None:
            rendered.plot.viewport().update()

    def _update_rendered_track_curve_data(
        self, rendered: RenderedTrack, top: float, bottom: float
    ) -> None:
        if self._dataset is None:
            return
        depth = self._axis_values()
        logarithmic = rendered.definition.x_scale is XScale.LOGARITHMIC
        for mnemonic, item in (rendered.curve_items or {}).items():
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                item.setData([], [])
                continue
            source_values = np.asarray(curve.values, dtype=float)
            budget = self._lod_point_budget(
                rendered.plot.viewport().height() if rendered.plot is not None else 1000
            )
            key = self._curve_geometry_key(
                mnemonic, depth, source_values, top, bottom, budget, logarithmic
            )
            render_keys = rendered.curve_render_keys
            if render_keys is not None and render_keys.get(mnemonic) == key:
                continue
            values, visible_depth = self._geometry_cache.get_or_build(
                key, depth, source_values
            )
            item.setData(values, visible_depth)
            if render_keys is not None:
                render_keys[mnemonic] = key

    def _populate_track(
        self,
        track: TabletTrackWidget,
        definition: TrackDefinition,
        visible_top: float | None,
        visible_bottom: float | None,
    ) -> tuple[tuple[str, ...], dict[str, pg.PlotDataItem]]:
        assert self._dataset is not None
        depth = self._axis_values()

        if definition.kind == TrackKind.DEPTH:
            descriptor = self._axis_descriptor()
            track.plot.showAxis("left")
            label = descriptor.label if descriptor is not None else "Глубина"
            unit = descriptor.unit if descriptor is not None else "м"
            track.title.setText(label)
            track.plot.setLabel("left", label, units=unit or None)
            track.plot.hideAxis("bottom")
            track.plot.setMouseEnabled(x=False, y=True)
            return (), {}

        if definition.kind in (
            TrackKind.LITHOLOGY,
            TrackKind.CUTTINGS,
            TrackKind.CALCIMETRY,
            TrackKind.LBA,
            TrackKind.STRATIGRAPHY,
            TrackKind.INTERPRETATION,
            TrackKind.TEXT,
        ):
            track.plot.hideAxis("bottom")
            track.plot.setXRange(0.0, 1.0, padding=0)
            track.plot.setMouseEnabled(x=False, y=True)
            return (), {}

        track.plot.setLabel("bottom", definition.title)
        track.plot.setMouseEnabled(x=False, y=True)
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
                    else pg.mkPen(pg.intColor(index, hues=max(1, len(definition.curve_mnemonics))))
                )
                if visible_top is None or visible_bottom is None:
                    visible_values = np.array([], dtype=np.float64)
                    visible_depth = np.array([], dtype=np.float64)
                else:
                    budget = self._lod_point_budget(track.plot.viewport().height())
                    key = self._curve_geometry_key(
                        mnemonic, depth, values, visible_top, visible_bottom, budget, logarithmic
                    )
                    visible_values, visible_depth = self._geometry_cache.get_or_build(
                        key, depth, values
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
        elif curve_items:
            automatic_range = self._automatic_track_x_range(definition, logarithmic)
            if automatic_range is not None:
                track.plot.setXRange(*automatic_range, padding=0)
        else:
            track.title.setText(f"{definition.title} — нет числовых данных")
            message = pg.TextItem("Нет числовых данных", color="#64748b", anchor=(0.5, 0.5))
            depth_bounds = self._depth_bounds()
            center_depth = sum(depth_bounds) / 2.0 if depth_bounds is not None else 0.0
            message.setPos(0.5, center_depth)
            track.plot.addItem(message)
            track.plot.setLogMode(x=False, y=False)
            track.plot.setXRange(0.0, 1.0, padding=0)
        return tuple(legend_labels), curve_items

    def _automatic_track_x_range(
        self, definition: TrackDefinition, logarithmic: bool
    ) -> tuple[float, float] | None:
        if self._dataset is None:
            return None
        values: list[np.ndarray] = []
        for mnemonic in definition.curve_mnemonics:
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                continue
            finite = np.asarray(curve.values, dtype=float)
            finite = finite[np.isfinite(finite)]
            if logarithmic:
                finite = finite[finite > 0]
            if finite.size:
                values.append(finite)
        if not values:
            return None
        combined = np.concatenate(values)
        if combined.size >= 10:
            minimum, maximum = (
                float(value) for value in np.nanpercentile(combined, [1.0, 99.0])
            )
        else:
            minimum, maximum = float(np.min(combined)), float(np.max(combined))
        if logarithmic:
            minimum = float(np.log10(max(minimum, float(np.min(combined)))))
            maximum = float(np.log10(maximum))
        if not np.isfinite(minimum) or not np.isfinite(maximum):
            return None
        if minimum == maximum:
            padding = max(abs(minimum) * 0.05, 0.1)
        else:
            padding = (maximum - minimum) * 0.04
        return minimum - padding, maximum + padding

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
            axis_top, axis_bottom = self._depth_interval_to_axis(
                interval.top_depth, interval.bottom_depth
            )
            item = pg.BarGraphItem(
                x=[0.5],
                y=[(axis_top + axis_bottom) / 2.0],
                width=1.0,
                height=max(axis_bottom - axis_top, np.finfo(float).eps),
                brush=lithology_brush(color, pattern),
                pen=pg.mkPen("#303030", width=0.7),
            )
            track.plot.addItem(item)
            rendered[interval.interval_id] = item
        return rendered

    def _populate_stratigraphy(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, tuple[object, ...]]:
        if definition.kind is not TrackKind.STRATIGRAPHY:
            return {}
        ranks = sorted(
            {item.rank or "" for item in self._stratigraphy}, key=stratigraphy_rank_order
        )
        lane_by_rank = {rank: index for index, rank in enumerate(ranks)}
        track.plot.hideAxis("bottom")
        track.plot.setXRange(0.0, float(max(1, len(ranks))), padding=0)
        track.plot.setMouseEnabled(x=False, y=True)
        rendered: dict[str, tuple[object, ...]] = {}
        for interval in self._stratigraphy:
            lane = lane_by_rank[interval.rank or ""]
            color = interval.color if pg.mkColor(interval.color).isValid() else "#dbeafe"
            axis_top, axis_bottom = self._depth_interval_to_axis(
                interval.top_depth, interval.bottom_depth
            )
            bar = pg.BarGraphItem(
                x=[lane + 0.5],
                y=[(axis_top + axis_bottom) / 2.0],
                width=0.94,
                height=max(axis_bottom - axis_top, np.finfo(float).eps),
                brush=pg.mkBrush(color),
                pen=pg.mkPen("#334155", width=0.7),
            )
            track.plot.addItem(bar)
            label_text = "\n".join(value for value in (interval.code, interval.name) if value)
            label = pg.TextItem(label_text, color="#0f172a", anchor=(0.5, 0.5))
            label.setPos(lane + 0.5, (axis_top + axis_bottom) / 2.0)
            track.plot.addItem(label)
            rendered[interval.interval_id] = (bar, label)
        return rendered

    def _populate_interpretation(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> tuple[dict[str, tuple[object, ...]], dict[str, int]]:
        if definition.kind is not TrackKind.INTERPRETATION:
            return {}, {}
        interpretation = self._current_interpretation()
        track.plot.hideAxis("bottom")
        track.plot.setMouseEnabled(x=False, y=True)
        if interpretation is None:
            track.title.setText(definition.title)
            track.plot.setXRange(0.0, 1.0, padding=0)
            return {}, {}
        track.title.setText(f"{definition.title}: {interpretation.name}")
        interval_types = sorted(
            {item.interval_type for item in interpretation.intervals}, key=str.casefold
        )
        lane_by_type = {name: index for index, name in enumerate(interval_types)}
        track.plot.setXRange(0.0, float(max(1, len(interval_types))), padding=0)
        rendered: dict[str, tuple[object, ...]] = {}
        lane_by_interval: dict[str, int] = {}
        for interval in sorted(
            interpretation.intervals,
            key=lambda item: (item.top_depth, item.bottom_depth, item.interval_type.casefold()),
        ):
            lane = lane_by_type[interval.interval_type]
            color = interval.color if pg.mkColor(interval.color).isValid() else "#fde68a"
            axis_top, axis_bottom = self._depth_interval_to_axis(
                interval.top_depth, interval.bottom_depth
            )
            bar = pg.BarGraphItem(
                x=[lane + 0.5],
                y=[(axis_top + axis_bottom) / 2.0],
                width=0.94,
                height=max(axis_bottom - axis_top, np.finfo(float).eps),
                brush=pg.mkBrush(color),
                pen=pg.mkPen("#475569", width=0.8),
            )
            track.plot.addItem(bar)
            label_text = f"{interval.interval_type}\n{interval.label}"
            label = pg.TextItem(label_text, color="#0f172a", anchor=(0.5, 0.5))
            label.setPos(lane + 0.5, (axis_top + axis_bottom) / 2.0)
            label.setToolTip(
                f"{interval.top_depth:g}–{interval.bottom_depth:g} m\n"
                f"{interval.interval_type}: {interval.label}"
                + (f"\n{interval.comment}" if interval.comment else "")
            )
            track.plot.addItem(label)
            rendered[interval.interval_id] = (bar, label)
            lane_by_interval[interval.interval_id] = lane
        return rendered, lane_by_interval

    def hit_test_interpretation(
        self, track_id: str, x_value: float, depth: float
    ) -> str | None:
        rendered = self._rendered.get(track_id)
        interpretation = self._current_interpretation()
        if (
            rendered is None
            or rendered.definition.kind is not TrackKind.INTERPRETATION
            or interpretation is None
        ):
            return None
        lane = int(np.floor(float(x_value)))
        model_depth = self._axis_to_depth_value(depth)
        candidates = [
            item
            for item in interpretation.intervals
            if (rendered.interpretation_lanes or {}).get(item.interval_id) == lane
            and item.top_depth <= model_depth <= item.bottom_depth
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (item.bottom_depth - item.top_depth, item.top_depth, item.interval_id),
        ).interval_id

    def begin_interval_drag(self, track_id: str, x_value: float, depth: float) -> bool:
        rendered = self._rendered.get(track_id)
        interpretation = self._current_interpretation()
        if (
            rendered is None
            or rendered.definition.kind is not TrackKind.INTERPRETATION
            or rendered.plot is None
            or interpretation is None
            or self._interval_edit_mode is IntervalEditMode.SELECT
        ):
            return False
        snapped = self._snap_depth(self._axis_to_depth_value(depth))
        lane_types = self._interpretation_lane_types(interpretation)
        lane = max(0, int(np.floor(float(x_value))))
        if lane_types:
            lane = min(lane, len(lane_types) - 1)
            interval_type = lane_types[lane]
        else:
            lane = 0
            interval_type = self._interval_creation_type

        if self._interval_edit_mode is IntervalEditMode.CREATE:
            self._interval_gesture = _IntervalGesture(
                track_id=track_id,
                interpretation_id=interpretation.interpretation_id,
                mode=IntervalEditMode.CREATE,
                lane=lane,
                interval_type=interval_type,
                start_depth=snapped,
                current_depth=snapped,
            )
            self._update_interval_preview()
            return True

        tolerance = self._resize_tolerance(rendered)
        interval = self._interval_for_resize(rendered, lane, snapped, tolerance)
        if interval is None:
            interval_id = self.hit_test_interpretation(track_id, x_value, snapped)
            if interval_id is not None:
                self.set_selected_interval(
                    interpretation.interpretation_id, interval_id, emit_signal=True
                )
            return False
        edge = choose_resize_edge(interval, snapped, tolerance=tolerance)
        if edge is None:
            return False
        self.set_selected_interval(
            interpretation.interpretation_id, interval.interval_id, emit_signal=True
        )
        self._interval_gesture = _IntervalGesture(
            track_id=track_id,
            interpretation_id=interpretation.interpretation_id,
            mode=IntervalEditMode.RESIZE,
            lane=lane,
            interval_type=interval.interval_type,
            start_depth=snapped,
            current_depth=snapped,
            interval_id=interval.interval_id,
            edge=edge,
            original_top=interval.top_depth,
            original_bottom=interval.bottom_depth,
        )
        self._update_interval_preview()
        return True

    def update_interval_drag(self, depth: float) -> bool:
        if self._interval_gesture is None:
            return False
        self._interval_gesture.current_depth = self._snap_depth(
            self._axis_to_depth_value(depth)
        )
        self._update_interval_preview()
        return True

    def finish_interval_drag(self, depth: float) -> bool:
        gesture = self._interval_gesture
        if gesture is None:
            return False
        gesture.current_depth = self._snap_depth(self._axis_to_depth_value(depth))
        result = self._gesture_result()
        self.cancel_interval_interaction(emit_signal=False)
        if result is None:
            return False
        if gesture.mode is IntervalEditMode.CREATE:
            self.interval_create_requested.emit(
                gesture.interpretation_id,
                result.top_depth,
                result.bottom_depth,
                gesture.interval_type,
            )
            return True
        if gesture.interval_id is None:
            return False
        self.interval_resize_requested.emit(
            gesture.interpretation_id,
            gesture.interval_id,
            result.top_depth,
            result.bottom_depth,
        )
        return True

    def cancel_interval_interaction(self, *, emit_signal: bool = True) -> None:
        gesture = self._interval_gesture
        if gesture is not None:
            rendered = self._rendered.get(gesture.track_id)
            if rendered is not None and rendered.plot is not None:
                preview = rendered.interpretation_preview
                if preview is not None:
                    self._overlay_layers.unregister(
                        OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
                    )
                    rendered.plot.removeItem(preview)
                rendered.interpretation_preview = None
        self._interval_gesture = None
        if gesture is not None and emit_signal:
            self.interval_interaction_cancelled.emit()

    def _handle_interpretation_mouse_event(
        self, rendered: RenderedTrack, event: QMouseEvent
    ) -> bool:
        if rendered.plot is None or self._interval_edit_mode is IntervalEditMode.SELECT:
            return False
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            point = self._mouse_event_view_point(rendered, event)
            return self.begin_interval_drag(
                rendered.definition.track_id, float(point.x()), float(point.y())
            )
        if event_type == QEvent.Type.MouseMove and self._interval_gesture is not None:
            point = self._mouse_event_view_point(rendered, event)
            return self.update_interval_drag(float(point.y()))
        if event_type == QEvent.Type.MouseButtonRelease and self._interval_gesture is not None:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            point = self._mouse_event_view_point(rendered, event)
            return self.finish_interval_drag(float(point.y()))
        return False

    @staticmethod
    def _mouse_event_view_point(
        rendered: RenderedTrack, event: QMouseEvent
    ) -> QPointF:
        assert rendered.plot is not None
        plot_position = rendered.plot.mapFromGlobal(event.globalPosition().toPoint())
        scene_position = rendered.plot.mapToScene(plot_position)
        return rendered.plot.getViewBox().mapSceneToView(scene_position)

    def _snap_depth(self, depth: float) -> float:
        if self._dataset is None:
            return float(depth)
        return snap_depth_to_samples(float(depth), self._dataset.depth)

    def _minimum_depth_span(self) -> float:
        if self._dataset is None:
            return 0.0
        values = np.asarray(self._dataset.depth, dtype=float)
        values = np.unique(values[np.isfinite(values)])
        if values.size < 2:
            return 0.0
        differences = np.diff(values)
        positive = differences[differences > 0]
        return float(np.min(positive)) * 0.25 if positive.size else 0.0

    def _gesture_result(self) -> IntervalDragResult | None:
        gesture = self._interval_gesture
        if gesture is None:
            return None
        minimum_span = self._minimum_depth_span()
        if gesture.mode is IntervalEditMode.CREATE:
            return normalize_drag_range(
                gesture.start_depth,
                gesture.current_depth,
                minimum_span=minimum_span,
            )
        interpretation = self._current_interpretation()
        if interpretation is None or gesture.interval_id is None or gesture.edge is None:
            return None
        interval = next(
            (item for item in interpretation.intervals if item.interval_id == gesture.interval_id),
            None,
        )
        if interval is None:
            return None
        return resize_interval_range(
            interval,
            gesture.edge,  # type: ignore[arg-type]
            gesture.current_depth,
            minimum_span=minimum_span,
        )

    def _update_interval_preview(self) -> None:
        gesture = self._interval_gesture
        if gesture is None:
            return
        rendered = self._rendered.get(gesture.track_id)
        result = self._gesture_result()
        if rendered is None or rendered.plot is None:
            return
        if result is None:
            top = bottom = gesture.current_depth
        else:
            top, bottom = result.top_depth, result.bottom_depth
        axis_top, axis_bottom = self._depth_interval_to_axis(top, bottom)
        height = max(axis_bottom - axis_top, np.finfo(float).eps)
        middle = (axis_top + axis_bottom) / 2.0
        options = dict(
            x=[gesture.lane + 0.5],
            y=[middle],
            width=0.94,
            height=height,
            brush=pg.mkBrush(37, 99, 235, 75),
            pen=pg.mkPen("#2563eb", width=2.0, style=Qt.PenStyle.DashLine),
        )
        if rendered.interpretation_preview is None:
            preview = pg.BarGraphItem(**options)
            rendered.plot.addItem(preview)
            rendered.interpretation_preview = preview
            self._overlay_layers.register(
                OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
            )
        else:
            rendered.interpretation_preview.setOpts(**options)

    @staticmethod
    def _interpretation_lane_types(
        interpretation: WellInterpretation,
    ) -> list[str]:
        return sorted({item.interval_type for item in interpretation.intervals}, key=str.casefold)

    def _resize_tolerance(self, rendered: RenderedTrack) -> float:
        if rendered.plot is None:
            return 0.0
        y_range = rendered.plot.getViewBox().viewRange()[1]
        axis_span = abs(float(y_range[1]) - float(y_range[0]))
        height = max(1, rendered.plot.viewport().height())
        axis_tolerance = axis_span * 8.0 / height
        center = sum(map(float, y_range)) / 2.0
        depth_tolerance = abs(
            self._axis_to_depth_value(center + axis_tolerance)
            - self._axis_to_depth_value(center)
        )
        return max(depth_tolerance, self._minimum_depth_span())

    def _interval_for_resize(
        self, rendered: RenderedTrack, lane: int, depth: float, tolerance: float
    ):
        interpretation = self._current_interpretation()
        if interpretation is None:
            return None
        candidates = [
            item
            for item in interpretation.intervals
            if (rendered.interpretation_lanes or {}).get(item.interval_id) == lane
            and item.top_depth - tolerance <= depth <= item.bottom_depth + tolerance
            and choose_resize_edge(item, depth, tolerance=tolerance) is not None
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: min(
                abs(depth - item.top_depth), abs(depth - item.bottom_depth)
            ),
        )

    def _interpretation_plot_clicked(self, rendered: RenderedTrack, event: object) -> None:
        if self._interval_edit_mode is not IntervalEditMode.SELECT or rendered.plot is None:
            return
        button = getattr(event, "button", lambda: Qt.MouseButton.LeftButton)()
        if button != Qt.MouseButton.LeftButton:
            return
        scene_position = event.scenePos()  # type: ignore[attr-defined]
        if not rendered.plot.sceneBoundingRect().contains(scene_position):
            return
        point = rendered.plot.getViewBox().mapSceneToView(scene_position)
        interval_id = self.hit_test_interpretation(
            rendered.definition.track_id, float(point.x()), float(point.y())
        )
        interpretation = self._current_interpretation()
        if interval_id is None or interpretation is None:
            self.clear_interval_selection(emit_signal=True)
            return
        self.set_selected_interval(
            interpretation.interpretation_id, interval_id, emit_signal=True
        )

    def _apply_interpretation_selection_style(self) -> None:
        self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
        interpretation = self._current_interpretation()
        selected = None
        if interpretation is not None and self._selected_interval_id is not None:
            selected = next(
                (item for item in interpretation.intervals if item.interval_id == self._selected_interval_id),
                None,
            )
        for rendered in self._rendered.values():
            for interval_id, items in (rendered.interpretation_items or {}).items():
                if not items or not isinstance(items[0], pg.BarGraphItem):
                    continue
                is_selected = interval_id == self._selected_interval_id
                items[0].setOpts(
                    pen=pg.mkPen(
                        "#111827" if is_selected else "#475569",
                        width=3.0 if is_selected else 0.8,
                    )
                )
                if len(items) > 1 and isinstance(items[1], pg.TextItem):
                    items[1].setColor("#000000" if is_selected else "#0f172a")
            if rendered.selection_highlight is not None and rendered.plot is not None:
                self._overlay_layers.unregister(
                    OverlayLayerKind.SELECTION,
                    rendered.definition.track_id,
                    rendered.selection_highlight,
                )
                rendered.plot.removeItem(rendered.selection_highlight)
                rendered.selection_highlight = None
            if (
                selected is None
                or rendered.plot is None
                or rendered.definition.kind is not TrackKind.INTERPRETATION
            ):
                continue
            lane = (rendered.interpretation_lanes or {}).get(selected.interval_id)
            if lane is None:
                continue
            axis_top, axis_bottom = self._depth_interval_to_axis(
                selected.top_depth, selected.bottom_depth
            )
            highlight = pg.BarGraphItem(
                x=[lane + 0.5],
                y=[(axis_top + axis_bottom) / 2.0],
                width=0.94,
                height=max(axis_bottom - axis_top, np.finfo(float).eps),
                brush=pg.mkBrush(0, 0, 0, 0),
                pen=pg.mkPen("#111827", width=3.0),
            )
            rendered.plot.addItem(highlight)
            rendered.selection_highlight = highlight
            self._overlay_layers.register(
                OverlayLayerKind.SELECTION, rendered.definition.track_id, highlight
            )
        self._overlay_layers.consume_dirty(OverlayLayerKind.SELECTION)

    def show_overlay_tooltip(
        self, track_id: str, x_value: float, axis_value: float, text: str
    ) -> bool:
        rendered = self._rendered.get(track_id)
        if rendered is None or rendered.plot is None:
            return False
        item = self._tooltip_items.get(track_id)
        if item is None:
            item = pg.TextItem("", color="#0f172a", fill=pg.mkBrush(255, 255, 255, 225))
            rendered.plot.addItem(item)
            self._tooltip_items[track_id] = item
            self._overlay_layers.register(OverlayLayerKind.TOOLTIP, track_id, item)
        item.setText(str(text))
        item.setPos(float(x_value), float(axis_value))
        item.setVisible(True)
        self._overlay_layers.mark_dirty(OverlayLayerKind.TOOLTIP)
        self._overlay_layers.consume_dirty(OverlayLayerKind.TOOLTIP)
        return True

    def clear_overlay_tooltip(self, track_id: str | None = None) -> int:
        target_ids = tuple(self._tooltip_items) if track_id is None else (track_id,)
        cleared = 0
        for current_id in target_ids:
            item = self._tooltip_items.get(current_id)
            if item is not None and item.isVisible():
                item.setVisible(False)
                cleared += 1
        if cleared:
            self._overlay_layers.mark_dirty(OverlayLayerKind.TOOLTIP)
            self._overlay_layers.consume_dirty(OverlayLayerKind.TOOLTIP)
        return cleared

    def show_rubber_band(
        self, track_id: str, x_left: float, x_right: float, axis_top: float, axis_bottom: float
    ) -> bool:
        rendered = self._rendered.get(track_id)
        if rendered is None or rendered.plot is None:
            return False
        left, right = sorted((float(x_left), float(x_right)))
        top, bottom = sorted((float(axis_top), float(axis_bottom)))
        options = dict(
            x=[(left + right) / 2.0],
            y=[(top + bottom) / 2.0],
            width=max(right - left, np.finfo(float).eps),
            height=max(bottom - top, np.finfo(float).eps),
            brush=pg.mkBrush(59, 130, 246, 35),
            pen=pg.mkPen("#3b82f6", width=1.5, style=Qt.PenStyle.DashLine),
        )
        item = self._rubber_band_items.get(track_id)
        if item is None:
            item = pg.BarGraphItem(**options)
            rendered.plot.addItem(item)
            self._rubber_band_items[track_id] = item
            self._overlay_layers.register(OverlayLayerKind.RUBBER_BAND, track_id, item)
        else:
            item.setOpts(**options)
            item.setVisible(True)
        self._overlay_layers.mark_dirty(OverlayLayerKind.RUBBER_BAND)
        self._overlay_layers.consume_dirty(OverlayLayerKind.RUBBER_BAND)
        return True

    def clear_rubber_band(self, track_id: str | None = None) -> int:
        target_ids = tuple(self._rubber_band_items) if track_id is None else (track_id,)
        cleared = 0
        for current_id in target_ids:
            item = self._rubber_band_items.get(current_id)
            if item is not None and item.isVisible():
                item.setVisible(False)
                cleared += 1
        if cleared:
            self._overlay_layers.mark_dirty(OverlayLayerKind.RUBBER_BAND)
            self._overlay_layers.consume_dirty(OverlayLayerKind.RUBBER_BAND)
        return cleared

    def _populate_cuttings(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, tuple[pg.BarGraphItem, ...]]:
        if definition.kind is not TrackKind.CUTTINGS:
            return {}
        track.plot.hideAxis("bottom")
        track.plot.setXRange(0.0, 100.0, padding=0)
        track.plot.setMouseEnabled(x=False, y=True)
        rendered: dict[str, tuple[pg.BarGraphItem, ...]] = {}
        for sample in self._cuttings:
            left = 0.0
            axis_top, axis_bottom = self._depth_interval_to_axis(
                sample.top_depth, sample.bottom_depth
            )
            items: list[pg.BarGraphItem] = []
            for component in sample.components:
                lithotype = self._lithotype_catalog.get(component.lithotype_id)
                color = lithotype.color if lithotype is not None else "#b0b0b0"
                pattern = lithotype.pattern_key if lithotype is not None else "solid"
                width = float(component.percentage)
                item = pg.BarGraphItem(
                    x=[left + width / 2.0],
                    y=[(axis_top + axis_bottom) / 2.0],
                    width=width,
                    height=max(axis_bottom - axis_top, np.finfo(float).eps),
                    brush=lithology_brush(color, pattern),
                    pen=pg.mkPen("#303030", width=0.7),
                )
                track.plot.addItem(item)
                items.append(item)
                left += width
            rendered[sample.sample_id] = tuple(items)
        return rendered

    def _populate_sample_analysis(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, tuple[object, ...]]:
        if definition.kind not in {TrackKind.CALCIMETRY, TrackKind.LBA}:
            return {}
        track.plot.hideAxis("bottom")
        track.plot.setXRange(
            0.0, 100.0 if definition.kind is TrackKind.CALCIMETRY else 1.0, padding=0
        )
        track.plot.setMouseEnabled(x=False, y=True)
        rendered: dict[str, tuple[object, ...]] = {}
        for sample in self._cuttings:
            items: list[object] = []
            axis_top, axis_bottom = self._depth_interval_to_axis(
                sample.top_depth, sample.bottom_depth
            )
            if definition.kind is TrackKind.CALCIMETRY:
                left = 0.0
                for value, color in (
                    (sample.calcite_percent, "#22d3ee"),
                    (sample.dolomite_percent, "#a78bfa"),
                    (sample.insoluble_residue_percent, "#d1d5db"),
                ):
                    if value is None:
                        continue
                    bar = pg.BarGraphItem(
                        x=[left + value / 2.0],
                        y=[(axis_top + axis_bottom) / 2.0],
                        width=value,
                        height=max(axis_bottom - axis_top, np.finfo(float).eps),
                        brush=pg.mkBrush(color),
                        pen=pg.mkPen("#334155", width=0.7),
                    )
                    track.plot.addItem(bar)
                    items.append(bar)
                    left += value
            else:
                fields = [
                    f"G={sample.lba_group}" if sample.lba_group is not None else None,
                    sample.lba_type_id,
                    f"I={sample.lba_intensity}" if sample.lba_intensity is not None else None,
                    sample.lba_color,
                    sample.lba_distribution,
                    sample.lba_cut,
                    sample.lba_cut_speed,
                    sample.lba_cut_color,
                    sample.lba_residue_type,
                    sample.lba_residue_color,
                    sample.lba_odour,
                    sample.lba_stain,
                    sample.lba_description,
                ]
                text = "; ".join(value for value in fields if value)
                if text:
                    label = pg.TextItem(text, color="#92400e", anchor=(0.0, 0.5))
                    label.setPos(0.02, (axis_top + axis_bottom) / 2.0)
                    track.plot.addItem(label)
                    items.append(label)
            if items:
                rendered[sample.sample_id] = tuple(items)
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
                f'<div style="width:{text_width}px; color:#202020">{escape(description)}</div>'
            )
            axis_top, axis_bottom = self._depth_interval_to_axis(
                interval.top_depth, interval.bottom_depth
            )
            label.setPos(0.02, (axis_top + axis_bottom) / 2.0)
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
            axis_top, axis_bottom = self._depth_interval_to_axis(
                interval.top_depth, interval.bottom_depth
            )
            label.setPos(0.5, (axis_top + axis_bottom) / 2.0)
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
                pos=self._depth_to_axis_value(float(depth)),
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

    def _curve_geometry_key(
        self,
        mnemonic: str,
        axis: np.ndarray,
        values: np.ndarray,
        top: float,
        bottom: float,
        max_points: int,
        positive_values_only: bool,
    ) -> CurveGeometryKey:
        axis_id = self.vertical_index_id or "vertical-axis"
        return CurveGeometryKey(
            curve_id=mnemonic,
            axis_id=axis_id,
            values_revision=(id(values), values.size),
            axis_revision=(id(axis), axis.size),
            top=float(top),
            bottom=float(bottom),
            max_points=int(max_points),
            positive_values_only=positive_values_only,
        )

    def _update_visible_curve_data(self, top: float, bottom: float) -> None:
        for rendered in self._rendered.values():
            self._update_rendered_track_curve_data(rendered, top, bottom)

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
                    axis_interval = (
                        self._depth_interval_to_axis(interval.top_depth, interval.bottom_depth)
                        if interval is not None
                        else None
                    )
                    visible = axis_interval is not None and lithology_label_is_visible(
                        axis_interval[0],
                        axis_interval[1],
                        top,
                        bottom,
                        viewport_height,
                        minimum_pixels=minimum_pixels,
                    )
                    text_item.setVisible(visible)

    def _update_stratigraphy_text_visibility(self, top: float, bottom: float) -> None:
        intervals = {item.interval_id: item for item in self._stratigraphy}
        for rendered in self._rendered.values():
            if rendered.plot is None:
                continue
            viewport_height = rendered.plot.viewport().height()
            for interval_id, items in (rendered.stratigraphy_items or {}).items():
                interval = intervals.get(interval_id)
                label = next((item for item in items if isinstance(item, pg.TextItem)), None)
                if label is None:
                    continue
                axis_interval = (
                    self._depth_interval_to_axis(interval.top_depth, interval.bottom_depth)
                    if interval is not None
                    else None
                )
                visible = axis_interval is not None and lithology_label_is_visible(
                    axis_interval[0],
                    axis_interval[1],
                    top,
                    bottom,
                    viewport_height,
                    minimum_pixels=22,
                )
                label.setVisible(visible)

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
            top, bottom = self._normalize_depth_window(
                float(y_range[0]), float(y_range[1])
            )
            self._update_visible_curve_data(top, bottom)
            self._synchronize_depth_ranges(top, bottom)
            self._update_lithology_text_visibility(top, bottom)
            self._update_stratigraphy_text_visibility(top, bottom)
            self._update_navigation_controls()
            self.visible_depth_changed.emit(top, bottom)
        finally:
            self._sync_guard = False
