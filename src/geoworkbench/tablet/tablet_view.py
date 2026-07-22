from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from enum import StrEnum
import re
import textwrap
from typing import cast

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import (
    QColor,
    QCursor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QBrush,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMenu,
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
from geoworkbench.project.stratigraphy_controller import (
    stratigraphy_rank_order,
    stratigraphy_text_anchor,
    stratigraphy_text_angle,
    stratigraphy_text_position_fraction,
)
from geoworkbench.printing.lba_visuals import (
    normalized_lba_intensity,
    resolve_lba_type_style,
)
from geoworkbench.printing.image_asset_rendering import image_asset_pixmap
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
    annotation_from_canvas,
    is_annotation_object,
)
from geoworkbench.services.curve_editing import DrawPoint, interpolate_drawn_curve
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.parameter_labels import localized_curve_name
from geoworkbench.services.time_display import (
    format_datetime_at_row,
    format_elapsed_time,
    format_time_curve_at_row,
    format_unix_seconds,
)
from geoworkbench.ui.oriented_text_label import OrientedTextLabel
from geoworkbench.tablet.curve_scaling import automatic_curve_range, normalize_curve_values
from geoworkbench.tablet.camera import (
    DEPTH_VIEW_SPAN_PRESETS,
    TabletCamera,
    recommended_initial_range,
    recommended_initial_span,
)
from geoworkbench.tablet.geometry_cache import (
    CurveGeometryCache,
    CurveGeometryKey,
    GeometryCacheStats,
)
from geoworkbench.tablet.render_invalidation import (
    DirtyReason,
    DirtyRenderStats,
    TrackDirtyRegistry,
)
from geoworkbench.tablet.static_layer_cache import (
    StaticLayerCache,
    StaticLayerCacheStats,
    StaticLayerKey,
)
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
from geoworkbench.tablet.lithology_graphics import DeviceTiledRectItem
from geoworkbench.tablet.lithology_patterns import lithology_brush
from geoworkbench.tablet.lithology_labels import lithology_label_is_visible
from geoworkbench.tablet.models import (
    CurveLineStyle,
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)
from geoworkbench.tablet.relative_gas import (
    build_relative_gas_stack,
    is_relative_gas_track,
)
from geoworkbench.tablet.resize import TrackResizeGesture
from geoworkbench.tablet.annotation_graphics import (
    TabletAnnotationItem,
    TabletAnnotationOverlay,
)
from geoworkbench.tablet.annotation_tool import (
    AnnotationGeometryChange,
    AnnotationInteractionHandler,
)
from geoworkbench.tablet.interaction_router import (
    InputEventKind,
    InteractionResponse,
    PointerButton,
    TabletInputEvent,
    TabletInteractionRouter,
)
from geoworkbench.tablet.track_edit_tool import TrackEditInteractionHandler
from geoworkbench.tablet.edit_mode_coordinator import TabletEditModeCoordinator
from geoworkbench.tablet.interaction_watchdog import TabletInteractionWatchdog
from geoworkbench.tablet.selection_interaction import (
    CallbackCommand,
    CommandStack,
    HitResult,
    SelectableKind,
    SelectionManager,
    SelectionRef,
    SelectionSnapshot,
    TrackHeaderDrag,
    choose_best_hit,
)


class GeologicalInputMode(StrEnum):
    """Explicit geological editing tool selected from the main toolbar."""

    SELECT = "select"
    LITHOLOGY = "lithology"
    SAMPLE = "sample"
    STRATIGRAPHY = "stratigraphy"
    DESCRIPTION = "description"
    EDIT = "edit"


class CurvePencilMode(StrEnum):
    """How the user defines a replacement segment for the selected curve."""

    FREEHAND = "freehand"
    CONNECT_POINTS = "connect_points"


@dataclass(slots=True)
class RenderedTrack:
    definition: TrackDefinition
    widget: TabletTrackWidget
    plot: pg.PlotWidget | None = None
    legend_labels: tuple[str, ...] = ()
    curve_items: dict[str, pg.PlotDataItem] | None = None
    annotation_items: dict[str, TabletAnnotationItem] | None = None
    lithology_items: dict[str, pg.BarGraphItem] | None = None
    lithology_label_items: dict[str, pg.TextItem] | None = None
    lithology_description_items: dict[str, pg.TextItem] | None = None
    cuttings_items: dict[str, tuple[pg.BarGraphItem, ...]] | None = None
    analysis_items: dict[str, tuple[object, ...]] | None = None
    stratigraphy_items: dict[str, tuple[object, ...]] | None = None
    interpretation_items: dict[str, tuple[object, ...]] | None = None
    interpretation_lanes: dict[str, int] | None = None
    cursor_line: pg.InfiniteLine | None = None
    cursor_label: pg.TextItem | None = None
    interpretation_preview: pg.BarGraphItem | None = None
    lithology_preview: pg.BarGraphItem | None = None
    sample_preview: pg.BarGraphItem | None = None
    stratigraphy_preview: pg.BarGraphItem | None = None
    selection_highlight: pg.BarGraphItem | None = None
    curve_render_keys: dict[str, CurveGeometryKey] | None = None
    relative_fill_items: dict[str, pg.FillBetweenItem] | None = None
    relative_baseline_item: pg.PlotDataItem | None = None
    curve_pencil_preview: pg.PlotDataItem | None = None
    curve_pencil_badge: QLabel | None = None
    curve_pencil_readout: QLabel | None = None
    analysis_region: pg.LinearRegionItem | None = None


@dataclass(frozen=True, slots=True)
class _QtPointerPayload:
    plot: pg.PlotWidget | None
    event: QMouseEvent | QKeyEvent


@dataclass(frozen=True, slots=True)
class _CurvePencilPoint:
    axis_value: float
    source_value: float
    display_x: float


@dataclass(slots=True)
class _LithologyGesture:
    track_id: str
    start_depth: float
    current_depth: float


@dataclass(slots=True)
class _SampleGesture:
    track_id: str
    start_depth: float
    current_depth: float


@dataclass(slots=True)
class _StratigraphyGesture:
    track_id: str
    start_depth: float
    current_depth: float


@dataclass(slots=True)
class _AnalysisIntervalGesture:
    track_id: str
    start_value: float
    current_value: float


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


class EngineeringGridAxisItem(pg.AxisItem):
    """Axis with stable major/minor engineering divisions for screen and export.

    PyQtGraph's automatic density changes with widget size.  That is useful for
    exploratory charts, but neighbouring well-log tracks must keep coincident
    grid lines.  The configured divisions are therefore calculated from the
    current visible range, which also keeps all tracks aligned while zooming.
    """

    def __init__(self, orientation: str) -> None:
        super().__init__(orientation=orientation)
        self._major_divisions = 5
        self._minor_divisions = 5

    def set_engineering_divisions(self, major: int, minor: int) -> None:
        self._major_divisions = max(1, int(major))
        self._minor_divisions = max(1, int(minor))
        self.setStyle(maxTickLevel=1 if self._minor_divisions > 1 else 0)
        self.picture = None
        self.update()

    def tickSpacing(self, minVal, maxVal, size):  # type: ignore[override]
        span = abs(float(maxVal) - float(minVal))
        if not np.isfinite(span) or span <= 0.0:
            return super().tickSpacing(minVal, maxVal, size)
        origin = min(float(minVal), float(maxVal))
        major_spacing = span / self._major_divisions
        levels = [(major_spacing, origin)]
        if self._minor_divisions > 1:
            levels.append((major_spacing / self._minor_divisions, origin))
        return levels


class TabletVerticalAxisItem(EngineeringGridAxisItem):
    """Readable vertical labels for depth, relative time and absolute timestamps."""

    def __init__(self, descriptor: VerticalAxisDescriptor) -> None:
        super().__init__("left")
        self.descriptor = descriptor

    def tickStrings(self, values, scale, spacing):  # type: ignore[override]
        if self.descriptor.is_datetime:
            return [self._format_datetime(float(value), float(spacing)) for value in values]
        if self.descriptor.is_time:
            return [self._format_relative_time(float(value)) for value in values]
        return [f"{float(value):g}" for value in values]

    @staticmethod
    def _format_datetime(value: float, spacing: float) -> str:
        rendered = format_unix_seconds(value)
        if rendered == "—":
            return ""
        absolute_spacing = abs(spacing)
        if absolute_spacing >= 86_400:
            return rendered[:10]
        if absolute_spacing >= 60:
            return rendered[:16]
        return rendered[11:19]

    def _format_relative_time(self, value: float) -> str:
        rendered = format_elapsed_time(value, self.descriptor.unit)
        return "" if rendered == "—" else rendered


class CurveHeaderLabel(QLabel):
    clicked = Signal(str)
    context_requested = Signal(str, QPoint)

    def __init__(self, mnemonic: str, text: str, color: str) -> None:
        super().__init__(text)
        self.mnemonic = mnemonic
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setToolTip(f"{text.replace(chr(10), ' · ')} [{mnemonic}]")
        self.setMinimumHeight(46)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._color = color
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        background = "#dbeafe" if selected else "#ffffff"
        border = "#2563eb" if selected else "#e2e8f0"
        self.setStyleSheet(
            f"QLabel {{ background: {background}; color: #0f172a; "
            f"border-left: 5px solid {self._color}; border-bottom: 1px solid {border}; "
            "padding: 2px 4px; font-size: 11px; font-weight: 600; } "
            "QLabel:hover { background: #eff6ff; }"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mnemonic)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(self.mnemonic, event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)


class TabletTrackWidget(QFrame):
    selected = Signal(str)
    width_change_requested = Signal(str, int)
    header_drag_started = Signal(str, int)
    header_drag_moved = Signal(str, int)
    header_drag_finished = Signal(str, int)
    context_requested = Signal(str, QPoint)
    edit_requested = Signal(str)
    curve_selected = Signal(str, str)
    curve_context_requested = Signal(str, str, QPoint)

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
        self._header_drag_origin_x: int | None = None
        self._header_dragging = False
        self._curve_header_labels: dict[str, CurveHeaderLabel] = {}
        self._natural_curve_header_height = 0
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

        self.title = OrientedTextLabel(
            definition.title,
            orientation=definition.title_orientation,
            position=definition.title_position,
        )
        self.title.setStyleSheet(
            "font-weight: 600; padding: 6px; "
            "background: #f8fafc; color: #0f172a; "
            "border-bottom: 1px solid #cbd5e1;"
        )
        self.title.setFixedHeight(88 if definition.title_orientation != "horizontal" else 36)

        self.curve_header = QWidget()
        self.curve_header.setObjectName("tablet-curve-header-content")
        self.curve_header.setStyleSheet("background:#ffffff;")
        self.curve_header_layout = QVBoxLayout(self.curve_header)
        self.curve_header_layout.setContentsMargins(0, 0, 0, 0)
        self.curve_header_layout.setSpacing(0)
        self.curve_header_scroll = QScrollArea()
        self.curve_header_scroll.setWidgetResizable(True)
        self.curve_header_scroll.setWidget(self.curve_header)
        self.curve_header_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.curve_header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.curve_header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.curve_header_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        # The application uses a dark global palette.  QScrollArea viewports do
        # not inherit the white TabletTrackWidget background reliably, so empty
        # synchronized header bands appeared as large black rectangles in
        # lithology, cuttings, text and gas columns.  Keep the common header
        # geometry, but paint every part of the band explicitly as paper-white.
        self.curve_header_scroll.setStyleSheet(
            "QScrollArea {background:#ffffff; border:0;} "
            "QScrollArea QWidget#qt_scrollarea_viewport {background:#ffffff;} "
            "QScrollBar:vertical {width:8px;}"
        )
        self.curve_header_scroll.viewport().setStyleSheet("background:#ffffff;")
        self.curve_header_scroll.hide()

        axis_items: dict[str, pg.AxisItem] = {
            "bottom": EngineeringGridAxisItem("bottom"),
            "left": (
                TabletVerticalAxisItem(vertical_axis)
                if vertical_axis is not None
                else EngineeringGridAxisItem("left")
            ),
        }
        self.plot = pg.PlotWidget(axisItems=axis_items)
        self.plot.setBackground("#ffffff")
        self.plot.setMinimumHeight(240)
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for axis_name in ("left", "bottom"):
            axis = self.plot.getAxis(axis_name)
            axis.setPen(pg.mkPen("#475569"))
            axis.setTextPen(pg.mkPen("#334155"))
            if isinstance(axis, EngineeringGridAxisItem):
                axis.set_engineering_divisions(
                    definition.grid_major_divisions,
                    definition.grid_minor_divisions,
                )
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
        self.set_track_width(display_width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title)
        layout.addWidget(self.curve_header_scroll)
        layout.addWidget(self.plot, 1)

        for target in (self.title, self.plot, self.plot.viewport()):
            target.setMouseTracking(True)
            target.installEventFilter(self)

    def set_curve_headers(self, rows: list[tuple[str, str, str]]) -> None:
        self._curve_header_labels.clear()
        while self.curve_header_layout.count():
            item = self.curve_header_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        for mnemonic, text, color in rows:
            label = CurveHeaderLabel(mnemonic, text, color)
            label.clicked.connect(
                lambda selected, track_id=self.definition.track_id: self.curve_selected.emit(
                    track_id, selected
                )
            )
            label.context_requested.connect(
                lambda selected, pos, track_id=self.definition.track_id: (
                    self.curve_context_requested.emit(track_id, selected, pos)
                )
            )
            self._curve_header_labels[mnemonic] = label
            self.curve_header_layout.addWidget(label)
        # The natural height is used by TabletView to reserve one common
        # parameter-header band for every column.  Without that common band,
        # tracks with three curve captions and tracks without captions start
        # their PlotWidget at different Y pixels even though their numeric
        # depth ranges are identical.
        self._natural_curve_header_height = min(320, max(0, len(rows) * 48))
        self.curve_header_scroll.setMaximumHeight(self._natural_curve_header_height)
        self.curve_header_scroll.setVisible(bool(rows))

    @property
    def natural_title_header_height(self) -> int:
        return 88 if self.definition.title_orientation != "horizontal" else 36

    def set_synchronized_title_header_height(self, height: int) -> None:
        self.title.setFixedHeight(max(36, int(height)))

    @property
    def natural_curve_header_height(self) -> int:
        return self._natural_curve_header_height

    def set_synchronized_header_height(self, height: int) -> None:
        """Reserve the same header band above every plot in the form."""

        normalized = max(0, int(height))
        self.curve_header_scroll.setVisible(normalized > 0)
        self.curve_header_scroll.setMinimumHeight(normalized)
        self.curve_header_scroll.setMaximumHeight(normalized)
        self.curve_header_scroll.setFixedHeight(normalized)

    def set_selected_curve(self, mnemonic: str | None) -> None:
        for key, label in self._curve_header_labels.items():
            label.set_selected(key == mnemonic)

    def set_pencil_active(self, active: bool) -> None:
        """Make the active pencil target unmistakable in wide Masterlog forms."""

        text = self.title.text().removeprefix("✎ ")
        self.title.setText(f"✎ {text}" if active else text)
        if active:
            self.title.setStyleSheet(
                "font-weight:700; padding:6px; background:#ffedd5; color:#9a3412; "
                "border:2px solid #f97316;"
            )
        else:
            self.title.setStyleSheet(
                "font-weight:600; padding:6px; background:#f8fafc; color:#0f172a; "
                "border-bottom:1px solid #cbd5e1;"
            )

    def set_track_width(self, width: int) -> None:
        self.setFixedWidth(int(width))
        if self.definition.kind is TrackKind.DEPTH:
            axis = self.plot.getAxis("left")
            axis_width = max(54, min(int(width) - 12, 92))
            axis.setStyle(
                autoExpandTextSpace=False,
                tickTextWidth=max(48, min(int(width) - 16, 88)),
                tickLength=-6,
            )
            axis.setWidth(axis_width)

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
        if isinstance(event, QMouseEvent):
            if (
                watched is self.title
                and event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.RightButton
            ):
                self.context_requested.emit(
                    self.definition.track_id, event.globalPosition().toPoint()
                )
                return True
            if self._handle_resize_event(event, watched):
                return True
        if watched is self.title and isinstance(event, QMouseEvent):
            global_x = event.globalPosition().toPoint().x()
            if (
                event.type() == QEvent.Type.MouseButtonDblClick
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._header_drag_origin_x = None
                self._header_dragging = False
                self.selected.emit(self.definition.track_id)
                self.edit_requested.emit(self.definition.track_id)
                event.accept()
                return True
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._header_drag_origin_x = global_x
                self._header_dragging = False
                return False
            if event.type() == QEvent.Type.MouseMove and self._header_drag_origin_x is not None:
                if not self._header_dragging and abs(global_x - self._header_drag_origin_x) >= 8:
                    self._header_dragging = True
                    self.header_drag_started.emit(
                        self.definition.track_id, self._header_drag_origin_x
                    )
                if self._header_dragging:
                    self.header_drag_moved.emit(self.definition.track_id, global_x)
                    return True
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
            ):
                was_dragging = self._header_dragging
                self._header_drag_origin_x = None
                self._header_dragging = False
                if was_dragging:
                    self.header_drag_finished.emit(self.definition.track_id, global_x)
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
            self.set_track_width(width)
            return True
        if (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._resize_gesture is not None
        ):
            width = self._resize_gesture.width_at(global_position.x())
            self._resize_gesture = None
            self.set_track_width(width)
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
    track_order_change_requested = Signal(str, int)
    curve_selected = Signal(str, str)
    track_hide_requested = Signal(str)
    track_remove_requested = Signal(str)
    track_add_curves_requested = Signal(str)
    track_replace_curves_requested = Signal(str)
    track_properties_requested = Signal(str)
    track_full_edit_requested = Signal(str)
    track_rename_requested = Signal(str)
    track_group_rename_requested = Signal(str)
    track_curve_settings_requested = Signal(str, str)
    curve_pencil_requested = Signal(str, str)
    curve_edit_requested = Signal(str, object, object)
    curve_pencil_mode_changed = Signal(bool, str)
    curve_pencil_undo_requested = Signal()
    curve_pencil_redo_requested = Signal()
    save_layout_requested = Signal()
    visible_depth_changed = Signal(float, float)
    vertical_index_changed = Signal(str)
    cursor_changed = Signal(float, str)
    interpretation_selected = Signal(str)
    interval_selected = Signal(str, str)
    interval_selection_cleared = Signal()
    interval_create_requested = Signal(str, float, float, str)
    interval_resize_requested = Signal(str, str, float, float)
    interval_interaction_cancelled = Signal()
    lithology_interval_requested = Signal(float, float)
    lithology_interval_edit_requested = Signal(str)
    cuttings_interval_requested = Signal(float, float)
    cuttings_sample_edit_requested = Signal(str)
    description_interval_requested = Signal(float, float)
    description_edit_requested = Signal(str)
    stratigraphy_interval_requested = Signal(float, float)
    stratigraphy_interval_edit_requested = Signal(str)
    annotation_add_requested = Signal(object)
    annotation_edit_requested = Signal(str)
    annotation_delete_requested = Signal(str)
    annotation_duplicate_requested = Signal(str)
    annotation_geometry_changed = Signal(str, float, float, float, float)
    annotation_selection_changed = Signal(object)
    annotation_tool_changed = Signal(object)
    curve_value_save_requested = Signal(object)
    interval_analysis_requested = Signal(object)
    interval_analysis_cleared = Signal()

    def __init__(self, *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__()
        pg.setConfigOptions(antialias=False)
        self._localizer = Localizer.create(language)
        self._navigation_hint = self._localizer.text("tablet.depth_navigation_hint")
        self._dataset: Dataset | None = None
        self._canvas_objects: tuple[CanvasObject, ...] = ()
        self._image_assets: dict[str, ImageAsset] = {}
        self._annotation_print_mode = False
        self._annotation_tool: AnnotationKind | None = None
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
        self._form_edit_mode = False
        self._selected_track_id: str | None = None
        self._curve_pencil_enabled = False
        self._curve_pencil_track_id: str | None = None
        self._curve_pencil_mnemonic: str | None = None
        self._curve_pencil_curve_id: str | None = None
        self._curve_pencil_points: list[_CurvePencilPoint] = []
        self._curve_pencil_mode = CurvePencilMode.FREEHAND
        self._curve_pencil_commit_ack: bool | None = None
        self._curve_pencil_commit_error = ""
        self._curve_pencil_unsaved = False
        self._curve_pencil_can_undo = False
        self._curve_pencil_can_redo = False
        self._curve_pencil_last_hover: tuple[str, _CurvePencilPoint, QPoint] | None = None
        self._pencil_cursor = self._build_pencil_cursor()
        self._cursor_depth: float | None = None
        self._cursor_guard = False
        self._cursor_color = "#dc2626"
        self._cursor_width = 2.0
        self._depth_viewports: dict[QObject, pg.PlotWidget] = {}
        self._wheel_targets: dict[QObject, pg.PlotWidget] = {}
        self._interpretation_viewports: dict[QObject, RenderedTrack] = {}
        self._interval_edit_mode = IntervalEditMode.SELECT
        self._interval_creation_type = self._localizer.text("interpretations.default_type")
        self._interval_gesture: _IntervalGesture | None = None
        self._lithology_gesture: _LithologyGesture | None = None
        self._sample_gesture: _SampleGesture | None = None
        self._stratigraphy_gesture: _StratigraphyGesture | None = None
        self._analysis_interval_gesture: _AnalysisIntervalGesture | None = None
        self._analysis_interval: tuple[float, float] | None = None
        self._geological_input_mode = GeologicalInputMode.SELECT
        self._axis_combo_guard = False
        self._span_combo_guard = False
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
        self._header_drag: TrackHeaderDrag | None = None
        self._tooltip_items: dict[str, pg.TextItem] = {}
        self._rubber_band_items: dict[str, pg.BarGraphItem] = {}

        # One scrollable canvas keeps the depth column in the exact template
        # order.  The previous implementation forcibly detached every depth
        # track and pinned it on the far left, which broke Masterlog layouts
        # where depth belongs in the middle and made group headers impossible.
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        self._group_header_container = QWidget()
        self._group_header_layout = QHBoxLayout(self._group_header_container)
        self._group_header_layout.setContentsMargins(0, 0, 0, 0)
        self._group_header_layout.setSpacing(2)
        self._group_header_container.setFixedHeight(30)
        self._group_header_container.hide()

        self._tracks_container = QWidget()
        self._tracks_layout = QHBoxLayout(self._tracks_container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(2)
        self._tracks_container.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding
        )
        self._annotation_overlay = TabletAnnotationOverlay(self._tracks_container)
        self._annotation_overlay.setGeometry(self._tracks_container.rect())
        self._annotation_overlay.edit_requested.connect(self.annotation_edit_requested.emit)
        self._annotation_overlay.delete_requested.connect(self.annotation_delete_requested.emit)
        self._annotation_overlay.duplicate_requested.connect(
            self.annotation_duplicate_requested.emit
        )
        self._annotation_overlay.selection_changed.connect(
            self.annotation_selection_changed.emit
        )

        # All edit gestures pass through one OOP router.  The paint overlay is
        # permanently mouse-transparent and can no longer block track menus or
        # remain in a stale native mouse-grab state.
        self._interaction_router = TabletInteractionRouter()
        self._annotation_interaction = AnnotationInteractionHandler(
            self._annotation_overlay,
            create_requested=self._create_annotation_from_input,
            edit_requested=self.annotation_edit_requested.emit,
            delete_requested=self.annotation_delete_requested.emit,
            context_requested=self._show_annotation_context_from_input,
            geometry_changed=self._commit_annotation_geometry,
            creation_tool_cancelled=lambda: self.set_annotation_tool(None),
        )
        self._track_edit_interaction = TrackEditInteractionHandler(
            select_track=self._select_track_from_interaction,
            edit_track=self.track_full_edit_requested.emit,
            can_edit_track=self._track_is_directly_editable,
        )
        self._interaction_router.register(self._annotation_interaction)
        self._interaction_router.register(self._track_edit_interaction)
        self._edit_mode_coordinator = TabletEditModeCoordinator(
            self._annotation_interaction,
            self._track_edit_interaction,
        )
        self._interaction_watchdog = TabletInteractionWatchdog(
            self._interaction_router,
            self._recover_lost_pointer_release,
            self,
        )
        self._container_layout.addWidget(self._group_header_container)
        self._container_layout.addWidget(self._tracks_container, 1)
        self._container.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding
        )

        self._scroll = QScrollArea()
        # A visible QScrollArea frame consumes pixels around the common canvas.
        # Masterlog columns must share one pixel-exact vertical origin, so the
        # scroll frame is intentionally disabled.
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        # The tracks must always consume the full available vertical viewport.
        # Horizontal overflow is still handled by the scroll bar because the
        # container keeps a fixed content width.
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._container)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Wheel events can land on the empty gaps between columns or on the common
        # viewport itself. Route those areas through the same depth camera too.
        self._scroll.viewport().installEventFilter(self)
        self._tracks_container.installEventFilter(self)
        self._group_header_container.installEventFilter(self)

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
        self._span_combo = QComboBox()
        self._span_combo.setMinimumWidth(132)
        self._span_combo.setEditable(True)
        self._span_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for span in DEPTH_VIEW_SPAN_PRESETS:
            self._span_combo.addItem(f"{span:g} {self._vertical_span_unit()}", span)
        self._span_combo.addItem(self._localizer.text("tablet.depth_span_custom"), None)
        # currentIndexChanged is intentional here.  The former ``activated``
        # connection only committed a preset after a very specific mouse/keyboard
        # activation path.  On an editable combo box the displayed value could
        # therefore change while the graph kept the old vertical interval.
        self._span_combo.currentIndexChanged.connect(self._depth_span_selected)
        self._span_edit_timer = QTimer(self)
        self._span_edit_timer.setSingleShot(True)
        self._span_edit_timer.setInterval(180)
        self._span_edit_timer.timeout.connect(self._depth_span_typed)
        self._resize_restore_timer = QTimer(self)
        self._resize_restore_timer.setSingleShot(True)
        self._resize_restore_timer.timeout.connect(self._restore_visible_depth_after_resize)
        span_line_edit = self._span_combo.lineEdit()
        if span_line_edit is not None:
            span_line_edit.returnPressed.connect(self._depth_span_typed)
            span_line_edit.editingFinished.connect(self._depth_span_typed)
            # Apply a valid manually typed value automatically after a very short
            # editing pause.  Applying on every keystroke made ``30`` become ``3``
            # because the control synchronized itself after the first character.
            span_line_edit.textEdited.connect(self._depth_span_text_edited)
        self._span_combo.setToolTip(self._localizer.text("tablet.depth_span_tooltip"))

        navigation = QHBoxLayout()
        navigation.setContentsMargins(6, 4, 6, 4)
        self._vertical_axis_label = QLabel(self._localizer.text("tablet.vertical_axis"))
        navigation.addWidget(self._vertical_axis_label)
        navigation.addWidget(self._axis_combo)
        navigation.addWidget(self._range_label, 1)
        navigation.addWidget(self._goto_value)
        navigation.addWidget(self._goto_button)
        navigation.addWidget(self._zoom_in_button)
        navigation.addWidget(self._zoom_out_button)
        self._depth_span_label = QLabel(self._localizer.text("tablet.depth_span"))
        navigation.addWidget(self._depth_span_label)
        navigation.addWidget(self._span_combo)
        navigation.addWidget(self._full_range_button)
        self._navigation_help_label = QLabel(self._navigation_hint)
        self._navigation_help_label.setStyleSheet("color: #64748b; font-size: 10px;")
        self._navigation_help_label.setToolTip(self._navigation_hint)
        navigation.addWidget(self._navigation_help_label)

        self._navigation_bar = QFrame()
        self._navigation_bar.setLayout(navigation)
        self._navigation_scroll = QScrollArea()
        self._navigation_scroll.setObjectName("tabletNavigationScroll")
        self._navigation_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._navigation_scroll.setWidgetResizable(True)
        self._navigation_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._navigation_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._navigation_scroll.setWidget(self._navigation_bar)
        self._navigation_scroll.setMinimumWidth(0)
        navigation_height = (
            self._navigation_bar.sizeHint().height()
            + self._navigation_scroll.horizontalScrollBar().sizeHint().height()
        )
        self._navigation_scroll.setFixedHeight(navigation_height)

        self._curve_pencil_bar = QFrame()
        self._curve_pencil_bar.setObjectName("tabletCurvePencilBar")
        pencil_layout = QHBoxLayout(self._curve_pencil_bar)
        pencil_layout.setContentsMargins(6, 4, 6, 4)
        pencil_layout.setSpacing(6)
        self._curve_pencil_button = QPushButton(self._localizer.text("tablet.curve_pencil_button"))
        self._curve_pencil_button.setCheckable(True)
        self._curve_pencil_button.setToolTip(self._localizer.text("tablet.curve_pencil_tooltip"))
        self._curve_pencil_button.toggled.connect(self._tablet_pencil_button_toggled)
        pencil_layout.addWidget(self._curve_pencil_button)
        self._curve_pencil_mode_label = QLabel(self._localizer.text("tablet.curve_pencil_mode"))
        self._curve_pencil_mode_label.hide()
        self._curve_pencil_mode_selector = QComboBox()
        self._curve_pencil_mode_selector.addItem(
            self._localizer.text("tablet.curve_pencil_mode_freehand"),
            CurvePencilMode.FREEHAND.value,
        )
        self._curve_pencil_mode_selector.addItem(
            self._localizer.text("tablet.curve_pencil_mode_points"),
            CurvePencilMode.CONNECT_POINTS.value,
        )
        self._curve_pencil_mode_selector.setToolTip(
            self._localizer.text("tablet.curve_pencil_mode_tooltip")
        )
        self._curve_pencil_mode_selector.currentIndexChanged.connect(
            self._curve_pencil_mode_changed
        )
        # Keep the combo as a compatibility model, but expose the two modes as
        # large, explicit buttons so the point-connection tool cannot disappear
        # in a crowded Masterlog toolbar.
        self._curve_pencil_mode_selector.hide()
        self._curve_pencil_freehand_button = QPushButton(
            self._localizer.text("tablet.curve_pencil_mode_freehand_button")
        )
        self._curve_pencil_freehand_button.setCheckable(True)
        self._curve_pencil_freehand_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_mode_tooltip")
        )
        self._curve_pencil_freehand_button.clicked.connect(
            lambda _checked=False: self._select_curve_pencil_mode(CurvePencilMode.FREEHAND)
        )
        pencil_layout.addWidget(self._curve_pencil_freehand_button)
        self._curve_pencil_points_button = QPushButton(
            self._localizer.text("tablet.curve_pencil_mode_points_button")
        )
        self._curve_pencil_points_button.setCheckable(True)
        self._curve_pencil_points_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_mode_tooltip")
        )
        self._curve_pencil_points_button.clicked.connect(
            lambda _checked=False: self._select_curve_pencil_mode(CurvePencilMode.CONNECT_POINTS)
        )
        pencil_layout.addWidget(self._curve_pencil_points_button)
        self._curve_pencil_target_label = QLabel(self._localizer.text("tablet.curve_pencil_target"))
        pencil_layout.addWidget(self._curve_pencil_target_label)
        self._curve_pencil_selector = QComboBox()
        self._curve_pencil_selector.setMinimumWidth(280)
        self._curve_pencil_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._curve_pencil_selector.setMinimumContentsLength(28)
        self._curve_pencil_selector.setToolTip(
            self._localizer.text("tablet.curve_pencil_selector_tooltip")
        )
        self._curve_pencil_selector.currentIndexChanged.connect(self._curve_pencil_target_changed)
        pencil_layout.addWidget(self._curve_pencil_selector, 1)
        self._curve_pencil_apply_button = QPushButton(
            self._localizer.text("tablet.curve_pencil_apply_points")
        )
        self._curve_pencil_apply_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_apply_points_tooltip")
        )
        self._curve_pencil_apply_button.clicked.connect(self._apply_curve_pencil_points)
        pencil_layout.addWidget(self._curve_pencil_apply_button)
        self._curve_pencil_clear_button = QPushButton(
            self._localizer.text("tablet.curve_pencil_clear_points")
        )
        self._curve_pencil_clear_button.clicked.connect(self.cancel_curve_pencil_gesture)
        pencil_layout.addWidget(self._curve_pencil_clear_button)
        self._curve_pencil_undo_button = QPushButton(
            self._localizer.text("tablet.curve_pencil_undo")
        )
        self._curve_pencil_undo_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_undo_tooltip")
        )
        self._curve_pencil_undo_button.clicked.connect(
            lambda _checked=False: self.curve_pencil_undo_requested.emit()
        )
        pencil_layout.addWidget(self._curve_pencil_undo_button)
        self._curve_pencil_redo_button = QPushButton(
            self._localizer.text("tablet.curve_pencil_redo")
        )
        self._curve_pencil_redo_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_redo_tooltip")
        )
        self._curve_pencil_redo_button.clicked.connect(
            lambda _checked=False: self.curve_pencil_redo_requested.emit()
        )
        pencil_layout.addWidget(self._curve_pencil_redo_button)
        self._curve_pencil_status = QLabel(self._localizer.text("tablet.curve_pencil_inactive"))
        self._curve_pencil_status.setMinimumWidth(180)
        self._curve_pencil_status.setToolTip(self._localizer.text("tablet.curve_pencil_tooltip"))
        pencil_layout.addWidget(self._curve_pencil_status)
        self._update_curve_pencil_bar_style()
        self._update_curve_pencil_mode_controls()
        self.set_curve_pencil_history_state(False, False)

        self._curve_pencil_scroll = QScrollArea()
        self._curve_pencil_scroll.setObjectName("tabletCurvePencilScroll")
        self._curve_pencil_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._curve_pencil_scroll.setWidgetResizable(True)
        self._curve_pencil_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._curve_pencil_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._curve_pencil_scroll.setWidget(self._curve_pencil_bar)
        self._curve_pencil_scroll.setMinimumWidth(0)
        pencil_height = (
            self._curve_pencil_bar.sizeHint().height()
            + self._curve_pencil_scroll.horizontalScrollBar().sizeHint().height()
        )
        self._curve_pencil_scroll.setFixedHeight(pencil_height)

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
        charts.addWidget(self._scroll, 1)
        charts.addWidget(self._mini_map, 0)
        charts.addWidget(self._vertical_scrollbar)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._navigation_scroll)
        root.addWidget(self._curve_pencil_scroll)
        root.addLayout(charts, 1)

    def set_language(self, language: AppLanguage) -> None:
        previous_localizer = self._localizer
        previous_default_type = previous_localizer.text("interpretations.default_type")
        current_span_data = self._span_combo.currentData()
        current_span_text = self._span_combo.currentText()

        self._localizer = Localizer.create(language)
        self._navigation_hint = self._localizer.text("tablet.depth_navigation_hint")
        self._navigation_help_label.setText(self._navigation_hint)
        self._navigation_help_label.setToolTip(self._navigation_hint)
        if self._interval_creation_type == previous_default_type:
            self._interval_creation_type = self._localizer.text("interpretations.default_type")

        self._vertical_axis_label.setText(self._localizer.text("tablet.vertical_axis"))
        self._goto_button.setText(self._localizer.text("tablet.goto"))
        self._zoom_in_button.setToolTip(self._localizer.text("tablet.zoom_in"))
        self._zoom_out_button.setToolTip(self._localizer.text("tablet.zoom_out"))
        self._full_range_button.setText(self._localizer.text("tablet.full_range"))
        self._depth_span_label.setText(self._localizer.text("tablet.depth_span"))
        self._curve_pencil_button.setText(self._localizer.text("tablet.curve_pencil_button"))
        self._curve_pencil_button.setToolTip(self._localizer.text("tablet.curve_pencil_tooltip"))
        self._curve_pencil_mode_label.setText(self._localizer.text("tablet.curve_pencil_mode"))
        self._curve_pencil_mode_selector.setItemText(
            0, self._localizer.text("tablet.curve_pencil_mode_freehand")
        )
        self._curve_pencil_mode_selector.setItemText(
            1, self._localizer.text("tablet.curve_pencil_mode_points")
        )
        self._curve_pencil_freehand_button.setText(
            self._localizer.text("tablet.curve_pencil_mode_freehand_button")
        )
        self._curve_pencil_freehand_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_mode_tooltip")
        )
        self._curve_pencil_points_button.setText(
            self._localizer.text("tablet.curve_pencil_mode_points_button")
        )
        self._curve_pencil_points_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_mode_tooltip")
        )
        self._curve_pencil_mode_selector.setToolTip(
            self._localizer.text("tablet.curve_pencil_mode_tooltip")
        )
        self._curve_pencil_apply_button.setText(
            self._localizer.text("tablet.curve_pencil_apply_points")
        )
        self._curve_pencil_undo_button.setText(
            self._localizer.text("tablet.curve_pencil_undo")
        )
        self._curve_pencil_redo_button.setText(
            self._localizer.text("tablet.curve_pencil_redo")
        )
        self._curve_pencil_undo_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_undo_tooltip")
        )
        self._curve_pencil_redo_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_redo_tooltip")
        )
        self._curve_pencil_apply_button.setToolTip(
            self._localizer.text("tablet.curve_pencil_apply_points_tooltip")
        )
        self._curve_pencil_clear_button.setText(
            self._localizer.text("tablet.curve_pencil_clear_points")
        )
        self._curve_pencil_target_label.setText(self._localizer.text("tablet.curve_pencil_target"))
        self._curve_pencil_selector.setToolTip(
            self._localizer.text("tablet.curve_pencil_selector_tooltip")
        )
        self._curve_pencil_status.setToolTip(self._localizer.text("tablet.curve_pencil_tooltip"))
        self._update_curve_pencil_status()

        self._span_combo.blockSignals(True)
        try:
            self._span_combo.clear()
            for span in DEPTH_VIEW_SPAN_PRESETS:
                self._span_combo.addItem(
                    f"{span:g} {self._vertical_span_unit()}",
                    span,
                )
            self._span_combo.addItem(
                self._localizer.text("tablet.depth_span_custom"),
                None,
            )
            selected_row = self._span_combo.findData(current_span_data)
            if selected_row >= 0:
                self._span_combo.setCurrentIndex(selected_row)
            elif current_span_text:
                self._span_combo.setEditText(current_span_text)
        finally:
            self._span_combo.blockSignals(False)
        self._span_combo.setToolTip(self._localizer.text("tablet.depth_span_tooltip"))

        cursor_depth = self._cursor_depth
        self.refresh_view()
        if cursor_depth is not None and self._dataset is not None:
            self.set_cursor_depth(cursor_depth)
        self._update_navigation_controls()

    @property
    def layout_model(self) -> TabletLayout:
        return self._layout_model

    def printable_tracks(self) -> tuple[RenderedTrack, ...]:
        """Return every currently rendered visible track in form order.

        Printing must not use the horizontal scroll viewport because it clips
        columns located outside the screen.  This method exposes the complete
        rendered form while keeping the internal mapping private.
        """

        return tuple(
            rendered
            for definition in self._layout_model.visible_tracks()
            if (rendered := self._rendered.get(definition.track_id)) is not None
        )

    @property
    def vertical_index_id(self) -> str | None:
        index = self._vertical_index()
        return index.index_id if index is not None else None

    @property
    def vertical_axis_is_time(self) -> bool:
        index = self._vertical_index()
        return index is not None and index.role is IndexRole.TIME

    def printable_vertical_range(self) -> tuple[float, float] | None:
        """Return the complete active depth/time domain for paged printing."""

        return self._axis_bounds()

    @property
    def printable_vertical_unit(self) -> str:
        descriptor = self._axis_descriptor()
        return descriptor.unit if descriptor is not None else ""

    @property
    def printable_vertical_label(self) -> str:
        descriptor = self._axis_descriptor()
        return descriptor.label if descriptor is not None else self._localizer.text("print.depth")

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
            for mnemonic in rendered.curve_items or {}:
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

    @property
    def group_header_titles(self) -> tuple[str, ...]:
        """Return merged visible form-section captions in screen order."""
        titles: list[str] = []
        for index in range(self._group_header_layout.count()):
            item = self._group_header_layout.itemAt(index)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel):
                titles.append(label.text().strip())
        return tuple(titles)

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
        annotation_ids: list[str] = []
        visible_ids = set(self._annotation_overlay.annotation_ids)
        for canvas_item in self._canvas_objects:
            if not is_annotation_object(canvas_item):
                continue
            record = annotation_from_canvas(canvas_item)
            if record.annotation_id not in visible_ids:
                continue
            target = self._annotation_target_track(record)
            if target is rendered:
                annotation_ids.append(record.annotation_id)
        return tuple(annotation_ids)

    def rendered_annotation_item(
        self, annotation_id: str
    ) -> TabletAnnotationItem | None:
        return self._annotation_overlay.annotation_item(annotation_id)

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

    @property
    def lithology_preview_range(self) -> tuple[float, float] | None:
        preview = self._lithology_gesture_result()
        if preview is None:
            return None
        return preview.top_depth, preview.bottom_depth

    @property
    def sample_preview_range(self) -> tuple[float, float] | None:
        gesture = self._sample_gesture
        if gesture is None:
            return None
        preview = normalize_drag_range(
            gesture.start_depth,
            gesture.current_depth,
            minimum_span=self._minimum_depth_span(),
        )
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
            requested = (
                self._interpretations[0].interpretation_id if self._interpretations else None
            )
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
            self._apply_curve_selection_style()
            if emit_signal:
                self.selection_changed.emit(self._selection.snapshot())
                self.track_selected.emit(track_id)
        return changed

    def select_curve(
        self,
        track_id: str,
        mnemonic: str,
        *,
        additive: bool = False,
        toggle: bool = False,
        emit_signal: bool = True,
    ) -> bool:
        try:
            definition = self._layout_model.track_by_id(track_id)
        except KeyError:
            return False
        if mnemonic not in definition.curve_mnemonics:
            return False
        changed = self._selection.select(
            SelectionRef(SelectableKind.CURVE, mnemonic, track_id),
            additive=additive,
            toggle=toggle,
        )
        if changed:
            self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
            self._apply_curve_selection_style()
            if emit_signal:
                self.selection_changed.emit(self._selection.snapshot())
                self.curve_selected.emit(track_id, mnemonic)
        return changed

    def clear_selection(self, *, emit_signal: bool = True) -> bool:
        changed = self._selection.clear()
        interval_changed = self._selected_interval_id is not None
        self._selected_interval_id = None
        if changed or interval_changed:
            self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
            self._apply_track_selection_style()
            self._apply_curve_selection_style()
            self._apply_interpretation_selection_style()
            if emit_signal:
                self.selection_changed.emit(self._selection.snapshot())
        return changed or interval_changed

    def _track_selected_from_widget(self, track_id: str) -> None:
        self._selected_track_id = track_id
        modifiers = QApplication.keyboardModifiers()
        additive = bool(
            modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        )
        toggle = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        self.select_track(track_id, additive=additive, toggle=toggle, emit_signal=True)

    @property
    def can_undo_interaction(self) -> bool:
        return self._interaction_history.can_undo

    @property
    def can_redo_interaction(self) -> bool:
        return self._interaction_history.can_redo

    def undo_interaction(self) -> bool:
        return self._interaction_history.undo()

    def redo_interaction(self) -> bool:
        return self._interaction_history.redo()

    def _resize_track_from_widget(self, track_id: str, new_width: int) -> None:
        try:
            definition = self._layout_model.track_by_id(track_id)
        except KeyError:
            return
        old_width = definition.width
        if old_width == new_width:
            return

        def apply(width: int) -> None:
            definition.width = width
            rendered = self._rendered.get(track_id)
            if rendered is not None:
                rendered.widget.set_track_width(width)
            total_width = sum(track.width + 2 for track in self._layout_model.visible_tracks())
            self._container.setFixedWidth(max(total_width, 1))
            self._tracks_container.setFixedWidth(max(total_width, 1))
            self._rebuild_group_headers()
            self.invalidate_track(track_id, DirtyReason.STATIC)
            self.refresh_dirty_tracks()
            self.track_width_change_requested.emit(track_id, width)

        self._interaction_history.execute(
            CallbackCommand(
                description=f"resize track {track_id}",
                _redo_callback=lambda: apply(new_width),
                _undo_callback=lambda: apply(old_width),
            )
        )

    def _start_track_header_drag(self, track_id: str, global_x: int) -> None:
        try:
            source_index = self._layout_model.tracks.index(self._layout_model.track_by_id(track_id))
        except (KeyError, ValueError):
            return
        self._header_drag = TrackHeaderDrag(track_id, source_index, global_x)
        self.select_track(track_id, emit_signal=True)

    def _move_track_header_drag(self, track_id: str, global_x: int) -> None:
        if self._header_drag is None or self._header_drag.track_id != track_id:
            return
        rendered = self._rendered.get(track_id)
        if rendered is not None:
            rendered.widget.title.setStyleSheet(
                rendered.widget.title.styleSheet() + " background: #dbeafe;"
            )

    def _track_center_positions(
        self, *, exclude_track_id: str | None = None
    ) -> tuple[tuple[int, int], ...]:
        centers: list[tuple[int, int]] = []
        for layout_index, definition in enumerate(self._layout_model.tracks):
            if definition.track_id == exclude_track_id or definition.kind is TrackKind.DEPTH:
                continue
            rendered = self._rendered.get(definition.track_id)
            if rendered is None:
                continue
            widget = rendered.widget
            center_x = widget.mapToGlobal(QPoint(widget.width() // 2, 0)).x()
            centers.append((layout_index, center_x))
        return tuple(centers)

    def _finish_track_header_drag(self, track_id: str, global_x: int) -> None:
        gesture = self._header_drag
        self._header_drag = None
        if gesture is None or gesture.track_id != track_id:
            return
        target_index = gesture.target_index(
            global_x, self._track_center_positions(exclude_track_id=track_id)
        )
        if target_index == gesture.source_index:
            self._apply_track_selection_style()
            return

        self.move_track_with_history(track_id, target_index, source_index=gesture.source_index)

    def move_track_with_history(
        self, track_id: str, target_index: int, *, source_index: int | None = None
    ) -> bool:
        try:
            definition = self._layout_model.track_by_id(track_id)
            current_index = self._layout_model.tracks.index(definition)
        except (KeyError, ValueError):
            return False
        original_index = current_index if source_index is None else source_index
        bounded_target = max(0, min(int(target_index), len(self._layout_model.tracks) - 1))
        if bounded_target == current_index:
            return False

        def move(index: int) -> None:
            self._layout_model.move_track(track_id, index)
            self.refresh_view()
            self.select_track(track_id, emit_signal=False)
            self.track_order_change_requested.emit(track_id, index)

        self._interaction_history.execute(
            CallbackCommand(
                description=f"move track {track_id}",
                _redo_callback=lambda: move(bounded_target),
                _undo_callback=lambda: move(original_index),
            )
        )
        return True

    def hit_test_header(self, track_id: str, local_x: float, local_y: float) -> HitResult | None:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            return None
        title = rendered.widget.title
        if 0.0 <= local_x <= title.width() and 0.0 <= local_y <= title.height():
            return HitResult(
                target=SelectionRef(SelectableKind.TRACK, track_id, track_id),
                priority=100,
                distance_px=0.0,
                local_x=float(local_x),
                local_y=float(local_y),
            )
        return None

    def hit_test_curve(
        self, track_id: str, local_x: float, local_y: float, *, tolerance_px: float = 8.0
    ) -> HitResult | None:
        """Return the nearest rendered curve at widget-local coordinates."""

        rendered = self._rendered.get(track_id)
        if rendered is None or rendered.plot is None or not rendered.curve_items:
            return None
        viewport = rendered.plot.viewport()
        scene_point = viewport.mapToGlobal(QPoint(int(local_x), int(local_y)))
        local_to_plot = rendered.plot.mapFromGlobal(scene_point)
        scene_pos = rendered.plot.mapToScene(local_to_plot)
        view_pos = rendered.plot.getViewBox().mapSceneToView(scene_pos)
        hits: list[HitResult] = []
        for mnemonic, item in rendered.curve_items.items():
            x_values, y_values = item.getData()
            if x_values is None or y_values is None or len(y_values) == 0:
                continue
            finite = np.isfinite(x_values) & np.isfinite(y_values)
            if not np.any(finite):
                continue
            xf = np.asarray(x_values)[finite]
            yf = np.asarray(y_values)[finite]
            candidate_index = int(np.argmin(np.abs(yf - float(view_pos.y()))))
            candidate_scene = rendered.plot.getViewBox().mapViewToScene(
                QPointF(float(xf[candidate_index]), float(yf[candidate_index]))
            )
            distance = float(
                (
                    (candidate_scene.x() - scene_pos.x()) ** 2
                    + (candidate_scene.y() - scene_pos.y()) ** 2
                )
                ** 0.5
            )
            if distance <= tolerance_px:
                hits.append(
                    HitResult(
                        target=SelectionRef(SelectableKind.CURVE, mnemonic, track_id),
                        priority=50,
                        distance_px=distance,
                        local_x=float(view_pos.x()),
                        local_y=float(view_pos.y()),
                    )
                )
        return choose_best_hit(hits)

    def select_curve_at(
        self,
        track_id: str,
        local_x: float,
        local_y: float,
        *,
        tolerance_px: float = 8.0,
        additive: bool = False,
        toggle: bool = False,
    ) -> HitResult | None:
        hit = self.hit_test_curve(track_id, local_x, local_y, tolerance_px=tolerance_px)
        if hit is None:
            return None
        if self._selection.select(hit.target, additive=additive, toggle=toggle):
            self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
            self._apply_curve_selection_style()
            self.selection_changed.emit(self._selection.snapshot())
            self.curve_selected.emit(track_id, hit.target.object_id)
        return hit

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

    def _apply_curve_selection_style(self) -> None:
        selected_by_track: dict[str, str] = {}
        for item in self._selection.snapshot().items:
            if item.kind is SelectableKind.CURVE and item.track_id is not None:
                selected_by_track[item.track_id] = item.object_id
        for track_id, rendered in self._rendered.items():
            rendered.widget.set_selected_curve(selected_by_track.get(track_id))

    @staticmethod
    def _build_pencil_cursor() -> QCursor:
        """Build a compact pencil cursor whose hotspot is the graphite tip."""

        pixmap = QPixmap(26, 26)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Short white halo keeps the compact cursor visible on dense curves.
        painter.setPen(
            QPen(
                QColor("#ffffff"),
                6.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawLine(6, 20, 19, 7)
        painter.setPen(
            QPen(
                QColor("#0f172a"),
                4.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawLine(6, 20, 19, 7)
        painter.setPen(
            QPen(
                QColor("#f97316"),
                2.2,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawLine(7, 19, 18, 8)
        painter.setPen(QPen(QColor("#0f172a"), 1.4))
        painter.setBrush(QBrush(QColor("#fde68a")))
        painter.drawPolygon([QPoint(3, 23), QPoint(7, 19), QPoint(8, 22)])
        painter.setBrush(QBrush(QColor("#0f172a")))
        painter.drawPolygon([QPoint(3, 23), QPoint(5, 21), QPoint(5, 23)])
        painter.end()
        return QCursor(pixmap, 3, 23)

    @staticmethod
    def _curve_is_directly_editable(curve: CurveData) -> bool:
        provenance = (curve.metadata.provenance or "").strip().casefold()
        description = (curve.metadata.description or "").strip().casefold()
        calculated_prefixes = ("calculation:", "custom-formula:")
        return (
            not provenance.startswith(calculated_prefixes)
            and not description.startswith(calculated_prefixes)
            and provenance != "derived"
        )

    @property
    def curve_pencil_enabled(self) -> bool:
        return self._curve_pencil_enabled

    @property
    def curve_pencil_target(self) -> tuple[str, str] | None:
        if self._curve_pencil_track_id is None or self._curve_pencil_mnemonic is None:
            return None
        return self._curve_pencil_track_id, self._curve_pencil_mnemonic

    @property
    def curve_pencil_controls_visible(self) -> bool:
        return self._curve_pencil_bar.isVisible()

    def selected_curve_pencil_target(self) -> tuple[str, str] | None:
        """Return the user's selected editable curve before choosing a fallback."""

        if self._dataset is None:
            return None
        selected = self._selection.snapshot().items
        for item in reversed(selected):
            if item.kind is not SelectableKind.CURVE or item.track_id is None:
                continue
            curve = self._dataset.curve_by_mnemonic(item.object_id)
            rendered = self._rendered.get(item.track_id)
            if (
                curve is not None
                and rendered is not None
                and rendered.curve_items
                and item.object_id in rendered.curve_items
                and self._curve_is_directly_editable(curve)
            ):
                return item.track_id, item.object_id
        return None

    def _select_curve_pencil_mode(self, mode: CurvePencilMode) -> None:
        row = self._curve_pencil_mode_selector.findData(mode.value)
        if row >= 0:
            self._curve_pencil_mode_selector.setCurrentIndex(row)

    def _sync_curve_pencil_mode_buttons(self) -> None:
        point_mode = self._curve_pencil_mode is CurvePencilMode.CONNECT_POINTS
        for button, checked in (
            (self._curve_pencil_freehand_button, not point_mode),
            (self._curve_pencil_points_button, point_mode),
        ):
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
            button.setStyleSheet(
                "QPushButton { padding: 5px 9px; border-radius: 4px; "
                + (
                    "background:#f97316; color:#ffffff; border:1px solid #c2410c; "
                    "font-weight:700; }"
                    if checked
                    else "background:#fff7ed; color:#9a3412; border:1px solid #fdba74; }"
                )
            )

    def _curve_pencil_mode_changed(self, _row: int) -> None:
        raw = self._curve_pencil_mode_selector.currentData()
        try:
            mode = CurvePencilMode(str(raw))
        except ValueError:
            mode = CurvePencilMode.FREEHAND
        if mode is self._curve_pencil_mode:
            self._sync_curve_pencil_mode_buttons()
            self._update_curve_pencil_mode_controls()
            return
        self.cancel_curve_pencil_gesture()
        self._curve_pencil_mode = mode
        self._curve_pencil_commit_error = ""
        self._sync_curve_pencil_mode_buttons()
        self._update_curve_pencil_mode_controls()
        self._update_curve_pencil_status()

    def _update_curve_pencil_mode_controls(self) -> None:
        self._sync_curve_pencil_mode_buttons()
        point_mode = self._curve_pencil_mode is CurvePencilMode.CONNECT_POINTS
        self._curve_pencil_apply_button.setVisible(point_mode)
        self._curve_pencil_clear_button.setVisible(point_mode)
        self._curve_pencil_apply_button.setEnabled(
            point_mode and self._curve_pencil_enabled and len(self._curve_pencil_points) >= 2
        )
        self._curve_pencil_clear_button.setEnabled(
            point_mode and bool(self._curve_pencil_points)
        )

    def set_curve_pencil_history_state(self, can_undo: bool, can_redo: bool) -> None:
        self._curve_pencil_can_undo = bool(can_undo)
        self._curve_pencil_can_redo = bool(can_redo)
        self._curve_pencil_undo_button.setEnabled(self._curve_pencil_can_undo)
        self._curve_pencil_redo_button.setEnabled(self._curve_pencil_can_redo)

    def _apply_curve_pencil_points(self) -> None:
        if self._curve_pencil_mode is not CurvePencilMode.CONNECT_POINTS:
            return
        if self._commit_curve_pencil_gesture():
            self.cancel_curve_pencil_gesture()
        else:
            self._update_curve_pencil_status()

    def acknowledge_curve_pencil_commit(self, accepted: bool, error: str = "") -> None:
        """Acknowledge synchronous application of the emitted curve edit request.

        TabletView deliberately does not mutate the project model itself.  The
        main-window controller applies the command and calls this method before
        the signal handler returns.  A failed edit therefore keeps the orange
        preview and selected points visible instead of silently discarding them.
        """

        self._curve_pencil_commit_ack = bool(accepted)
        self._curve_pencil_commit_error = error.strip()
        self._update_curve_pencil_status()

    def _tablet_pencil_button_toggled(self, enabled: bool) -> None:
        if enabled == self._curve_pencil_enabled:
            return
        if not self.set_curve_pencil_mode(enabled):
            self._curve_pencil_button.blockSignals(True)
            self._curve_pencil_button.setChecked(False)
            self._curve_pencil_button.blockSignals(False)

    def _curve_pencil_target_changed(self, _row: int) -> None:
        data = self._curve_pencil_selector.currentData()
        if not (
            isinstance(data, tuple)
            and len(data) == 2
            and all(isinstance(value, str) for value in data)
        ):
            self._curve_pencil_track_id = None
            self._curve_pencil_mnemonic = None
            self._curve_pencil_curve_id = None
            if self._curve_pencil_enabled:
                self.set_curve_pencil_mode(False)
            self._update_curve_pencil_status()
            return
        track_id, mnemonic = data
        if not self._set_curve_pencil_target(track_id, mnemonic):
            return
        if self._curve_pencil_enabled:
            self._clear_curve_pencil_preview()
            self._curve_pencil_points.clear()
            self._curve_pencil_last_hover = None
            self._apply_curve_pencil_cursors()
            self._scroll_to_curve_pencil_target()
            self.curve_pencil_mode_changed.emit(True, mnemonic)
        self._update_curve_pencil_status()

    def _available_curve_pencil_targets(self) -> list[tuple[str, str, str]]:
        if self._dataset is None:
            return []
        targets: list[tuple[str, str, str]] = []
        for definition in self._layout_model.visible_tracks():
            rendered = self._rendered.get(definition.track_id)
            if (
                rendered is None
                or not rendered.curve_items
                or is_relative_gas_track(definition.curve_mnemonics)
            ):
                continue
            for mnemonic in definition.curve_mnemonics:
                if mnemonic not in rendered.curve_items:
                    continue
                curve = self._dataset.curve_by_mnemonic(mnemonic)
                if curve is None or not self._curve_is_directly_editable(curve):
                    continue
                display = self._curve_display_name(definition, mnemonic, curve)
                unit = (curve.metadata.unit or "").strip()
                suffix = f" [{mnemonic}]"
                if unit:
                    suffix += f" · {unit}"
                targets.append(
                    (definition.track_id, mnemonic, f"{definition.title} — {display}{suffix}")
                )
        return targets

    def _refresh_curve_pencil_targets(self) -> None:
        preferred = self.curve_pencil_target
        targets = self._available_curve_pencil_targets()
        self._curve_pencil_selector.blockSignals(True)
        try:
            self._curve_pencil_selector.clear()
            for track_id, mnemonic, label in targets:
                self._curve_pencil_selector.addItem(label, (track_id, mnemonic))
            selected = -1
            if preferred is not None:
                for row in range(self._curve_pencil_selector.count()):
                    if self._curve_pencil_selector.itemData(row) == preferred:
                        selected = row
                        break
            if selected < 0 and targets:
                selected = 0
            self._curve_pencil_selector.setCurrentIndex(selected)
        finally:
            self._curve_pencil_selector.blockSignals(False)
        enabled = bool(targets)
        self._curve_pencil_selector.setEnabled(enabled)
        self._curve_pencil_button.setEnabled(enabled)
        if not enabled:
            self._curve_pencil_track_id = None
            self._curve_pencil_mnemonic = None
            self._curve_pencil_curve_id = None
            if self._curve_pencil_enabled:
                self.set_curve_pencil_mode(False)
            self._update_curve_pencil_status()
            return
        data = self._curve_pencil_selector.currentData()
        if isinstance(data, tuple) and len(data) == 2:
            self._set_curve_pencil_target(str(data[0]), str(data[1]))
        if self._curve_pencil_enabled:
            self._apply_curve_pencil_cursors()
            self._scroll_to_curve_pencil_target()
        self._update_curve_pencil_status()

    def _set_curve_pencil_target(self, track_id: str, mnemonic: str) -> bool:
        if self._dataset is None:
            return False
        rendered = self._rendered.get(track_id)
        curve = self._dataset.curve_by_mnemonic(mnemonic)
        if (
            rendered is None
            or not rendered.curve_items
            or mnemonic not in rendered.curve_items
            or curve is None
            or not self._curve_is_directly_editable(curve)
            or is_relative_gas_track(rendered.definition.curve_mnemonics)
        ):
            return False
        self._curve_pencil_track_id = track_id
        self._curve_pencil_mnemonic = mnemonic
        self._curve_pencil_curve_id = curve.metadata.curve_id
        rendered.widget.set_selected_curve(mnemonic)
        return True

    def set_curve_pencil_mode(
        self,
        enabled: bool,
        *,
        track_id: str | None = None,
        mnemonic: str | None = None,
    ) -> bool:
        if not enabled:
            was_enabled = self._curve_pencil_enabled
            active_mnemonic = self._curve_pencil_mnemonic or ""
            self._curve_pencil_enabled = False
            self._curve_pencil_points.clear()
            self._curve_pencil_last_hover = None
            self._clear_curve_pencil_preview()
            self._curve_pencil_button.blockSignals(True)
            self._curve_pencil_button.setChecked(False)
            self._curve_pencil_button.blockSignals(False)
            self._apply_geological_mode_cursors()
            self._update_curve_pencil_status()
            if was_enabled:
                self.curve_pencil_mode_changed.emit(False, active_mnemonic)
            return True

        if self._dataset is None:
            return False
        if track_id is not None and mnemonic is not None:
            requested = (track_id, mnemonic)
            for row in range(self._curve_pencil_selector.count()):
                if self._curve_pencil_selector.itemData(row) == requested:
                    self._curve_pencil_selector.setCurrentIndex(row)
                    break
        data = self._curve_pencil_selector.currentData()
        if not (
            isinstance(data, tuple)
            and len(data) == 2
            and self._set_curve_pencil_target(str(data[0]), str(data[1]))
        ):
            self._refresh_curve_pencil_targets()
            data = self._curve_pencil_selector.currentData()
            if not (
                isinstance(data, tuple)
                and len(data) == 2
                and self._set_curve_pencil_target(str(data[0]), str(data[1]))
            ):
                return False
        self._curve_pencil_enabled = True
        self._curve_pencil_points.clear()
        self._clear_curve_pencil_preview()
        self._curve_pencil_button.blockSignals(True)
        self._curve_pencil_button.setChecked(True)
        self._curve_pencil_button.blockSignals(False)
        self._apply_curve_pencil_cursors()
        self._scroll_to_curve_pencil_target()
        self._update_curve_pencil_status()
        self.curve_pencil_mode_changed.emit(True, self._curve_pencil_mnemonic or "")
        return True

    def activate_curve_pencil_for_mnemonic(self, mnemonic: str) -> bool:
        for row in range(self._curve_pencil_selector.count()):
            data = self._curve_pencil_selector.itemData(row)
            if isinstance(data, tuple) and len(data) == 2 and data[1] == mnemonic:
                self._curve_pencil_selector.setCurrentIndex(row)
                return self.set_curve_pencil_mode(
                    True, track_id=str(data[0]), mnemonic=str(data[1])
                )
        return False

    def _scroll_to_curve_pencil_target(self) -> None:
        if self._curve_pencil_track_id is None:
            return
        rendered = self._rendered.get(self._curve_pencil_track_id)
        if rendered is not None:
            self._scroll.ensureWidgetVisible(rendered.widget, 20, 0)

    def _update_curve_pencil_bar_style(self) -> None:
        if self._curve_pencil_enabled:
            self._curve_pencil_bar.setStyleSheet(
                "QFrame#tabletCurvePencilBar { background:#fff7ed; "
                "border-top:1px solid #fdba74; border-bottom:1px solid #fdba74; } "
                "QPushButton:checked { background:#f97316; color:white; "
                "border:1px solid #c2410c; font-weight:700; padding:4px 10px; }"
            )
        else:
            self._curve_pencil_bar.setStyleSheet(
                "QFrame#tabletCurvePencilBar { background:#f8fafc; "
                "border-top:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; }"
            )

    def _update_curve_pencil_status(self) -> None:
        if self._curve_pencil_commit_error:
            self._curve_pencil_status.setText(
                self._localizer.text(
                    "tablet.curve_pencil_commit_failed",
                    error=self._curve_pencil_commit_error,
                )
            )
            self._curve_pencil_status.setStyleSheet(
                "color:#b91c1c; font-weight:700; padding:2px 6px;"
            )
        elif self._curve_pencil_enabled and self._curve_pencil_mnemonic:
            if (
                self._curve_pencil_mode is CurvePencilMode.CONNECT_POINTS
                and self._curve_pencil_points
            ):
                self._curve_pencil_status.setText(
                    self._localizer.text(
                        "tablet.curve_pencil_points_selected",
                        mnemonic=self._curve_pencil_mnemonic,
                        count=len(self._curve_pencil_points),
                    )
                )
            else:
                key = (
                    "tablet.curve_pencil_unsaved"
                    if self._curve_pencil_unsaved
                    else "tablet.curve_pencil_active"
                )
                self._curve_pencil_status.setText(
                    self._localizer.text(key, mnemonic=self._curve_pencil_mnemonic)
                )
            self._curve_pencil_status.setStyleSheet(
                "color:#9a3412; font-weight:700; padding:2px 6px;"
            )
        elif self._curve_pencil_selector.count() == 0:
            self._curve_pencil_status.setText(self._localizer.text("tablet.curve_pencil_no_curves"))
            self._curve_pencil_status.setStyleSheet("color:#64748b; padding:2px 6px;")
        else:
            self._curve_pencil_status.setText(self._localizer.text("tablet.curve_pencil_inactive"))
            self._curve_pencil_status.setStyleSheet("color:#475569; padding:2px 6px;")
        self._update_curve_pencil_bar_style()
        self._update_curve_pencil_mode_controls()

    def mark_curve_pencil_unsaved(self) -> None:
        self._curve_pencil_unsaved = True
        self._update_curve_pencil_status()

    def clear_curve_pencil_unsaved(self) -> None:
        # Saving clears only the dirty indicator.  Undo/redo history remains
        # available, matching standard editor behaviour; an undo after Save
        # marks the project dirty again through the controller.
        self._curve_pencil_unsaved = False
        self._update_curve_pencil_status()

    def _apply_curve_pencil_cursors(self) -> None:
        self._apply_geological_mode_cursors_base()
        for item in self._rendered.values():
            item.widget.set_pencil_active(False)
            if item.curve_pencil_badge is not None:
                item.curve_pencil_badge.hide()
            if item.curve_pencil_readout is not None:
                item.curve_pencil_readout.hide()
        if not self._curve_pencil_enabled or self._curve_pencil_track_id is None:
            return
        rendered = self._rendered.get(self._curve_pencil_track_id)
        if rendered is not None and rendered.plot is not None:
            rendered.widget.set_pencil_active(True)
            viewport = rendered.plot.viewport()
            viewport.setMouseTracking(True)
            viewport.setCursor(self._pencil_cursor)
            rendered.plot.setCursor(self._pencil_cursor)
            rendered.plot.setToolTip(
                self._localizer.text(
                    "tablet.curve_pencil_active", mnemonic=self._curve_pencil_mnemonic or ""
                )
            )
            if rendered.curve_pencil_badge is None:
                badge = QLabel(viewport)
                badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                badge.setStyleSheet(
                    "background:rgba(255,237,213,235); color:#9a3412; "
                    "border:1px solid #f97316; border-radius:5px; "
                    "padding:3px 7px; font-weight:700;"
                )
                rendered.curve_pencil_badge = badge
            rendered.curve_pencil_badge.setText(
                f"✎ {self._curve_pencil_mnemonic or ''}"
            )
            rendered.curve_pencil_badge.adjustSize()
            rendered.curve_pencil_badge.move(8, 8)
            rendered.curve_pencil_badge.show()
            rendered.curve_pencil_badge.raise_()
            if rendered.curve_pencil_readout is None:
                readout = QLabel(viewport)
                readout.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                readout.setWordWrap(False)
                readout.setStyleSheet(
                    "background:rgba(15,23,42,238); color:#ffffff; "
                    "border:2px solid #f97316; border-radius:6px; "
                    "padding:5px 8px; font-weight:700;"
                )
                rendered.curve_pencil_readout = readout
            if (
                self._curve_pencil_last_hover is not None
                and self._curve_pencil_last_hover[0] == self._curve_pencil_track_id
            ):
                _, last_point, last_position = self._curve_pencil_last_hover
                self._show_curve_pencil_readout(rendered, last_point, last_position)

    def _curve_pencil_point_from_values(
        self, axis_value: float, source_value: float
    ) -> _CurvePencilPoint:
        if self._curve_pencil_track_id is None or self._curve_pencil_mnemonic is None:
            raise RuntimeError("Кривая карандаша не выбрана")
        rendered = self._rendered.get(self._curve_pencil_track_id)
        if rendered is None:
            raise RuntimeError("Дорожка карандаша не отрисована")
        display_x = self._curve_pencil_display_x(
            rendered.definition, self._curve_pencil_mnemonic, source_value
        )
        return _CurvePencilPoint(float(axis_value), float(source_value), display_x)

    def _curve_pencil_point(
        self, plot: pg.PlotWidget, event: QMouseEvent
    ) -> _CurvePencilPoint | None:
        if self._curve_pencil_track_id is None or self._curve_pencil_mnemonic is None:
            return None
        rendered = self._rendered.get(self._curve_pencil_track_id)
        if rendered is None:
            return None
        point = self._mouse_event_plot_point(plot, event)
        display_x = float(point.x())
        axis_value = float(point.y())
        if not np.isfinite(display_x) or not np.isfinite(axis_value):
            return None
        source_value = self._curve_pencil_source_value(
            rendered.definition, self._curve_pencil_mnemonic, display_x
        )
        if source_value is None or not np.isfinite(source_value):
            return None
        return _CurvePencilPoint(axis_value, float(source_value), display_x)

    def _update_curve_pencil_hover(
        self, plot: pg.PlotWidget, event: QMouseEvent, track_id: str | None
    ) -> None:
        """Keep a visible pencil and live depth/value readout under the mouse."""

        if (
            not self._curve_pencil_enabled
            or track_id != self._curve_pencil_track_id
            or self._curve_pencil_mnemonic is None
            or self._dataset is None
        ):
            return
        rendered = self._rendered.get(track_id) if track_id is not None else None
        if rendered is None or rendered.plot is None:
            return
        viewport = rendered.plot.viewport()
        # Some pyqtgraph/Qt interactions restore ArrowCursor after a scene event.
        # Reassert the pencil cursor on every movement so it cannot disappear.
        viewport.setCursor(self._pencil_cursor)
        plot.setCursor(self._pencil_cursor)
        point = self._curve_pencil_point(plot, event)
        if point is None:
            if rendered.curve_pencil_readout is not None:
                rendered.curve_pencil_readout.hide()
            return
        if track_id is None:
            return
        position = event.position().toPoint()
        self._curve_pencil_last_hover = (track_id, point, position)
        self._show_curve_pencil_readout(rendered, point, position)

    def _show_curve_pencil_readout(
        self, rendered: RenderedTrack, point: _CurvePencilPoint, cursor_position: QPoint
    ) -> None:
        if self._dataset is None or self._curve_pencil_mnemonic is None or rendered.plot is None:
            return
        curve = self._dataset.curve_by_mnemonic(self._curve_pencil_mnemonic)
        unit = (curve.metadata.unit or "").strip() if curve is not None else ""
        old_value: float | None = None
        axis = np.asarray(self._axis_values(), dtype=float)
        if curve is not None and axis.size and curve.values.size == axis.size:
            finite = np.flatnonzero(np.isfinite(axis))
            if finite.size:
                sample_index = int(finite[np.argmin(np.abs(axis[finite] - point.axis_value))])
                candidate = float(curve.values[sample_index])
                if np.isfinite(candidate):
                    old_value = candidate
        axis_text = self._format_axis_value(point.axis_value)
        axis_descriptor = self._axis_descriptor()
        axis_name = axis_descriptor.label if axis_descriptor is not None else "Axis"
        value_text = f"{point.source_value:.6g}{(' ' + unit) if unit else ''}"
        old_text = (
            f"{old_value:.6g}{(' ' + unit) if unit else ''}"
            if old_value is not None
            else "—"
        )
        label = rendered.curve_pencil_readout
        if label is None:
            return
        label.setText(
            self._localizer.text(
                "tablet.curve_pencil_live_readout",
                mnemonic=self._curve_pencil_mnemonic,
                axis_name=axis_name,
                axis=axis_text,
                value=value_text,
                old=old_text,
            )
        )
        label.adjustSize()
        viewport = rendered.plot.viewport()
        margin = 10
        position = QPoint(cursor_position) + QPoint(20, 20)
        maximum_x = max(margin, viewport.width() - label.width() - margin)
        maximum_y = max(margin, viewport.height() - label.height() - margin)
        position.setX(max(margin, min(position.x(), maximum_x)))
        position.setY(max(margin, min(position.y(), maximum_y)))
        label.move(position)
        label.show()
        label.raise_()

    def _hide_curve_pencil_hover(self, track_id: str | None) -> None:
        if track_id is None:
            return
        if self._curve_pencil_last_hover is not None and self._curve_pencil_last_hover[0] == track_id:
            self._curve_pencil_last_hover = None
        rendered = self._rendered.get(track_id)
        if rendered is not None and rendered.curve_pencil_readout is not None:
            rendered.curve_pencil_readout.hide()

    def _curve_pencil_source_value(
        self, definition: TrackDefinition, mnemonic: str, display_x: float
    ) -> float | None:
        if self._dataset is None:
            return None
        curve = self._dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            return None
        if definition.kind is TrackKind.CALCIMETRY:
            return float(np.clip(display_x, 0.0, 100.0))
        fraction = float(np.clip(display_x, 0.0, 1.0))
        settings = definition.curve_display_settings(mnemonic)
        minimum, maximum = self._curve_display_range(
            definition, mnemonic, np.asarray(curve.values, dtype=float)
        )
        if settings.x_scale is XScale.LOGARITHMIC:
            if minimum <= 0 or maximum <= minimum:
                return None
            lower = np.log10(minimum)
            upper = np.log10(maximum)
            return float(10.0 ** (lower + fraction * (upper - lower)))
        return float(minimum + fraction * (maximum - minimum))

    def _curve_pencil_display_x(
        self, definition: TrackDefinition, mnemonic: str, source_value: float
    ) -> float:
        if self._dataset is None:
            return 0.0
        if definition.kind is TrackKind.CALCIMETRY:
            return float(np.clip(source_value, 0.0, 100.0))
        curve = self._dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            return 0.0
        settings = definition.curve_display_settings(mnemonic)
        minimum, maximum = self._curve_display_range(
            definition, mnemonic, np.asarray(curve.values, dtype=float)
        )
        normalized = self._normalize_curve_values(
            np.asarray([source_value], dtype=float), settings.x_scale, minimum, maximum
        )
        return float(normalized[0]) if normalized.size and np.isfinite(normalized[0]) else 0.0

    def _update_curve_pencil_preview(self) -> None:
        if self._curve_pencil_track_id is None or not self._curve_pencil_points:
            self._clear_curve_pencil_preview()
            return
        rendered = self._rendered.get(self._curve_pencil_track_id)
        if rendered is None or rendered.plot is None:
            return
        if rendered.curve_pencil_preview is None:
            preview = pg.PlotDataItem(
                pen=pg.mkPen("#f97316", width=3.0),
                symbol="o",
                symbolSize=4,
                symbolBrush=pg.mkBrush("#f97316"),
                connect="finite",
            )
            preview.setZValue(200)
            rendered.plot.addItem(preview)
            rendered.curve_pencil_preview = preview
        rendered.curve_pencil_preview.setData(
            [point.display_x for point in self._curve_pencil_points],
            [point.axis_value for point in self._curve_pencil_points],
            connect="finite",
        )

    def _clear_curve_pencil_preview(self) -> None:
        for rendered in self._rendered.values():
            preview = rendered.curve_pencil_preview
            if preview is None or rendered.plot is None:
                continue
            try:
                rendered.plot.removeItem(preview)
            except RuntimeError:
                pass
            rendered.curve_pencil_preview = None

    def cancel_curve_pencil_gesture(self) -> None:
        self._curve_pencil_points.clear()
        self._curve_pencil_commit_ack = None
        self._curve_pencil_commit_error = ""
        self._clear_curve_pencil_preview()
        self._update_curve_pencil_mode_controls()
        self._update_curve_pencil_status()

    def _commit_curve_pencil_gesture(self) -> bool:
        if (
            not self._curve_pencil_enabled
            or self._dataset is None
            or self._curve_pencil_curve_id is None
            or len(self._curve_pencil_points) < 2
        ):
            return False
        unique: dict[float, _CurvePencilPoint] = {}
        for point in self._curve_pencil_points:
            unique[point.axis_value] = point
        points = list(unique.values())
        if len(points) < 2:
            return False
        top = min(point.axis_value for point in points)
        bottom = max(point.axis_value for point in points)
        axis = np.asarray(self._axis_values(), dtype=np.float64)
        indices = np.flatnonzero(np.isfinite(axis) & (axis >= top) & (axis <= bottom))
        if indices.size == 0:
            return False
        order = np.argsort(axis[indices], kind="stable")
        sorted_indices = indices[order]
        draw_points = [DrawPoint(point.axis_value, point.source_value) for point in points]
        try:
            sorted_values = interpolate_drawn_curve(axis[sorted_indices], draw_points)
        except ValueError:
            return False
        new_values = np.empty(sorted_values.shape, dtype=np.float64)
        new_values[order] = sorted_values
        self._curve_pencil_commit_ack = None
        self._curve_pencil_commit_error = ""
        self.curve_edit_requested.emit(self._curve_pencil_curve_id, indices, new_values)
        # Legacy/test receivers may not acknowledge explicitly.  In that case the
        # emitted request is treated as accepted.  The real application always
        # acknowledges success or failure synchronously from MainWindow.
        return self._curve_pencil_commit_ack is not False

    def _handle_curve_pencil_event(
        self,
        plot: pg.PlotWidget,
        event: QMouseEvent,
        track_id: str | None,
    ) -> bool:
        if not self._curve_pencil_enabled or track_id != self._curve_pencil_track_id:
            return False
        event_type = event.type()
        if self._curve_pencil_mode is CurvePencilMode.CONNECT_POINTS:
            if (
                event_type in {QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick}
                and event.button() == Qt.MouseButton.LeftButton
            ):
                point = self._curve_pencil_point(plot, event)
                if point is None:
                    return False
                self._curve_pencil_commit_error = ""
                self._curve_pencil_points.append(point)
                # Keep one point per sampled vertical position while preserving
                # click order for the user's visual feedback.
                deduplicated: list[_CurvePencilPoint] = []
                for candidate in self._curve_pencil_points:
                    if deduplicated and np.isclose(
                        deduplicated[-1].axis_value, candidate.axis_value, rtol=0.0, atol=1e-9
                    ):
                        deduplicated[-1] = candidate
                    else:
                        deduplicated.append(candidate)
                self._curve_pencil_points = deduplicated
                self._update_curve_pencil_preview()
                self._update_curve_pencil_status()
                if event_type == QEvent.Type.MouseButtonDblClick and len(self._curve_pencil_points) >= 2:
                    if self._commit_curve_pencil_gesture():
                        self.cancel_curve_pencil_gesture()
                event.accept()
                return True
            return False

        if (
            event_type == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            point = self._curve_pencil_point(plot, event)
            if point is None:
                return False
            self._curve_pencil_commit_error = ""
            self._curve_pencil_points = [point]
            self._update_curve_pencil_preview()
            event.accept()
            return True
        if event_type == QEvent.Type.MouseMove and self._curve_pencil_points:
            point = self._curve_pencil_point(plot, event)
            if point is not None:
                self._curve_pencil_points.append(point)
                self._update_curve_pencil_preview()
            event.accept()
            return True
        if (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._curve_pencil_points
        ):
            point = self._curve_pencil_point(plot, event)
            if point is not None:
                self._curve_pencil_points.append(point)
            if self._commit_curve_pencil_gesture():
                self.cancel_curve_pencil_gesture()
            else:
                # Keep the preview in place so the user can see what failed and
                # retry after correcting the target or scale.
                self._update_curve_pencil_status()
            event.accept()
            return True
        return False

    @property
    def form_edit_mode(self) -> bool:
        return self._form_edit_mode

    @property
    def annotation_tool(self) -> AnnotationKind | None:
        return self._annotation_tool

    def set_annotation_tool(self, kind: AnnotationKind | str | None) -> None:
        """Arm a direct annotation tool for the next click in any plot body.

        Unlike the old toolbar behavior, selecting a tool does not create an
        object at the viewport center and does not open a modal dialog first.
        The user chooses the exact track and depth/time position with the mouse;
        the new box then appears selected for immediate move/resize editing.
        """

        normalized: AnnotationKind | None
        if kind is None or not self._form_edit_mode:
            normalized = None
        else:
            try:
                normalized = kind if isinstance(kind, AnnotationKind) else AnnotationKind(str(kind))
            except ValueError:
                normalized = None
        state = self._edit_mode_coordinator.set_annotation_tool(normalized)
        effective = state.annotation_tool
        normalized = effective if isinstance(effective, AnnotationKind) else None
        if normalized == self._annotation_tool:
            return
        self._annotation_tool = normalized
        cursor = (
            Qt.CursorShape.CrossCursor
            if normalized is not None
            else Qt.CursorShape.ArrowCursor
        )
        for rendered in self._rendered.values():
            if rendered.plot is not None:
                rendered.plot.viewport().setCursor(cursor)
        self.annotation_tool_changed.emit(
            normalized.value if normalized is not None else None
        )

    def set_form_edit_mode(self, enabled: bool) -> None:
        """Enable structural form editing while leaving geological data entry intact."""

        requested = bool(enabled)
        if not requested and self._annotation_tool is not None:
            # Disarm through the same public path so every viewport cursor and
            # toolbar action is restored before the handlers are disabled.
            self.set_annotation_tool(None)
        state = self._edit_mode_coordinator.set_form_edit_enabled(requested)
        self._form_edit_mode = state.form_edit_enabled
        if not self._form_edit_mode:
            self._interaction_router.reset("form_edit_disabled")
            self._interaction_watchdog.sync()
        hint = self._localizer.text(
            "tablet.form_edit_on" if self._form_edit_mode else "tablet.form_edit_off"
        )
        for rendered in self._rendered.values():
            rendered.widget.title.setToolTip(hint)
            for item in (rendered.annotation_items or {}).values():
                item.set_edit_mode(self._form_edit_mode)
        self._annotation_overlay.set_edit_mode(self._form_edit_mode)
        self._annotation_overlay.raise_()

    def show_geological_context_menu(
        self,
        track_id: str,
        depth: float,
        global_pos: QPoint,
        *,
        axis_value: float | None = None,
        x_fraction: float = 0.5,
    ) -> None:
        """Show data-entry actions at the clicked geological interval."""

        try:
            definition = self._layout_model.track_by_id(track_id)
        except KeyError:
            return
        self.select_track(track_id, emit_signal=True)
        menu = QMenu(self)
        sample = self.cuttings_sample_at_depth(depth)
        lithology = self.lithology_interval_at_depth(depth)
        stratigraphy = self.stratigraphy_interval_at_depth(depth)

        create_action = edit_action = full_edit_action = None
        if definition.kind is TrackKind.STRATIGRAPHY:
            if stratigraphy is None:
                create_action = menu.addAction(self._localizer.text("stratigraphy.new_interval"))
            else:
                edit_action = menu.addAction(self._localizer.text("stratigraphy.edit_interval"))
        elif definition.kind is TrackKind.LITHOLOGY:
            if lithology is None:
                create_action = menu.addAction(
                    self._localizer.text("geology.context.new_lithology")
                )
            else:
                edit_action = menu.addAction(self._localizer.text("geology.context.edit_lithology"))
        elif definition.kind is TrackKind.TEXT:
            if sample is None:
                create_action = menu.addAction(
                    self._localizer.text("geology.context.new_description")
                )
            else:
                edit_action = menu.addAction(
                    self._localizer.text("geology.context.edit_description")
                )
                full_edit_action = menu.addAction(
                    self._localizer.text("geology.context.edit_full_sample")
                )
        else:
            if sample is None:
                create_action = menu.addAction(self._localizer.text("geology.context.new_sample"))
            else:
                edit_action = menu.addAction(
                    self._localizer.text("geology.context.edit_full_sample")
                )

        annotation_callout_action = annotation_comment_action = annotation_image_action = None
        if self._form_edit_mode:
            menu.addSeparator()
            annotation_callout_action = menu.addAction(
                self._localizer.text("annotations.add_callout_action")
            )
            annotation_comment_action = menu.addAction(
                self._localizer.text("annotations.add_comment_action")
            )
            annotation_image_action = menu.addAction(
                self._localizer.text("annotations.add_image_action")
            )

        edit_track_action = rename_track_action = rename_group_action = None
        properties_action = save_action = None
        if self._form_edit_mode:
            menu.addSeparator()
            edit_track_action = menu.addAction(self._localizer.text("tablet.edit_track_full"))
            rename_track_action = menu.addAction(self._localizer.text("tablet.rename_track"))
            rename_group_action = menu.addAction(self._localizer.text("tablet.rename_group"))
            properties_action = menu.addAction(self._localizer.text("tablet.track_properties"))
            save_action = menu.addAction(self._localizer.text("tablet.save_layout_as_form"))
        chosen = menu.exec(global_pos)
        annotation_kind = None
        if chosen is annotation_callout_action:
            annotation_kind = AnnotationKind.CALLOUT
        elif chosen is annotation_comment_action:
            annotation_kind = AnnotationKind.COMMENT
        elif chosen is annotation_image_action:
            annotation_kind = AnnotationKind.IMAGE
        if annotation_kind is not None:
            self.annotation_add_requested.emit(
                self._annotation_request_payload(
                    track_id=track_id,
                    depth=depth,
                    axis_value=axis_value,
                    x_fraction=x_fraction,
                    kind=annotation_kind,
                )
            )
            return
        if chosen is edit_track_action:
            self.track_full_edit_requested.emit(track_id)
            return
        if chosen is rename_track_action:
            self.track_rename_requested.emit(track_id)
            return
        if chosen is rename_group_action:
            self.track_group_rename_requested.emit(track_id)
            return
        if chosen is properties_action:
            self.track_properties_requested.emit(track_id)
            return
        if chosen is save_action:
            self.save_layout_requested.emit()
            return
        if chosen is full_edit_action and sample is not None:
            self.cuttings_sample_edit_requested.emit(sample.sample_id)
            return
        if chosen == edit_action:
            if definition.kind is TrackKind.STRATIGRAPHY and stratigraphy is not None:
                self.stratigraphy_interval_edit_requested.emit(stratigraphy.interval_id)
            elif definition.kind is TrackKind.LITHOLOGY and lithology is not None:
                self.lithology_interval_edit_requested.emit(lithology.interval_id)
            elif definition.kind is TrackKind.TEXT and sample is not None:
                self.description_edit_requested.emit(sample.sample_id)
            elif sample is not None:
                self.cuttings_sample_edit_requested.emit(sample.sample_id)
            return
        if chosen is create_action:
            top, bottom = self._default_geological_interval(depth)
            if definition.kind is TrackKind.STRATIGRAPHY:
                self.stratigraphy_interval_requested.emit(top, bottom)
            elif definition.kind is TrackKind.LITHOLOGY:
                self.lithology_interval_requested.emit(top, bottom)
            elif definition.kind is TrackKind.TEXT:
                self.description_interval_requested.emit(top, bottom)
            else:
                self.cuttings_interval_requested.emit(top, bottom)

    def _default_geological_interval(self, depth: float) -> tuple[float, float]:
        """Return an editable one-sample interval for right-click creation."""

        bounds = self._depth_bounds()
        snapped = self._snap_depth(float(depth))
        step = max(self._minimum_depth_span(), 1.0)
        if bounds is None:
            return snapped, snapped + step
        domain_top, domain_bottom = sorted(bounds)
        top = max(domain_top, min(snapped, domain_bottom))
        bottom = min(domain_bottom, top + step)
        if bottom <= top:
            top = max(domain_top, domain_bottom - step)
            bottom = domain_bottom
        return float(top), float(bottom)

    def show_track_context_menu(
        self,
        track_id: str,
        global_pos: QPoint,
        *,
        depth: float | None = None,
        axis_value: float | None = None,
        x_fraction: float = 0.5,
        local_x: float | None = None,
        local_y: float | None = None,
    ) -> None:
        try:
            definition = self._layout_model.track_by_id(track_id)
            index = self._layout_model.tracks.index(definition)
        except (KeyError, ValueError):
            return
        self.select_track(track_id, emit_signal=True)
        menu = QMenu(self)

        graphical = definition.kind in {TrackKind.CURVE, TrackKind.GAS, TrackKind.DEXP}
        add_curves = replace_curves = properties_action = None
        curve_settings_action = save_layout_action = pencil_action = None
        selected_curve = ""
        if graphical:
            for selected in self._selection.snapshot().items:
                if selected.kind is SelectableKind.CURVE and selected.track_id == track_id:
                    selected_curve = selected.object_id
                    break
            if not selected_curve and definition.curve_mnemonics:
                selected_curve = definition.curve_mnemonics[0]
            pencil_action = menu.addAction(self._localizer.text("tablet.curve_pencil_action"))
            pencil_action.setEnabled(bool(selected_curve))
            if self._form_edit_mode:
                add_curves = menu.addAction(self._localizer.text("tablet.add_curves"))
                replace_curves = menu.addAction(self._localizer.text("tablet.choose_track_curves"))
                curve_settings_action = menu.addAction(
                    self._localizer.text("tablet.curve_settings")
                )
                menu.addSeparator()

        annotation_callout_action = annotation_comment_action = annotation_image_action = None
        save_value_action = None
        curve_value = None
        if local_x is not None and local_y is not None:
            curve_value = self._curve_value_payload(track_id, local_x, local_y)
        if curve_value is not None:
            value_text = self._curve_value_caption(curve_value)
            value_label_action = menu.addAction(value_text)
            value_label_action.setEnabled(False)
            save_value_action = menu.addAction(
                self._localizer.text("annotations.save_curve_value_action")
            )
            menu.addSeparator()
        if self._form_edit_mode and depth is not None:
            annotation_callout_action = menu.addAction(
                self._localizer.text("annotations.add_callout_action")
            )
            annotation_comment_action = menu.addAction(
                self._localizer.text("annotations.add_comment_action")
            )
            annotation_image_action = menu.addAction(
                self._localizer.text("annotations.add_image_action")
            )
            menu.addSeparator()

        edit_track_action = rename_track_action = rename_group_action = None
        move_left = move_right = hide_action = remove_action = None
        save_layout_action = None
        if self._form_edit_mode:
            edit_track_action = menu.addAction(self._localizer.text("tablet.edit_track_full"))
            rename_track_action = menu.addAction(self._localizer.text("tablet.rename_track"))
            rename_group_action = menu.addAction(self._localizer.text("tablet.rename_group"))
            properties_action = menu.addAction(self._localizer.text("tablet.track_properties"))
            menu.addSeparator()
            move_left = menu.addAction(self._localizer.text("tablet.move_left"))
            move_right = menu.addAction(self._localizer.text("tablet.move_right"))
            menu.addSeparator()
            hide_action = menu.addAction(self._localizer.text("tablet.hide_track"))
            remove_action = menu.addAction(self._localizer.text("tablet.remove_track"))
            menu.addSeparator()
            save_layout_action = menu.addAction(self._localizer.text("tablet.save_layout_as_form"))
            menu.addSeparator()
        curve_undo_action = curve_redo_action = None
        if graphical:
            menu.addSeparator()
            curve_undo_action = menu.addAction(
                self._localizer.text("tablet.curve_pencil_undo_context")
            )
            curve_redo_action = menu.addAction(
                self._localizer.text("tablet.curve_pencil_redo_context")
            )
            curve_undo_action.setEnabled(self._curve_pencil_can_undo)
            curve_redo_action.setEnabled(self._curve_pencil_can_redo)
        undo_action = menu.addAction(self._localizer.text("tablet.undo_interaction"))
        redo_action = menu.addAction(self._localizer.text("tablet.redo_interaction"))
        if move_left is not None:
            move_left.setEnabled(index > 0 and definition.kind is not TrackKind.DEPTH)
        if move_right is not None:
            move_right.setEnabled(
                index < len(self._layout_model.tracks) - 1
                and definition.kind is not TrackKind.DEPTH
            )
        undo_action.setEnabled(self.can_undo_interaction)
        redo_action.setEnabled(self.can_redo_interaction)
        chosen = menu.exec(global_pos)
        if (
            save_value_action is not None
            and chosen is save_value_action
            and curve_value is not None
        ):
            self.curve_value_save_requested.emit(curve_value)
        elif (
            chosen is not None
            and depth is not None
            and (
                chosen is annotation_callout_action
                or chosen is annotation_comment_action
                or chosen is annotation_image_action
            )
        ):
            kind = (
                AnnotationKind.CALLOUT
                if chosen is annotation_callout_action
                else AnnotationKind.COMMENT
                if chosen is annotation_comment_action
                else AnnotationKind.IMAGE
            )
            self.annotation_add_requested.emit(
                self._annotation_request_payload(
                    track_id=track_id,
                    depth=depth,
                    axis_value=axis_value,
                    x_fraction=x_fraction,
                    kind=kind,
                )
            )
        elif pencil_action is not None and chosen is pencil_action:
            self.curve_pencil_requested.emit(track_id, selected_curve)
        elif add_curves is not None and chosen is add_curves:
            self.track_add_curves_requested.emit(track_id)
        elif replace_curves is not None and chosen is replace_curves:
            self.track_replace_curves_requested.emit(track_id)
        elif curve_settings_action is not None and chosen is curve_settings_action:
            first_curve = definition.curve_mnemonics[0] if definition.curve_mnemonics else ""
            self.track_curve_settings_requested.emit(track_id, first_curve)
        elif chosen is edit_track_action:
            self.track_full_edit_requested.emit(track_id)
        elif chosen is rename_track_action:
            self.track_rename_requested.emit(track_id)
        elif chosen is rename_group_action:
            self.track_group_rename_requested.emit(track_id)
        elif chosen is properties_action:
            self.track_properties_requested.emit(track_id)
        elif chosen is move_left:
            self.move_track_with_history(track_id, index - 1)
        elif chosen is move_right:
            self.move_track_with_history(track_id, index + 1)
        elif chosen is hide_action:
            self.track_hide_requested.emit(track_id)
        elif chosen is remove_action:
            self.track_remove_requested.emit(track_id)
        elif save_layout_action is not None and chosen is save_layout_action:
            self.save_layout_requested.emit()
        elif curve_undo_action is not None and chosen is curve_undo_action:
            self.curve_pencil_undo_requested.emit()
        elif curve_redo_action is not None and chosen is curve_redo_action:
            self.curve_pencil_redo_requested.emit()
        elif chosen is undo_action:
            self.undo_interaction()
        elif chosen is redo_action:
            self.redo_interaction()

    def _annotation_request_payload(
        self,
        *,
        track_id: str,
        depth: float,
        axis_value: float | None,
        x_fraction: float,
        kind: AnnotationKind,
    ) -> dict[str, object]:
        descriptor = self._axis_descriptor()
        anchor = (
            AnnotationAnchor.TIME
            if descriptor is not None and descriptor.role is not IndexRole.DEPTH
            else AnnotationAnchor.DEPTH
        )
        fraction = max(0.0, min(1.0, float(x_fraction)))
        if kind is AnnotationKind.CALLOUT:
            width, height = 240.0, 86.0
            offset_x = 54.0 if fraction <= 0.65 else -(width + 54.0)
            offset_y = -68.0
        elif kind is AnnotationKind.COMMENT:
            width, height = 220.0, 76.0
            offset_x = 12.0 if fraction <= 0.65 else -(width + 12.0)
            offset_y = -42.0
        else:
            width, height = 240.0, 160.0
            offset_x = 18.0 if fraction <= 0.65 else -(width + 18.0)
            offset_y = -80.0
        return {
            "kind": kind.value,
            "anchor": anchor.value,
            "track_id": track_id,
            "depth": float(depth),
            "axis_value": float(axis_value) if axis_value is not None else None,
            "axis_id": self.vertical_index_id,
            "x_fraction": fraction,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "width": width,
            "height": height,
        }

    def _direct_annotation_payload(
        self,
        plot: pg.PlotWidget,
        event: QMouseEvent,
        track_id: str,
        definition: TrackDefinition | None,
        *,
        kind: AnnotationKind | None = None,
    ) -> dict[str, object] | None:
        kind = kind or self._annotation_tool
        if kind is None:
            return None
        point = self._mouse_event_plot_point(plot, event)
        axis_value = float(point.y())
        depth = self._axis_to_depth_value(axis_value)
        viewport_width = max(1.0, float(plot.viewport().width()))
        x_fraction = max(0.0, min(1.0, float(event.position().x()) / viewport_width))
        payload = self._annotation_request_payload(
            track_id=track_id,
            depth=depth,
            axis_value=axis_value,
            x_fraction=x_fraction,
            kind=kind,
        )
        payload["direct_create"] = kind in {AnnotationKind.CALLOUT, AnnotationKind.COMMENT}
        payload["text"] = self._localizer.text(
            "annotations.default_callout_text"
            if kind is AnnotationKind.CALLOUT
            else "annotations.default_comment_text"
        )
        # Keep a freshly created box completely inside the graph body.  Near
        # the upper/lower edge the default negative offset would otherwise put
        # part of the object under the track header or outside the viewport.
        viewport_height = max(1.0, float(plot.viewport().height()))
        raw_height = payload.get("height", 76.0)
        raw_offset_y = payload.get("offset_y", -42.0)
        box_height = float(raw_height) if isinstance(raw_height, (int, float)) else 76.0
        offset_y = float(raw_offset_y) if isinstance(raw_offset_y, (int, float)) else -42.0
        local_y = float(event.position().y())
        margin = 12.0
        if local_y + offset_y < margin:
            payload["offset_y"] = margin
        elif local_y + offset_y + box_height > viewport_height - margin:
            payload["offset_y"] = -(box_height + margin)
        return payload

    @staticmethod
    def _plot_x_fraction(definition: TrackDefinition | None, x_value: float) -> float:
        if definition is not None and definition.kind is TrackKind.CALCIMETRY:
            return max(0.0, min(1.0, float(x_value) / 100.0))
        return max(0.0, min(1.0, float(x_value)))

    def _curve_value_payload(
        self, track_id: str, local_x: float, local_y: float
    ) -> dict[str, object] | None:
        if self._dataset is None:
            return None
        hit = self.hit_test_curve(track_id, local_x, local_y, tolerance_px=10.0)
        if hit is None or hit.local_y is None:
            return None
        sample_index = self._cursor_sample_index(float(hit.local_y))
        curve = self._dataset.curve_by_mnemonic(hit.target.object_id)
        if (
            sample_index is None
            or curve is None
            or sample_index >= curve.values.size
            or sample_index >= self._dataset.depth.size
        ):
            return None
        value = float(curve.values[sample_index])
        depth = float(self._dataset.depth[sample_index])
        if not np.isfinite(value) or not np.isfinite(depth):
            return None
        try:
            definition = self._layout_model.track_by_id(track_id)
        except KeyError:
            return None
        display_x = float(hit.local_x) if hit.local_x is not None else 0.5
        payload: dict[str, object] = {
            "track_id": track_id,
            "depth": depth,
            "axis_value": float(hit.local_y),
            "axis_id": self.vertical_index_id,
            "mnemonic": hit.target.object_id,
            "value": value,
            "unit": (curve.metadata.unit or "").strip(),
            "depth_unit": (self._dataset.active_index.unit or "м").strip(),
            "x_fraction": self._plot_x_fraction(definition, display_x),
        }
        time_text = format_time_curve_at_row(self._dataset, curve, sample_index)
        if time_text is not None:
            payload["display_value"] = time_text
        return payload

    @staticmethod
    def _curve_value_caption(payload: dict[str, object]) -> str:
        display_value = str(payload.get("display_value", "")).strip()
        if display_value:
            rendered_value = display_value
        else:
            unit = str(payload.get("unit", "")).strip()
            suffix = f" {unit}" if unit else ""
            raw_value = payload.get("value", 0.0)
            value = float(raw_value) if isinstance(raw_value, (int, float)) else 0.0
            rendered_value = f"{value:g}{suffix}"
        depth_unit = str(payload.get("depth_unit", "м")).strip() or "м"
        raw_depth = payload.get("depth", 0.0)
        depth = float(raw_depth) if isinstance(raw_depth, (int, float)) else 0.0
        return (
            f"{payload.get('mnemonic', '')}: {rendered_value} · "
            f"{depth:g} {depth_unit}"
        )

    def _show_curve_value_popup(
        self,
        track_id: str,
        local_x: float,
        local_y: float,
        global_pos: QPoint,
    ) -> None:
        payload = self._curve_value_payload(track_id, local_x, local_y)
        if payload is None:
            return
        menu = QMenu(self)
        value_action = menu.addAction(self._curve_value_caption(payload))
        value_action.setEnabled(False)
        menu.addSeparator()
        save_action = menu.addAction(
            self._localizer.text("annotations.save_curve_value_action")
        )
        cancel_action = menu.addAction(self._localizer.text("common.cancel"))
        chosen = menu.exec(global_pos)
        if chosen is save_action:
            self.curve_value_save_requested.emit(payload)
        elif chosen is cancel_action:
            return

    def _curve_header_selected(self, track_id: str, mnemonic: str) -> None:
        self.select_curve(track_id, mnemonic, emit_signal=True)

    def _curve_header_context(self, track_id: str, mnemonic: str, pos: QPoint) -> None:
        self.select_curve(track_id, mnemonic, emit_signal=True)
        menu = QMenu(self)
        pencil_action = menu.addAction(self._localizer.text("tablet.curve_pencil_action"))
        settings_action = (
            menu.addAction(self._localizer.text("tablet.curve_settings"))
            if self._form_edit_mode
            else None
        )
        chosen = menu.exec(pos)
        if chosen is pencil_action:
            self.curve_pencil_requested.emit(track_id, mnemonic)
        elif chosen is settings_action:
            self.track_curve_settings_requested.emit(track_id, mnemonic)

    @property
    def visible_depth_range(self) -> tuple[float, float] | None:
        # The layout model is the authoritative camera state.  Reading the first
        # pyqtgraph ViewBox here caused the toolbar to observe transient ranges
        # during widget resize/rebuild and then silently restore an older span.
        top = self._layout_model.visible_depth_top
        bottom = self._layout_model.visible_depth_bottom
        if top is not None and bottom is not None:
            ordered = sorted((float(top), float(bottom)))
            return ordered[0], ordered[1]
        first = next((entry.plot for entry in self._rendered.values() if entry.plot), None)
        if first is None:
            return None
        y_range = first.getViewBox().viewRange()[1]
        plot_top, plot_bottom = sorted((float(y_range[0]), float(y_range[1])))
        return plot_top, plot_bottom

    def track_depth_range(self, track_id: str) -> tuple[float, float]:
        rendered = self._rendered.get(track_id)
        if rendered is None or rendered.plot is None:
            raise KeyError(f"Трек не отрисован: {track_id}")
        y_range = rendered.plot.getViewBox().viewRange()[1]
        top, bottom = sorted((float(y_range[0]), float(y_range[1])))
        return top, bottom

    def set_dataset(self, dataset: Dataset | None) -> None:
        previous_id = self._dataset.dataset_id if self._dataset is not None else None
        next_id = dataset.dataset_id if dataset is not None else None
        if previous_id != next_id:
            self._analysis_interval = None
            self._analysis_interval_gesture = None
            self.interval_analysis_cleared.emit()
        self._dataset = dataset
        self._geometry_cache.clear()
        self._static_layer_cache.clear()
        self.refresh_view()

    def set_canvas_objects(self, canvas_objects: list[CanvasObject]) -> None:
        """Synchronize project canvas objects without rebuilding curves.

        An annotation edit changes only the transparent overlay. The former
        implementation called ``refresh_view()`` here, rebuilding every track,
        curve and header after each drag release and causing a full-tablet flash.
        Existing rendered tracks are now preserved and only the annotation layer
        is synchronized. Initial dataset/layout construction still owns the full
        render path.
        """

        self._canvas_objects = tuple(canvas_objects)
        if self._rendered:
            self._refresh_annotation_overlay()
        else:
            self._annotation_overlay.set_entries([])

    def set_image_assets(self, image_assets: dict[str, ImageAsset]) -> None:
        """Provide project-owned images without rebuilding tablet tracks."""

        next_assets = dict(image_assets)
        if next_assets == self._image_assets:
            return
        self._image_assets = next_assets
        if self._rendered:
            self._refresh_annotation_overlay()

    def set_annotation_print_mode(self, enabled: bool) -> None:
        """Hide screen-only annotations while a PDF/print snapshot is captured."""

        self._annotation_print_mode = bool(enabled)
        for rendered in self._rendered.values():
            for item in (rendered.annotation_items or {}).values():
                item.set_print_mode(self._annotation_print_mode)
        self._annotation_overlay.set_print_mode(self._annotation_print_mode)

    def annotation_request_at_view_center(
        self,
        kind: AnnotationKind | str,
        *,
        track_id: str | None = None,
    ) -> dict[str, object] | None:
        if self._dataset is None or not self._layout_model.tracks:
            return None
        try:
            normalized_kind = (
                kind
                if isinstance(kind, AnnotationKind)
                else AnnotationKind(str(kind))
            )
        except ValueError:
            return None
        selected_track = track_id
        if selected_track is None or not any(
            track.track_id == selected_track for track in self._layout_model.tracks
        ):
            selected_track = next(
                (
                    track.track_id
                    for track in self._layout_model.tracks
                    if track.kind is not TrackKind.DEPTH
                ),
                self._layout_model.tracks[0].track_id,
            )
        visible = self.visible_depth_range or self._axis_bounds()
        if visible is None:
            return None
        axis_value = (visible[0] + visible[1]) / 2.0
        depth = self._axis_to_depth_value(axis_value)
        return self._annotation_request_payload(
            track_id=selected_track,
            depth=depth,
            axis_value=axis_value,
            x_fraction=0.5,
            kind=normalized_kind,
        )

    def set_lithology(
        self,
        intervals: list[LithologyInterval],
        catalog: tuple[CatalogLithotype, ...],
    ) -> None:
        self._lithology = tuple(intervals)
        self._lithotype_catalog = {item.lithotype_id: item for item in catalog}
        self.refresh_view()

    @property
    def geological_input_mode(self) -> GeologicalInputMode:
        return self._geological_input_mode

    def set_geological_input_mode(self, mode: GeologicalInputMode | str) -> None:
        """Select a creation/edit tool while retaining Shift+drag shortcuts."""

        self.cancel_lithology_interaction()
        self.cancel_sample_interaction()
        self.cancel_stratigraphy_interaction()
        self._geological_input_mode = GeologicalInputMode(mode)
        self._apply_geological_mode_cursors()

    def _apply_geological_mode_cursors(self) -> None:
        self._apply_curve_pencil_cursors()

    def _apply_geological_mode_cursors_base(self) -> None:
        for rendered in self._rendered.values():
            if rendered.plot is None:
                continue
            kind = rendered.definition.kind
            active = (
                (
                    self._geological_input_mode is GeologicalInputMode.LITHOLOGY
                    and kind is TrackKind.LITHOLOGY
                )
                or (
                    self._geological_input_mode is GeologicalInputMode.SAMPLE
                    and kind in {TrackKind.CUTTINGS, TrackKind.CALCIMETRY, TrackKind.LBA}
                )
                or (
                    self._geological_input_mode is GeologicalInputMode.STRATIGRAPHY
                    and kind is TrackKind.STRATIGRAPHY
                )
                or (
                    self._geological_input_mode is GeologicalInputMode.DESCRIPTION
                    and kind is TrackKind.TEXT
                )
                or (
                    self._geological_input_mode is GeologicalInputMode.EDIT
                    and kind
                    in {
                        TrackKind.LITHOLOGY,
                        TrackKind.CUTTINGS,
                        TrackKind.CALCIMETRY,
                        TrackKind.LBA,
                        TrackKind.STRATIGRAPHY,
                        TrackKind.TEXT,
                    }
                )
            )
            cursor = Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor
            rendered.plot.viewport().setCursor(cursor)
            rendered.plot.setCursor(cursor)

    def set_cuttings(self, samples: list[CuttingsSample]) -> None:
        self._cuttings = tuple(samples)
        self.refresh_view()

    def stratigraphy_interval_at_depth(self, depth: float) -> StratigraphyInterval | None:
        value = float(depth)
        matches = [
            item for item in self._stratigraphy if item.top_depth <= value < item.bottom_depth
        ]
        if not matches:
            matches = [item for item in self._stratigraphy if value == item.bottom_depth]
        if not matches:
            return None
        return min(
            matches,
            key=lambda item: (
                item.bottom_depth - item.top_depth,
                -stratigraphy_rank_order(item.rank)[0],
                item.interval_id,
            ),
        )

    def lithology_interval_at_depth(self, depth: float) -> LithologyInterval | None:
        value = float(depth)
        # Use half-open intervals so a shared boundary belongs to the deeper
        # interval.  The final bottom is accepted as a fallback for usability.
        matches = [item for item in self._lithology if item.top_depth <= value < item.bottom_depth]
        if not matches:
            matches = [item for item in self._lithology if np.isclose(item.bottom_depth, value)]
        return max(matches, key=lambda item: item.top_depth) if matches else None

    def cuttings_sample_at_depth(self, depth: float) -> CuttingsSample | None:
        value = float(depth)
        matches = [item for item in self._cuttings if item.top_depth <= value < item.bottom_depth]
        if not matches:
            matches = [item for item in self._cuttings if np.isclose(item.bottom_depth, value)]
        return max(matches, key=lambda item: item.top_depth) if matches else None

    def set_stratigraphy(self, intervals: list[StratigraphyInterval]) -> None:
        self._stratigraphy = tuple(intervals)
        self.refresh_view()

    def set_layout_model(self, layout_model: TabletLayout) -> None:
        previous_range = self.visible_depth_range
        previous_index = self.vertical_index_id
        same_axis = (
            previous_index is None
            or layout_model.vertical_index_id is None
            or layout_model.vertical_index_id == previous_index
        )
        if (
            previous_range is not None
            and same_axis
            and layout_model.visible_depth_top is None
            and layout_model.visible_depth_bottom is None
        ):
            # Changing a form/layout must not throw away the user's current
            # depth scale and scroll position.  The range is normalized against
            # the dataset during refresh, so it remains safe for the new tracks.
            layout_model.set_visible_depth(*previous_range)
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
            if rendered.cursor_label is not None:
                rendered.cursor_label.setVisible(enabled and self._cursor_depth is not None)
        if enabled and self._cursor_depth is None:
            depth_range = self.visible_depth_range
            if depth_range is not None:
                self.set_cursor_depth(sum(depth_range) / 2.0)
        elif enabled and self._cursor_depth is not None:
            self._update_cursor_labels(self._cursor_depth)

    def set_cursor_depth(self, depth: float) -> None:
        if self._dataset is None or not np.isfinite(depth):
            return
        finite = self._axis_values()
        finite = finite[np.isfinite(finite)]
        if not finite.size:
            return
        bounded = min(max(float(depth), float(np.min(finite))), float(np.max(finite)))
        bounded = float(finite[int(np.argmin(np.abs(finite - bounded)))])
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
        self._update_cursor_labels(bounded)
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
        depth_unit = self._localizer.text("tablet.depth_span_unit")
        depth_index = next(
            (item for item in self._dataset.indexes.values() if item.role is IndexRole.DEPTH),
            None,
        )
        if depth_index is not None and depth_index.unit:
            depth_unit = depth_index.unit
        values = [f"{self._localizer.text('cursor.depth')}: {sample_depth:g} {depth_unit}"]
        descriptor = self._axis_descriptor()
        absolute_datetime = format_datetime_at_row(self._dataset, index)
        if absolute_datetime is not None:
            values.insert(
                0,
                f"{self._localizer.text('cursor.datetime')}: {absolute_datetime}",
            )
        elif descriptor is not None and descriptor.is_time:
            values.insert(
                0,
                f"{self._localizer.text('cursor.time')}: "
                f"{self._format_axis_value(float(axis_values[index]))}",
            )
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
                f"{self._localizer.text('cursor.lithology')}: {rock} "
                f"({interval.top_depth:g}–{interval.bottom_depth:g} {depth_unit})"
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
                f"{self._localizer.text('cursor.stratigraphy')}: {label} "
                f"({stratigraphy.top_depth:g}–{stratigraphy.bottom_depth:g} {depth_unit})"
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
                        f"{self._localizer.text('cursor.interpretation')} «{interpretation.name}»: "
                        f"{interpretation_interval.interval_type} / "
                        f"{interpretation_interval.label} "
                        f"({interpretation_interval.top_depth:g}–"
                        f"{interpretation_interval.bottom_depth:g} {depth_unit})"
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
                    f"{self._localizer.text('cursor.cuttings')} "
                    f"{sample.top_depth:g}–{sample.bottom_depth:g} {depth_unit}: "
                    + "; ".join(parts)
                )
            if sample.calcite_percent is not None or sample.dolomite_percent is not None:
                residue = sample.insoluble_residue_percent
                values.append(
                    f"{self._localizer.text('cursor.calcimetry')}: "
                    f"CaCO₃ {sample.calcite_percent or 0.0:g}%; "
                    f"CaMg(CO₃)₂ {sample.dolomite_percent or 0.0:g}%"
                    + (
                        f"; {self._localizer.text('cursor.insoluble_residue')} {residue:g}%"
                        if residue is not None
                        else ""
                    )
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
                values.append(
                    f"{self._localizer.text('cursor.lba')}: "
                    + "; ".join(value for value in lba if value)
                )
            if sample.analysis_interpretation:
                values.append(
                    f"{self._localizer.text('cursor.geologist_interpretation')}: "
                    + sample.analysis_interpretation
                )
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
                display_name = self._curve_display_name(definition, mnemonic, curve)
                time_text = format_time_curve_at_row(self._dataset, curve, index)
                if time_text is not None:
                    values.append(f"{display_name} [{mnemonic}]: {time_text}")
                else:
                    values.append(
                        f"{display_name} [{mnemonic}]: {value:g}"
                        f"{f' {unit}' if unit else ''}"
                    )
                seen.add(mnemonic)
        return " | ".join(values)

    def add_track(self, definition: TrackDefinition) -> None:
        self._layout_model.add_track(definition)
        self.refresh_view()

    def remove_track(self, track_id: str) -> None:
        self._layout_model.remove_track(track_id)
        self.refresh_view()

    def clear(self) -> None:
        self.cancel_curve_pencil_gesture()
        self.cancel_interval_interaction(emit_signal=False)
        self.cancel_lithology_interaction()
        self.cancel_sample_interaction()
        self.cancel_interval_analysis(clear_interval=False)
        self._dirty_registry.clear()
        self._overlay_layers.clear()
        self._tooltip_items.clear()
        self._rubber_band_items.clear()
        self._depth_viewports.clear()
        self._wheel_targets.clear()
        self._interpretation_viewports.clear()
        self._annotation_overlay.set_entries([])
        for layout in (self._group_header_layout, self._tracks_layout):
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
            label = QLabel(self._localizer.text("tablet.empty"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tracks_layout.addWidget(label)
            self._refresh_curve_pencil_targets()
            return

        visible = self._layout_model.visible_tracks()
        if not visible:
            label = QLabel(self._localizer.text("tablet.empty_add_track"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tracks_layout.addWidget(label)
            self._refresh_curve_pencil_targets()
            return

        depth = self._axis_values()
        finite_depth = depth[np.isfinite(depth)]
        visible_top = self._layout_model.visible_depth_top
        visible_bottom = self._layout_model.visible_depth_bottom
        if finite_depth.size and (visible_top is None or visible_bottom is None):
            data_top = float(np.min(finite_depth))
            data_bottom = float(np.max(finite_depth))
            descriptor = self._axis_descriptor()
            visible_top, visible_bottom = recommended_initial_range(
                data_top,
                data_bottom,
                is_time=descriptor.is_time if descriptor is not None else False,
                is_datetime=descriptor.is_datetime if descriptor is not None else False,
                unit=descriptor.unit if descriptor is not None else "",
            )
            self._layout_model.set_visible_depth(visible_top, visible_bottom)
        elif visible_top is not None and visible_bottom is not None:
            visible_top, visible_bottom = self._normalize_depth_window(visible_top, visible_bottom)
            self._layout_model.set_visible_depth(visible_top, visible_bottom)

        master_plot: pg.PlotWidget | None = None
        axis_descriptor = self._axis_descriptor()
        for definition in visible:
            track = TabletTrackWidget(definition, self._navigation_hint, axis_descriptor)
            track.title.setText(self._localized_track_title(definition))
            if definition.kind is TrackKind.LITHOLOGY:
                track.plot.setToolTip(self._localizer.text("lithology.drag_hint"))
                track.title.setToolTip(self._localizer.text("lithology.drag_hint"))
            elif definition.kind in {
                TrackKind.CUTTINGS,
                TrackKind.CALCIMETRY,
                TrackKind.LBA,
                TrackKind.TEXT,
            }:
                hint = self._localizer.text("cuttings.drag_hint")
                track.plot.setToolTip(hint)
                track.title.setToolTip(hint)
            elif definition.kind in {
                TrackKind.DEPTH,
                TrackKind.CURVE,
                TrackKind.GAS,
                TrackKind.DEXP,
            }:
                hint = (
                    f"{self._navigation_hint}\n"
                    f"{self._localizer.text('statistics.drag_hint')}"
                )
                track.plot.setToolTip(hint)
                track.title.setToolTip(hint)
            track.selected.connect(self._track_selected_from_widget)
            track.width_change_requested.connect(self._resize_track_from_widget)
            track.header_drag_started.connect(self._start_track_header_drag)
            track.header_drag_moved.connect(self._move_track_header_drag)
            track.header_drag_finished.connect(self._finish_track_header_drag)
            track.context_requested.connect(self.show_track_context_menu)
            track.edit_requested.connect(self.track_full_edit_requested.emit)
            track.curve_selected.connect(self._curve_header_selected)
            track.curve_context_requested.connect(self._curve_header_context)
            (
                legend_labels,
                curve_items,
                relative_fill_items,
                relative_baseline_item,
            ) = self._populate_track(
                track,
                definition,
                visible_top,
                visible_bottom,
            )
            # Professional annotations are rendered once by the tablet-wide
            # overlay.  Keeping them in a ViewBox clipped movement at column
            # borders and duplicated track-less comments.
            annotation_items: dict[str, TabletAnnotationItem] = {}
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
                relative_fill_items=relative_fill_items,
                relative_baseline_item=relative_baseline_item,
            )
            self._rendered[definition.track_id] = rendered
            self._install_analysis_region(rendered)
            self._register_track_overlays(rendered)
            self._install_cursor(rendered)
            if definition.kind is TrackKind.INTERPRETATION:
                track.plot.scene().sigMouseClicked.connect(
                    lambda event, entry=rendered: self._interpretation_plot_clicked(entry, event)
                )
            viewport = track.plot.viewport()
            viewport.installEventFilter(self)
            self._depth_viewports[viewport] = track.plot
            self._register_wheel_targets(track, track.plot)
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
            self._tracks_layout.addWidget(track)

        total_width = sum(track.width + 2 for track in visible)
        self._container.setFixedWidth(max(total_width, 1))
        self._tracks_container.setFixedWidth(max(total_width, 1))
        self._rebuild_group_headers()
        self._synchronize_track_header_bands()
        self._apply_geological_mode_cursors()
        self._synchronize_track_heights()
        if master_plot is not None and visible_top is not None and visible_bottom is not None:
            self._synchronize_depth_ranges(visible_top, visible_bottom)
            self._update_lithology_text_visibility(visible_top, visible_bottom)
            self._update_stratigraphy_text_visibility(visible_top, visible_bottom)
            self._apply_interpretation_selection_style()
        self._apply_track_selection_style()
        self._apply_curve_selection_style()
        if self._cursor_depth is not None:
            self._update_cursor_labels(self._cursor_depth)
        self._update_navigation_controls()
        self._refresh_curve_pencil_targets()
        self._refresh_annotation_overlay()
        # refresh_view is commonly executed before the widget receives its final
        # on-screen geometry. Reuse the instance timer after Qt has laid out the
        # horizontal scrollbar and the final chart viewport.
        self._resize_restore_timer.start(0)

    @property
    def interval_analysis_range(self) -> tuple[float, float] | None:
        return self._analysis_interval

    def visible_curve_mnemonics(self) -> tuple[str, ...]:
        if self._dataset is None:
            return ()
        result: list[str] = []
        seen: set[str] = set()
        for definition in self._layout_model.visible_tracks():
            for mnemonic in definition.curve_mnemonics:
                curve = self._dataset.curve_by_mnemonic(mnemonic)
                if curve is None:
                    continue
                original = curve.metadata.original_mnemonic
                key = original.casefold()
                if key in seen:
                    continue
                seen.add(key)
                result.append(original)
        return tuple(result)

    def begin_interval_analysis(self, track_id: str, axis_value: float) -> bool:
        rendered = self._rendered.get(track_id)
        if (
            self._dataset is None
            or rendered is None
            or rendered.plot is None
            or rendered.definition.kind
            not in {TrackKind.DEPTH, TrackKind.CURVE, TrackKind.GAS, TrackKind.DEXP}
            or self._form_edit_mode
            or self._curve_pencil_enabled
            or self._annotation_tool is not None
        ):
            return False
        snapped = self._snap_analysis_axis_value(axis_value)
        if snapped is None:
            return False
        self._analysis_interval_gesture = _AnalysisIntervalGesture(track_id, snapped, snapped)
        self._analysis_interval = (snapped, snapped)
        self._update_analysis_regions()
        rendered.plot.viewport().setCursor(Qt.CursorShape.CrossCursor)
        return True

    def update_interval_analysis(self, axis_value: float) -> bool:
        gesture = self._analysis_interval_gesture
        if gesture is None:
            return False
        snapped = self._snap_analysis_axis_value(axis_value)
        if snapped is None:
            return False
        gesture.current_value = snapped
        ordered = sorted((gesture.start_value, snapped))
        self._analysis_interval = (ordered[0], ordered[1])
        self._update_analysis_regions()
        return True

    def finish_interval_analysis(self, axis_value: float) -> bool:
        gesture = self._analysis_interval_gesture
        if gesture is None:
            return False
        self.update_interval_analysis(axis_value)
        interval = self._analysis_interval
        self._analysis_interval_gesture = None
        rendered = self._rendered.get(gesture.track_id)
        if rendered is not None and rendered.plot is not None:
            rendered.plot.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        if interval is None or interval[0] >= interval[1]:
            self.clear_interval_analysis(emit_signal=False)
            return True
        descriptor = self._axis_descriptor()
        self.interval_analysis_requested.emit(
            {
                "top": interval[0],
                "bottom": interval[1],
                "axis_id": descriptor.index_id if descriptor is not None else "",
                "axis_label": descriptor.label if descriptor is not None else "",
                "axis_unit": descriptor.unit if descriptor is not None else "",
                "axis_is_datetime": descriptor.is_datetime if descriptor is not None else False,
                "mnemonics": self.visible_curve_mnemonics(),
            }
        )
        return True

    def cancel_interval_analysis(self, *, clear_interval: bool = False) -> bool:
        gesture = self._analysis_interval_gesture
        changed = gesture is not None
        self._analysis_interval_gesture = None
        if gesture is not None:
            rendered = self._rendered.get(gesture.track_id)
            if rendered is not None and rendered.plot is not None:
                rendered.plot.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        if clear_interval:
            changed = self.clear_interval_analysis(emit_signal=False) or changed
        return changed

    def clear_interval_analysis(self, *, emit_signal: bool = True) -> bool:
        if self._analysis_interval is None and self._analysis_interval_gesture is None:
            return False
        self._analysis_interval = None
        self._analysis_interval_gesture = None
        self._update_analysis_regions()
        if emit_signal:
            self.interval_analysis_cleared.emit()
        return True

    def _snap_analysis_axis_value(self, value: float) -> float | None:
        axis = self._axis_values()
        finite = np.flatnonzero(np.isfinite(axis))
        if finite.size == 0 or not np.isfinite(value):
            return None
        nearest = int(finite[np.argmin(np.abs(axis[finite] - float(value)))])
        return float(axis[nearest])

    def _install_analysis_region(self, rendered: RenderedTrack) -> None:
        if rendered.plot is None:
            return
        region = pg.LinearRegionItem(
            values=self._analysis_interval or (0.0, 0.0),
            orientation=pg.LinearRegionItem.Horizontal,
            movable=False,
            brush=pg.mkBrush(37, 99, 235, 42),
            pen=pg.mkPen("#2563eb", width=1.3, style=Qt.PenStyle.DashLine),
        )
        region.setZValue(72)
        rendered.plot.addItem(region, ignoreBounds=True)
        rendered.analysis_region = region
        region.setVisible(self._analysis_interval is not None)

    def _update_analysis_regions(self) -> None:
        for rendered in self._rendered.values():
            region = rendered.analysis_region
            if region is None:
                continue
            if self._analysis_interval is None:
                region.hide()
            else:
                region.setRegion(self._analysis_interval)
                region.show()

    def _rebuild_group_headers(self) -> None:
        """Build merged section captions aligned with contiguous form columns."""

        while self._group_header_layout.count():
            item = self._group_header_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        visible = self._layout_model.visible_tracks()
        if not visible or not any(track.group_title.strip() for track in visible):
            self._group_header_container.hide()
            self._group_header_container.setFixedHeight(0)
            return

        groups: list[tuple[str, int]] = []
        for track in visible:
            title = track.group_title.strip()
            width = int(track.width) + 2
            if groups and groups[-1][0] == title:
                previous_title, previous_width = groups[-1]
                groups[-1] = (previous_title, previous_width + width)
            else:
                groups.append((title, width))

        for title, width in groups:
            label = QLabel(title or " ")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(max(1, width - 2))
            label.setFixedHeight(30)
            label.setStyleSheet(
                "font-weight: 700; padding: 4px; "
                "background: #eef2f7; color: #0f172a; "
                "border: 1px solid #94a3b8;"
            )
            self._group_header_layout.addWidget(label)
        self._group_header_container.setFixedHeight(30)
        self._group_header_container.show()

    def _synchronize_track_header_bands(self) -> None:
        """Align the plot viewport origin for every visible Masterlog column.

        All plots can share exactly the same numeric Y range and still look
        vertically shifted when their title/header widgets consume different
        heights.  A Masterlog requires one horizontal parameter-header band,
        therefore every track reserves the maximum natural header height of
        the current form, including depth and special interval tracks.
        """

        title_height = max(
            (entry.widget.natural_title_header_height for entry in self._rendered.values()),
            default=36,
        )
        curve_height = max(
            (entry.widget.natural_curve_header_height for entry in self._rendered.values()),
            default=0,
        )
        for rendered in self._rendered.values():
            rendered.widget.set_synchronized_title_header_height(title_height)
            rendered.widget.set_synchronized_header_height(curve_height)

    def _synchronize_track_heights(self) -> None:
        """Give every track one identical chart-body height.

        The horizontal scrollbar belongs to the common scroll area. Using merely
        a minimum height allowed some tracks to expand into the
        scrollbar's row, so the same 50 m range occupied a different number of
        pixels.  Fixing every track to the scroll viewport height keeps the top
        and bottom depth coordinates pixel-aligned.
        """

        group_height = 30 if self._group_header_container.isVisible() else 0
        height = max(self._scroll.viewport().height() - group_height, 240)
        self._tracks_container.setFixedHeight(height)
        self._container.setFixedHeight(height + group_height)
        for rendered in self._rendered.values():
            rendered.widget.setFixedHeight(height)

    def _register_wheel_targets(self, root: QWidget, plot: pg.PlotWidget) -> None:
        """Route wheel navigation from every visible part of a tablet column.

        Qt sends wheel events to the deepest child under the cursor. Registering
        only the plot viewport leaves curve-header labels and nested widgets
        outside the depth navigation path, which feels like intermittent broken
        scrolling.
        """

        targets: list[QWidget] = [root, *root.findChildren(QWidget)]
        for target in targets:
            target.installEventFilter(self)
            self._wheel_targets[target] = plot

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._synchronize_track_heights()
        self._sync_annotation_overlay_geometry()
        # pyqtgraph may briefly recalculate a ViewBox while the form/tablet is
        # being resized. Re-assert the camera range after Qt finishes geometry
        # processing so the selected metres-on-screen value cannot be lost.
        self._resize_restore_timer.start(0)

    def _restore_visible_depth_after_resize(self) -> None:
        if not self._rendered:
            return
        self._synchronize_track_header_bands()
        self._synchronize_track_heights()
        current = self.visible_depth_range
        if current is None:
            return
        self._synchronize_depth_ranges(*current)
        self._update_navigation_controls()
        self._refresh_annotation_overlay()

    def _register_track_overlays(self, rendered: RenderedTrack) -> None:
        track_id = rendered.definition.track_id
        for annotation_item in (rendered.annotation_items or {}).values():
            self._overlay_layers.register(
                OverlayLayerKind.MARKER, track_id, annotation_item
            )
        for label_item in (rendered.lithology_label_items or {}).values():
            self._overlay_layers.register(
                OverlayLayerKind.ANNOTATION, track_id, label_item
            )
        for description_item in (rendered.lithology_description_items or {}).values():
            self._overlay_layers.register(
                OverlayLayerKind.ANNOTATION, track_id, description_item
            )
        for items in (rendered.stratigraphy_items or {}).values():
            for graphics_item in items:
                if hasattr(graphics_item, "setZValue") and hasattr(
                    graphics_item, "setVisible"
                ):
                    kind = (
                        OverlayLayerKind.ANNOTATION
                        if isinstance(graphics_item, pg.TextItem)
                        else OverlayLayerKind.MARKER
                    )
                    self._overlay_layers.register(kind, track_id, graphics_item)
        for items in (rendered.interpretation_items or {}).values():
            for graphics_item in items:
                if hasattr(graphics_item, "setZValue") and hasattr(
                    graphics_item, "setVisible"
                ):
                    kind = (
                        OverlayLayerKind.ANNOTATION
                        if isinstance(graphics_item, pg.TextItem)
                        else OverlayLayerKind.MARKER
                    )
                    self._overlay_layers.register(kind, track_id, graphics_item)

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
        label = pg.TextItem(
            "",
            color="#0f172a",
            fill=pg.mkBrush(255, 255, 255, 225),
            border=pg.mkPen("#dc2626", width=1),
            anchor=(0.0, 1.0),
        )
        label.setZValue(10_001)
        label.setVisible(self._cursor_enabled and self._cursor_depth is not None)
        rendered.plot.addItem(label)
        rendered.cursor_label = label
        self._overlay_layers.register(OverlayLayerKind.CURSOR, rendered.definition.track_id, line)
        self._overlay_layers.register(OverlayLayerKind.CURSOR, rendered.definition.track_id, label)
        rendered.plot.scene().sigMouseClicked.connect(
            lambda event, entry=rendered: self._cursor_plot_clicked(entry, event)
        )

    def _cursor_sample_index(self, axis_value: float) -> int | None:
        if self._dataset is None:
            return None
        axis_values = self._axis_values()
        valid = np.flatnonzero(np.isfinite(axis_values))
        if not valid.size:
            return None
        return int(valid[np.argmin(np.abs(axis_values[valid] - float(axis_value)))])

    def _cursor_track_text(self, rendered: RenderedTrack, sample_index: int) -> str:
        if self._dataset is None:
            return ""
        definition = rendered.definition
        if definition.kind is TrackKind.DEPTH:
            axis_values = self._axis_values()
            if sample_index >= axis_values.size:
                return ""
            descriptor = self._axis_descriptor()
            unit = descriptor.unit if descriptor is not None else ""
            axis_text = self._format_axis_value(float(axis_values[sample_index]))
            key = "cursor.time" if descriptor is not None and descriptor.is_time else "cursor.depth"
            return f"{self._localizer.text(key)}: {axis_text}{f' {unit}' if unit else ''}"

        lines: list[str] = []
        for mnemonic in definition.curve_mnemonics:
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None or sample_index >= curve.values.size:
                continue
            curve_value = float(curve.values[sample_index])
            if not np.isfinite(curve_value):
                continue
            name = self._curve_display_name(definition, mnemonic, curve)
            unit = (curve.metadata.unit or "").strip()
            time_text = format_time_curve_at_row(self._dataset, curve, sample_index)
            if time_text is not None:
                lines.append(f"{name}: {time_text}")
            else:
                lines.append(f"{name}: {curve_value:g}{f' {unit}' if unit else ''}")
        return "\n".join(lines)

    def _update_cursor_labels(self, axis_value: float) -> None:
        sample_index = self._cursor_sample_index(axis_value)
        if sample_index is None:
            return
        for rendered in self._rendered.values():
            label = rendered.cursor_label
            if label is None:
                continue
            text = self._cursor_track_text(rendered, sample_index)
            label.setText(text)
            label.setPos(0.015, float(axis_value))
            label.setVisible(self._cursor_enabled and bool(text))

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
        """Depth columns now follow the form order instead of being detached."""

        return ()

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
            self._span_combo,
            self._vertical_scrollbar,
        ):
            widget.setEnabled(enabled)
        if not enabled or current is None or bounds is None:
            self._range_label.setText("—")
            self._vertical_scrollbar.setRange(0, 0)
            return
        top, bottom = current
        data_top, data_bottom = bounds
        visible_span = bottom - top
        self._range_label.setText(
            self._localizer.text(
                "tablet.visible_range",
                top=self._format_axis_value(top),
                bottom=self._format_axis_value(bottom),
                span=self._format_vertical_span(visible_span),
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
        self._sync_depth_span_control(visible_span)
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

    def _depth_span_selected(self, row: int) -> None:
        if self._span_combo_guard or row < 0:
            return
        raw = self._span_combo.itemData(row)
        if raw is None:
            current = self.visible_depth_range
            initial = (current[1] - current[0]) if current is not None else 50.0
            span, accepted = QInputDialog.getDouble(
                self,
                self._localizer.text("tablet.depth_span"),
                self._localizer.text("tablet.depth_span_prompt"),
                float(initial),
                0.001,
                1_000_000.0,
                3,
            )
            if not accepted:
                self._sync_depth_span_control(initial)
                return
        else:
            span = float(raw)
        current = self.visible_depth_range
        top = current[0] if current is not None else None
        self.set_vertical_span(span, top=top)

    def _depth_span_typed(self) -> None:
        self._span_edit_timer.stop()
        if self._span_combo_guard:
            return
        line_edit = self._span_combo.lineEdit()
        if line_edit is None:
            return
        if not self._apply_depth_span_text(line_edit.text()):
            current = self.visible_depth_range
            if current is not None:
                self._sync_depth_span_control(current[1] - current[0])

    def _depth_span_text_edited(self, text: str) -> None:
        if self._span_combo_guard:
            return
        # Do not mutate the combo contents while the user is still typing a
        # multi-digit value. The timer commits the complete number automatically.
        normalized = text.strip().casefold()
        unit = self._vertical_span_unit().casefold()
        if unit and normalized.endswith(unit):
            normalized = normalized[: -len(unit)].strip()
        try:
            span = float(normalized.replace(",", "."))
        except ValueError:
            self._span_edit_timer.stop()
            return
        if np.isfinite(span) and span > 0:
            self._span_edit_timer.start()
        else:
            self._span_edit_timer.stop()

    def _apply_depth_span_text(self, text: str) -> bool:
        normalized = text.strip().casefold()
        unit = self._vertical_span_unit().casefold()
        if unit and normalized.endswith(unit):
            normalized = normalized[: -len(unit)].strip()
        try:
            span = float(normalized.replace(",", "."))
        except ValueError:
            return False
        if not np.isfinite(span) or span <= 0:
            return False
        current = self.visible_depth_range
        top = current[0] if current is not None else None
        return self.set_vertical_span(span, top=top)

    def _vertical_span_unit(self) -> str:
        descriptor = self._axis_descriptor()
        # Depth windows are presented in the localized metre label even when the
        # LAS header stores the ASCII unit ``m``.  Mixing ``м`` in the editor with
        # ``m`` in the parser made a valid value such as ``30 м`` fail silently.
        if descriptor is None or descriptor.role is IndexRole.DEPTH:
            return self._localizer.text("tablet.depth_span_unit")
        if descriptor.unit:
            return descriptor.unit
        return self._localizer.text("tablet.depth_span_unit")

    def _format_vertical_span(self, span: float) -> str:
        return f"{float(span):g} {self._vertical_span_unit()}".strip()

    def _sync_depth_span_control(self, visible_span: float) -> None:
        if not np.isfinite(visible_span) or visible_span <= 0:
            return
        unit = self._vertical_span_unit()
        matching_row = -1
        self._span_combo_guard = True
        self._span_combo.blockSignals(True)
        try:
            for row in range(self._span_combo.count()):
                raw = self._span_combo.itemData(row)
                if raw is None:
                    self._span_combo.setItemText(
                        row, self._localizer.text("tablet.depth_span_custom")
                    )
                    continue
                self._span_combo.setItemText(row, f"{float(raw):g} {unit}")
                if np.isclose(float(raw), visible_span, rtol=0.0, atol=1e-6):
                    matching_row = row
            if matching_row >= 0:
                self._span_combo.setCurrentIndex(matching_row)
            else:
                self._span_combo.setEditText(f"{visible_span:g} {unit}")
        finally:
            self._span_combo.blockSignals(False)
            self._span_combo_guard = False

    def set_vertical_span(
        self,
        span: float,
        *,
        center: float | None = None,
        top: float | None = None,
    ) -> bool:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        if current is None or bounds is None or not np.isfinite(span) or span <= 0:
            return False
        data_span = bounds[1] - bounds[0]
        requested = min(float(span), data_span)
        if top is not None and np.isfinite(top):
            window_top = float(top)
            window_bottom = window_top + requested
        else:
            anchor = float(center) if center is not None else sum(current) / 2.0
            window_top = anchor - requested / 2.0
            window_bottom = anchor + requested / 2.0
        return self._apply_visible_depth(window_top, window_bottom, emit_change=True)

    def set_visible_depth(self, top: float, bottom: float) -> None:
        self._apply_visible_depth(top, bottom, emit_change=False)

    def scroll_depth(self, steps: float) -> bool:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        if current is None or bounds is None or not np.isfinite(steps) or steps == 0:
            return False
        self._sync_camera(bounds, current)
        domain_span = bounds[1] - bounds[0]
        current_span = current[1] - current[0]
        if np.isclose(current_span, domain_span, rtol=0.0, atol=max(domain_span, 1.0) * 1e-9):
            descriptor = self._axis_descriptor()
            initial_span = recommended_initial_span(
                domain_span,
                is_time=descriptor.is_time if descriptor is not None else False,
                is_datetime=descriptor.is_datetime if descriptor is not None else False,
                unit=descriptor.unit if descriptor is not None else "",
            )
            if initial_span < domain_span:
                if steps > 0:
                    current = (bounds[0], bounds[0] + initial_span)
                else:
                    current = (bounds[1] - initial_span, bounds[1])
                self._sync_camera(bounds, current)
        top, bottom = self._camera.pan_fraction(0.10 * float(steps))
        return self._apply_visible_depth(top, bottom, emit_change=True)

    def zoom_depth(self, factor: float, anchor: float | None = None) -> bool:
        current = self.visible_depth_range
        bounds = self._axis_bounds()
        if current is None or bounds is None or not np.isfinite(factor) or factor <= 0:
            return False
        self._sync_camera(bounds, current)
        top, bottom = self._camera.zoom(float(factor), anchor=anchor)
        return self._apply_visible_depth(top, bottom, emit_change=True)

    def _sync_camera(self, bounds: tuple[float, float], current: tuple[float, float]) -> None:
        self._camera.set_domain(*bounds, preserve_window=False)
        self._camera.set_visible_range(*current)

    def _axis_value_at_event(
        self,
        plot: pg.PlotWidget,
        watched: QObject,
        event: QMouseEvent | QWheelEvent,
    ) -> float | None:
        try:
            local_position = event.position().toPoint()
            if isinstance(watched, QWidget):
                global_position = watched.mapToGlobal(local_position)
                viewport_position = plot.viewport().mapFromGlobal(global_position)
            else:
                viewport_position = local_position
            scene_position = plot.mapToScene(viewport_position)
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

    @staticmethod
    def _annotation_ancestor(item: object | None) -> TabletAnnotationItem | None:
        """Resolve a graphics-scene hit or child to its annotation item."""

        current = item
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            if isinstance(current, TabletAnnotationItem):
                return current
            parent_item = getattr(current, "parentItem", None)
            current = parent_item() if callable(parent_item) else None
        return None

    @staticmethod
    def _pointer_button(button: Qt.MouseButton) -> PointerButton:
        if button == Qt.MouseButton.LeftButton:
            return PointerButton.LEFT
        if button == Qt.MouseButton.RightButton:
            return PointerButton.RIGHT
        if button == Qt.MouseButton.MiddleButton:
            return PointerButton.MIDDLE
        return PointerButton.NONE

    @classmethod
    def _pressed_pointer_buttons(cls, buttons: Qt.MouseButton) -> frozenset[PointerButton]:
        pressed: set[PointerButton] = set()
        for qt_button in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.MiddleButton,
        ):
            if buttons & qt_button:
                pressed.add(cls._pointer_button(qt_button))
        return frozenset(pressed)

    @staticmethod
    def _key_name(event: QKeyEvent) -> str | None:
        keys: dict[int, str] = {
            int(Qt.Key.Key_Escape): "escape",
            int(Qt.Key.Key_Return): "return",
            int(Qt.Key.Key_Enter): "enter",
            int(Qt.Key.Key_F2): "f2",
            int(Qt.Key.Key_Delete): "delete",
            int(Qt.Key.Key_Backspace): "backspace",
        }
        return keys.get(event.key())

    def _tablet_input_from_mouse(
        self,
        plot: pg.PlotWidget | None,
        event: QMouseEvent,
    ) -> TabletInputEvent:
        kind = {
            QEvent.Type.MouseButtonPress: InputEventKind.POINTER_PRESS,
            QEvent.Type.MouseMove: InputEventKind.POINTER_MOVE,
            QEvent.Type.MouseButtonRelease: InputEventKind.POINTER_RELEASE,
            QEvent.Type.MouseButtonDblClick: InputEventKind.POINTER_DOUBLE_CLICK,
        }.get(event.type(), InputEventKind.POINTER_MOVE)
        global_point = event.globalPosition().toPoint()
        canvas_point = self._tracks_container.mapFromGlobal(global_point)
        return TabletInputEvent(
            kind=kind,
            x=float(canvas_point.x()),
            y=float(canvas_point.y()),
            track_id=self._track_id_for_plot(plot) if plot is not None else None,
            button=self._pointer_button(event.button()),
            pressed_buttons=self._pressed_pointer_buttons(event.buttons()),
            global_x=global_point.x(),
            global_y=global_point.y(),
            payload=_QtPointerPayload(plot, event),
        )

    def _tablet_input_from_key(
        self,
        plot: pg.PlotWidget | None,
        event: QKeyEvent,
    ) -> TabletInputEvent:
        return TabletInputEvent(
            kind=InputEventKind.KEY_PRESS,
            track_id=self._track_id_for_plot(plot) if plot is not None else None,
            key=self._key_name(event),
            payload=_QtPointerPayload(plot, event),
        )

    @staticmethod
    def _cursor_shape(name: str | None) -> Qt.CursorShape | None:
        if name is None:
            return None
        return {
            "arrow": Qt.CursorShape.ArrowCursor,
            "cross": Qt.CursorShape.CrossCursor,
            "size_all": Qt.CursorShape.SizeAllCursor,
            "size_fdiag": Qt.CursorShape.SizeFDiagCursor,
            "size_bdiag": Qt.CursorShape.SizeBDiagCursor,
            "size_ver": Qt.CursorShape.SizeVerCursor,
            "size_hor": Qt.CursorShape.SizeHorCursor,
        }.get(name)

    def _apply_interaction_cursor(
        self, watched: QObject, response: InteractionResponse
    ) -> None:
        setter = getattr(watched, "setCursor", None)
        if not callable(setter):
            return
        shape = self._cursor_shape(response.cursor)
        if shape is not None:
            setter(shape)
            return
        if self._annotation_tool is not None:
            setter(Qt.CursorShape.CrossCursor)
        elif not self._curve_pencil_enabled:
            setter(Qt.CursorShape.ArrowCursor)

    def _route_interaction_event(
        self, event: TabletInputEvent
    ) -> InteractionResponse:
        response = self._interaction_router.route(event)
        self._interaction_watchdog.sync()
        return response

    def _recover_lost_pointer_release(self) -> None:
        if not self._interaction_router.has_active_capture:
            return
        global_point = QCursor.pos()
        canvas_point = self._tracks_container.mapFromGlobal(global_point)
        self._route_interaction_event(
            TabletInputEvent(
                kind=InputEventKind.POINTER_RELEASE,
                x=float(canvas_point.x()),
                y=float(canvas_point.y()),
                button=PointerButton.LEFT,
                global_x=global_point.x(),
                global_y=global_point.y(),
            )
        )

    def _create_annotation_from_input(
        self, event: TabletInputEvent, tool: object
    ) -> bool:
        native = event.payload
        if not isinstance(native, _QtPointerPayload):
            return False
        if not isinstance(native.event, QMouseEvent) or native.plot is None:
            return False
        if event.track_id is None:
            return False
        try:
            kind = tool if isinstance(tool, AnnotationKind) else AnnotationKind(str(tool))
        except ValueError:
            return False
        try:
            definition = self._layout_model.track_by_id(event.track_id)
        except KeyError:
            definition = None
        payload = self._direct_annotation_payload(
            native.plot,
            native.event,
            event.track_id,
            definition,
            kind=kind,
        )
        if payload is None:
            return False
        self.select_track(event.track_id, emit_signal=True)
        self.annotation_add_requested.emit(payload)
        return True

    def _show_annotation_context_from_input(
        self, annotation_id: str, global_x: int, global_y: int
    ) -> None:
        self._show_annotation_context_menu(annotation_id, QPoint(global_x, global_y))

    def _commit_annotation_geometry(self, change: AnnotationGeometryChange) -> None:
        self.annotation_geometry_changed.emit(
            change.annotation_id,
            change.offset_x,
            change.offset_y,
            change.width,
            change.height,
        )

    def _track_is_directly_editable(self, track_id: str) -> bool:
        try:
            definition = self._layout_model.track_by_id(track_id)
        except KeyError:
            return False
        return definition.kind in {TrackKind.CURVE, TrackKind.GAS, TrackKind.DEXP}

    def _track_id_for_plot(self, plot: pg.PlotWidget) -> str | None:
        return next(
            (track_id for track_id, rendered in self._rendered.items() if rendered.plot is plot),
            None,
        )

    def _select_track_from_interaction(self, track_id: str) -> None:
        self.select_track(track_id, emit_signal=True)

    def _handle_depth_wheel(
        self,
        event: QWheelEvent,
        *,
        plot: pg.PlotWidget | None = None,
        watched: QObject | None = None,
    ) -> bool:
        angle_delta = event.angleDelta().y()
        pixel_delta = event.pixelDelta().y()
        delta = angle_delta if angle_delta else pixel_delta
        if not delta:
            return False
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = float(delta) / (120.0 if angle_delta else 60.0)
            anchor = (
                self._axis_value_at_event(plot, watched, event)
                if plot is not None and watched is not None
                else None
            )
            changed = self.zoom_depth(0.8**steps, anchor=anchor)
        elif angle_delta:
            changed = self.scroll_depth(-float(angle_delta) / 120.0)
        else:
            current = self.visible_depth_range
            if current is None:
                return False
            viewport_height = max(
                1, plot.viewport().height() if plot is not None else self.height()
            )
            depth_per_pixel = (current[1] - current[0]) / viewport_height
            changed = self._apply_pan_delta(-float(pixel_delta) * depth_per_pixel)
        event.accept()
        return bool(changed)

    def event(self, event: QEvent) -> bool:  # noqa: A003
        if event.type() in {
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Hide,
        }:
            self._interaction_router.cancel_active(event.type().name)
            self._interaction_watchdog.sync()
        return super().event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in {
            QEvent.Type.UngrabMouse,
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Hide,
        }:
            self._interaction_router.cancel_active(event.type().name)
            self._interaction_watchdog.sync()

        wheel_plot = self._wheel_targets.get(watched)
        if wheel_plot is not None and isinstance(event, QWheelEvent):
            self._handle_depth_wheel(event, plot=wheel_plot, watched=watched)
            return True
        if isinstance(event, QWheelEvent) and watched in {
            self._scroll.viewport(),
            self._tracks_container,
            self._group_header_container,
        }:
            self._handle_depth_wheel(event)
            return True
        plot = self._depth_viewports.get(watched)
        if plot is not None and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress:
                if (
                    event.key() == Qt.Key.Key_Escape
                    and self._analysis_interval_gesture is not None
                ):
                    self.cancel_interval_analysis(clear_interval=True)
                    event.accept()
                    return True
                response = self._route_interaction_event(
                    self._tablet_input_from_key(plot, event)
                )
                if response.consume:
                    event.accept()
                    return True
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
        if plot is not None and event.type() == QEvent.Type.Leave:
            self._hide_curve_pencil_hover(self._track_id_for_plot(plot))

        pan_pointer = isinstance(event, QMouseEvent) and (
            event.button() == Qt.MouseButton.MiddleButton
            or bool(event.buttons() & Qt.MouseButton.MiddleButton)
            or (
                self._space_pressed
                and (
                    event.button() == Qt.MouseButton.LeftButton
                    or bool(event.buttons() & Qt.MouseButton.LeftButton)
                )
            )
        )
        if isinstance(event, QMouseEvent) and (
            plot is not None or self._interaction_router.has_active_capture
        ) and (self._interaction_router.has_active_capture or not pan_pointer):
            response = self._route_interaction_event(
                self._tablet_input_from_mouse(plot, event)
            )
            self._apply_interaction_cursor(watched, response)
            if response.consume:
                if (
                    event.type()
                    in {QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick}
                    and isinstance(watched, QWidget)
                ):
                    watched.setFocus(Qt.FocusReason.MouseFocusReason)
                event.accept()
                return True

        if plot is not None and isinstance(event, QMouseEvent):
            track_id = self._track_id_for_plot(plot)
            if event.type() in {
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            }:
                self._update_curve_pencil_hover(plot, event, track_id)
            definition = None
            if track_id is not None:
                try:
                    definition = self._layout_model.track_by_id(track_id)
                except KeyError:
                    definition = None
            if self._handle_curve_pencil_event(plot, event, track_id):
                return True
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                and track_id is not None
            ):
                point = self._mouse_event_plot_point(plot, event)
                if self.begin_interval_analysis(track_id, float(point.y())):
                    event.accept()
                    return True
            if (
                event.type() == QEvent.Type.MouseMove
                and self._analysis_interval_gesture is not None
            ):
                point = self._mouse_event_plot_point(plot, event)
                if self.update_interval_analysis(float(point.y())):
                    event.accept()
                    return True
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
                and self._analysis_interval_gesture is not None
            ):
                point = self._mouse_event_plot_point(plot, event)
                if self.finish_interval_analysis(float(point.y())):
                    event.accept()
                    return True
            if (
                definition is not None
                and event.type() == QEvent.Type.MouseButtonDblClick
                and event.button() == Qt.MouseButton.LeftButton
            ):
                point = self._mouse_event_plot_point(plot, event)
                depth = self._axis_to_depth_value(float(point.y()))
                if definition.kind is TrackKind.STRATIGRAPHY:
                    stratigraphy_interval = self.stratigraphy_interval_at_depth(depth)
                    if stratigraphy_interval is not None:
                        self.stratigraphy_interval_edit_requested.emit(
                            stratigraphy_interval.interval_id
                        )
                        event.accept()
                        return True
                elif definition.kind is TrackKind.LITHOLOGY:
                    lithology_interval = self.lithology_interval_at_depth(depth)
                    if lithology_interval is not None:
                        self.lithology_interval_edit_requested.emit(
                            lithology_interval.interval_id
                        )
                        event.accept()
                        return True
                elif definition.kind is TrackKind.TEXT:
                    sample = self.cuttings_sample_at_depth(depth)
                    if sample is not None:
                        self.description_edit_requested.emit(sample.sample_id)
                        event.accept()
                        return True
                elif definition.kind in {
                    TrackKind.CUTTINGS,
                    TrackKind.CALCIMETRY,
                    TrackKind.LBA,
                }:
                    sample = self.cuttings_sample_at_depth(depth)
                    if sample is not None:
                        self.cuttings_sample_edit_requested.emit(sample.sample_id)
                        event.accept()
                        return True
            if (
                definition is not None
                and self._geological_input_mode is GeologicalInputMode.EDIT
                and event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                point = self._mouse_event_plot_point(plot, event)
                depth = self._axis_to_depth_value(float(point.y()))
                if definition.kind is TrackKind.STRATIGRAPHY:
                    stratigraphy_interval = self.stratigraphy_interval_at_depth(depth)
                    if stratigraphy_interval is not None:
                        self.stratigraphy_interval_edit_requested.emit(
                            stratigraphy_interval.interval_id
                        )
                        event.accept()
                        return True
                elif definition.kind is TrackKind.LITHOLOGY:
                    lithology_interval = self.lithology_interval_at_depth(depth)
                    if lithology_interval is not None:
                        self.lithology_interval_edit_requested.emit(
                            lithology_interval.interval_id
                        )
                        event.accept()
                        return True
                elif definition.kind is TrackKind.TEXT:
                    sample = self.cuttings_sample_at_depth(depth)
                    if sample is not None:
                        self.description_edit_requested.emit(sample.sample_id)
                        event.accept()
                        return True
                elif definition.kind in {TrackKind.CUTTINGS, TrackKind.CALCIMETRY, TrackKind.LBA}:
                    sample = self.cuttings_sample_at_depth(depth)
                    if sample is not None:
                        self.cuttings_sample_edit_requested.emit(sample.sample_id)
                        event.accept()
                        return True

            if definition is not None and definition.kind in {
                TrackKind.CUTTINGS,
                TrackKind.CALCIMETRY,
                TrackKind.LBA,
                TrackKind.TEXT,
            }:
                if (
                    event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton
                    and (
                        bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                        or (
                            self._geological_input_mode is GeologicalInputMode.SAMPLE
                            and definition.kind
                            in {TrackKind.CUTTINGS, TrackKind.CALCIMETRY, TrackKind.LBA}
                        )
                        or (
                            self._geological_input_mode is GeologicalInputMode.DESCRIPTION
                            and definition.kind is TrackKind.TEXT
                        )
                    )
                ):
                    point = self._mouse_event_plot_point(plot, event)
                    if track_id is not None and self.begin_sample_drag(
                        track_id, float(point.y())
                    ):
                        event.accept()
                        return True
                if event.type() == QEvent.Type.MouseMove and self._sample_gesture is not None:
                    point = self._mouse_event_plot_point(plot, event)
                    if self.update_sample_drag(float(point.y())):
                        event.accept()
                        return True
                if (
                    event.type() == QEvent.Type.MouseButtonRelease
                    and event.button() == Qt.MouseButton.LeftButton
                    and self._sample_gesture is not None
                ):
                    point = self._mouse_event_plot_point(plot, event)
                    if self.finish_sample_drag(float(point.y())):
                        event.accept()
                        return True
            if definition is not None and definition.kind is TrackKind.STRATIGRAPHY:
                if (
                    event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton
                    and (
                        bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                        or self._geological_input_mode is GeologicalInputMode.STRATIGRAPHY
                    )
                ):
                    point = self._mouse_event_plot_point(plot, event)
                    if track_id is not None and self.begin_stratigraphy_drag(
                        track_id, float(point.y())
                    ):
                        event.accept()
                        return True
                if event.type() == QEvent.Type.MouseMove and self._stratigraphy_gesture is not None:
                    point = self._mouse_event_plot_point(plot, event)
                    if self.update_stratigraphy_drag(float(point.y())):
                        event.accept()
                        return True
                if (
                    event.type() == QEvent.Type.MouseButtonRelease
                    and event.button() == Qt.MouseButton.LeftButton
                    and self._stratigraphy_gesture is not None
                ):
                    point = self._mouse_event_plot_point(plot, event)
                    if self.finish_stratigraphy_drag(float(point.y())):
                        event.accept()
                        return True
            if definition is not None and definition.kind is TrackKind.LITHOLOGY:
                if (
                    event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton
                    and (
                        bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                        or self._geological_input_mode is GeologicalInputMode.LITHOLOGY
                    )
                ):
                    point = self._mouse_event_plot_point(plot, event)
                    if track_id is not None and self.begin_lithology_drag(
                        track_id, float(point.y())
                    ):
                        event.accept()
                        return True
                if event.type() == QEvent.Type.MouseMove and self._lithology_gesture is not None:
                    point = self._mouse_event_plot_point(plot, event)
                    if self.update_lithology_drag(float(point.y())):
                        event.accept()
                        return True
                if (
                    event.type() == QEvent.Type.MouseButtonRelease
                    and event.button() == Qt.MouseButton.LeftButton
                    and self._lithology_gesture is not None
                ):
                    point = self._mouse_event_plot_point(plot, event)
                    if self.finish_lithology_drag(float(point.y())):
                        event.accept()
                        return True
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.RightButton
            ):
                track_id = self._track_id_for_plot(plot)
                if track_id is not None:
                    point = self._mouse_event_plot_point(plot, event)
                    depth = self._axis_to_depth_value(float(point.y()))
                    x_fraction = self._plot_x_fraction(definition, float(point.x()))
                    if definition is not None and definition.kind in {
                        TrackKind.STRATIGRAPHY,
                        TrackKind.LITHOLOGY,
                        TrackKind.CUTTINGS,
                        TrackKind.CALCIMETRY,
                        TrackKind.LBA,
                        TrackKind.TEXT,
                    }:
                        self.show_geological_context_menu(
                            track_id,
                            depth,
                            event.globalPosition().toPoint(),
                            axis_value=float(point.y()),
                            x_fraction=x_fraction,
                        )
                    else:
                        self.show_track_context_menu(
                            track_id,
                            event.globalPosition().toPoint(),
                            depth=depth,
                            axis_value=float(point.y()),
                            x_fraction=x_fraction,
                            local_x=event.position().x(),
                            local_y=event.position().y(),
                        )
                    event.accept()
                    return True
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and not self._space_pressed
                and watched not in self._interpretation_viewports
            ):
                track_id = self._track_id_for_plot(plot)
                if track_id is not None:
                    additive = bool(
                        event.modifiers()
                        & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                    )
                    toggle = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                    hit = self.select_curve_at(
                        track_id,
                        event.position().x(),
                        event.position().y(),
                        additive=additive,
                        toggle=toggle,
                    )
                    if hit is not None:
                        if not additive and not toggle and not self._form_edit_mode:
                            popup_args = (
                                track_id,
                                float(event.position().x()),
                                float(event.position().y()),
                                QPoint(event.globalPosition().toPoint()),
                            )
                            # Opening a modal menu directly from MouseButtonPress can
                            # leave the viewport in a pressed state on some platforms.
                            # Defer it until Qt has completed dispatching this event.
                            QTimer.singleShot(
                                0,
                                lambda args=popup_args: self._show_curve_value_popup(*args),
                            )
                        event.accept()
                        return True
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
            if event.type() == QEvent.Type.MouseButtonRelease and self._pan_viewport is watched:
                self._pan_viewport = None
                self._pan_last_position = None
                watched.setProperty("tablet_pan_active", False)
                event.accept()
                return True
        if plot is not None and isinstance(event, QKeyEvent):
            if (
                event.type() == QEvent.Type.KeyPress
                and self._curve_pencil_mode is CurvePencilMode.CONNECT_POINTS
                and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
                and len(self._curve_pencil_points) >= 2
            ):
                self._apply_curve_pencil_points()
                event.accept()
                return True
            if (
                event.type() == QEvent.Type.KeyPress
                and self._curve_pencil_mode is CurvePencilMode.CONNECT_POINTS
                and event.key() in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}
                and self._curve_pencil_points
            ):
                self._curve_pencil_points.pop()
                self._update_curve_pencil_preview()
                self._update_curve_pencil_status()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Escape and self._curve_pencil_points:
                self.cancel_curve_pencil_gesture()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Escape and self._lithology_gesture is not None:
                self.cancel_lithology_interaction()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Escape and self._sample_gesture is not None:
                self.cancel_sample_interaction()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Escape and self._stratigraphy_gesture is not None:
                self.cancel_stratigraphy_interaction()
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

    @staticmethod
    def _mouse_event_plot_point(plot: pg.PlotWidget, event: QMouseEvent) -> QPointF:
        # QMouseEvent.position() is expressed in the PlotWidget viewport because
        # the event filter is installed on that viewport. QGraphicsView.mapToScene
        # expects viewport coordinates, so no global/widget remapping is needed.
        scene_position = plot.mapToScene(event.position().toPoint())
        return plot.getViewBox().mapSceneToView(scene_position)

    def begin_sample_drag(self, track_id: str, axis_depth: float) -> bool:
        rendered = self._rendered.get(track_id)
        descriptor = self._axis_descriptor()
        if (
            rendered is None
            or rendered.definition.kind
            not in {TrackKind.CUTTINGS, TrackKind.CALCIMETRY, TrackKind.LBA, TrackKind.TEXT}
            or rendered.plot is None
            or (descriptor is not None and descriptor.role is not IndexRole.DEPTH)
        ):
            return False
        depth = self._snap_depth(self._axis_to_depth_value(float(axis_depth)))
        self.cancel_sample_interaction()
        self._sample_gesture = _SampleGesture(track_id, depth, depth)
        rendered.plot.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._update_sample_preview()
        return True

    def update_sample_drag(self, axis_depth: float) -> bool:
        if self._sample_gesture is None:
            return False
        self._sample_gesture.current_depth = self._snap_depth(
            self._axis_to_depth_value(float(axis_depth))
        )
        self._update_sample_preview()
        return True

    def finish_sample_drag(self, axis_depth: float) -> bool:
        gesture = self._sample_gesture
        if gesture is None:
            return False
        gesture.current_depth = self._snap_depth(self._axis_to_depth_value(float(axis_depth)))
        result = normalize_drag_range(
            gesture.start_depth,
            gesture.current_depth,
            minimum_span=self._minimum_depth_span(),
        )
        self.cancel_sample_interaction()
        if result is None:
            return False
        rendered = self._rendered.get(gesture.track_id)
        if rendered is not None and rendered.definition.kind is TrackKind.TEXT:
            self.description_interval_requested.emit(result.top_depth, result.bottom_depth)
        else:
            self.cuttings_interval_requested.emit(result.top_depth, result.bottom_depth)
        return True

    def cancel_sample_interaction(self) -> None:
        gesture = self._sample_gesture
        if gesture is not None:
            rendered = self._rendered.get(gesture.track_id)
            if rendered is not None and rendered.plot is not None:
                preview = rendered.sample_preview
                if preview is not None:
                    self._overlay_layers.unregister(
                        OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
                    )
                    rendered.plot.removeItem(preview)
                rendered.sample_preview = None
                rendered.plot.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self._sample_gesture = None

    def _update_sample_preview(self) -> None:
        gesture = self._sample_gesture
        if gesture is None:
            return
        rendered = self._rendered.get(gesture.track_id)
        if rendered is None or rendered.plot is None:
            return
        result = normalize_drag_range(
            gesture.start_depth,
            gesture.current_depth,
            minimum_span=self._minimum_depth_span(),
        )
        top = gesture.current_depth if result is None else result.top_depth
        bottom = gesture.current_depth if result is None else result.bottom_depth
        axis_top, axis_bottom = self._depth_interval_to_axis(top, bottom)
        x_width = (
            100.0 if rendered.definition.kind in {TrackKind.CUTTINGS, TrackKind.CALCIMETRY} else 1.0
        )
        options = dict(
            x=[x_width / 2.0],
            y=[(axis_top + axis_bottom) / 2.0],
            width=x_width,
            height=max(axis_bottom - axis_top, np.finfo(float).eps),
            brush=pg.mkBrush(14, 165, 233, 55),
            pen=pg.mkPen("#0284c7", width=2.0, style=Qt.PenStyle.DashLine),
        )
        if rendered.sample_preview is None:
            preview = pg.BarGraphItem(**options)
            rendered.plot.addItem(preview)
            rendered.sample_preview = preview
            self._overlay_layers.register(
                OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
            )
        else:
            rendered.sample_preview.setOpts(**options)

    def begin_stratigraphy_drag(self, track_id: str, axis_depth: float) -> bool:
        rendered = self._rendered.get(track_id)
        descriptor = self._axis_descriptor()
        if (
            rendered is None
            or rendered.definition.kind is not TrackKind.STRATIGRAPHY
            or rendered.plot is None
            or (descriptor is not None and descriptor.role is not IndexRole.DEPTH)
        ):
            return False
        depth = self._snap_depth(self._axis_to_depth_value(float(axis_depth)))
        self.cancel_stratigraphy_interaction()
        self._stratigraphy_gesture = _StratigraphyGesture(track_id, depth, depth)
        rendered.plot.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._update_stratigraphy_preview()
        return True

    def update_stratigraphy_drag(self, axis_depth: float) -> bool:
        if self._stratigraphy_gesture is None:
            return False
        self._stratigraphy_gesture.current_depth = self._snap_depth(
            self._axis_to_depth_value(float(axis_depth))
        )
        self._update_stratigraphy_preview()
        return True

    def finish_stratigraphy_drag(self, axis_depth: float) -> bool:
        gesture = self._stratigraphy_gesture
        if gesture is None:
            return False
        gesture.current_depth = self._snap_depth(self._axis_to_depth_value(float(axis_depth)))
        result = normalize_drag_range(
            gesture.start_depth,
            gesture.current_depth,
            minimum_span=self._minimum_depth_span(),
        )
        self.cancel_stratigraphy_interaction()
        if result is None:
            return False
        self.stratigraphy_interval_requested.emit(result.top_depth, result.bottom_depth)
        return True

    def cancel_stratigraphy_interaction(self) -> None:
        gesture = self._stratigraphy_gesture
        if gesture is not None:
            rendered = self._rendered.get(gesture.track_id)
            if rendered is not None and rendered.plot is not None:
                preview = rendered.stratigraphy_preview
                if preview is not None:
                    self._overlay_layers.unregister(
                        OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
                    )
                    rendered.plot.removeItem(preview)
                rendered.stratigraphy_preview = None
                rendered.plot.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self._stratigraphy_gesture = None

    def _update_stratigraphy_preview(self) -> None:
        gesture = self._stratigraphy_gesture
        if gesture is None:
            return
        rendered = self._rendered.get(gesture.track_id)
        if rendered is None or rendered.plot is None:
            return
        result = normalize_drag_range(
            gesture.start_depth,
            gesture.current_depth,
            minimum_span=self._minimum_depth_span(),
        )
        top = gesture.current_depth if result is None else result.top_depth
        bottom = gesture.current_depth if result is None else result.bottom_depth
        axis_top, axis_bottom = self._depth_interval_to_axis(top, bottom)
        options = dict(
            x=[0.5],
            y=[(axis_top + axis_bottom) / 2.0],
            width=0.94,
            height=max(axis_bottom - axis_top, np.finfo(float).eps),
            brush=pg.mkBrush(99, 102, 241, 55),
            pen=pg.mkPen("#4f46e5", width=2.0, style=Qt.PenStyle.DashLine),
        )
        if rendered.stratigraphy_preview is None:
            preview = pg.BarGraphItem(**options)
            rendered.plot.addItem(preview)
            rendered.stratigraphy_preview = preview
            self._overlay_layers.register(
                OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
            )
        else:
            rendered.stratigraphy_preview.setOpts(**options)

    def begin_lithology_drag(self, track_id: str, axis_depth: float) -> bool:
        rendered = self._rendered.get(track_id)
        descriptor = self._axis_descriptor()
        if (
            rendered is None
            or rendered.definition.kind is not TrackKind.LITHOLOGY
            or rendered.plot is None
            or (descriptor is not None and descriptor.role is not IndexRole.DEPTH)
        ):
            return False
        depth = self._snap_depth(self._axis_to_depth_value(float(axis_depth)))
        self.cancel_lithology_interaction()
        self._lithology_gesture = _LithologyGesture(track_id, depth, depth)
        rendered.plot.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._update_lithology_preview()
        return True

    def update_lithology_drag(self, axis_depth: float) -> bool:
        if self._lithology_gesture is None:
            return False
        self._lithology_gesture.current_depth = self._snap_depth(
            self._axis_to_depth_value(float(axis_depth))
        )
        self._update_lithology_preview()
        return True

    def finish_lithology_drag(self, axis_depth: float) -> bool:
        gesture = self._lithology_gesture
        if gesture is None:
            return False
        gesture.current_depth = self._snap_depth(self._axis_to_depth_value(float(axis_depth)))
        result = self._lithology_gesture_result()
        self.cancel_lithology_interaction()
        if result is None:
            return False
        self.lithology_interval_requested.emit(result.top_depth, result.bottom_depth)
        return True

    def cancel_lithology_interaction(self) -> None:
        gesture = self._lithology_gesture
        if gesture is not None:
            rendered = self._rendered.get(gesture.track_id)
            if rendered is not None and rendered.plot is not None:
                preview = rendered.lithology_preview
                if preview is not None:
                    self._overlay_layers.unregister(
                        OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
                    )
                    rendered.plot.removeItem(preview)
                rendered.lithology_preview = None
                rendered.plot.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self._lithology_gesture = None

    def _lithology_gesture_result(self) -> IntervalDragResult | None:
        gesture = self._lithology_gesture
        if gesture is None:
            return None
        return normalize_drag_range(
            gesture.start_depth,
            gesture.current_depth,
            minimum_span=self._minimum_depth_span(),
        )

    def _update_lithology_preview(self) -> None:
        gesture = self._lithology_gesture
        if gesture is None:
            return
        rendered = self._rendered.get(gesture.track_id)
        if rendered is None or rendered.plot is None:
            return
        result = self._lithology_gesture_result()
        if result is None:
            top = bottom = gesture.current_depth
        else:
            top, bottom = result.top_depth, result.bottom_depth
        axis_top, axis_bottom = self._depth_interval_to_axis(top, bottom)
        options = dict(
            x=[0.5],
            y=[(axis_top + axis_bottom) / 2.0],
            width=1.0,
            height=max(axis_bottom - axis_top, np.finfo(float).eps),
            brush=pg.mkBrush(16, 185, 129, 65),
            pen=pg.mkPen("#059669", width=2.0, style=Qt.PenStyle.DashLine),
        )
        if rendered.lithology_preview is None:
            preview = pg.BarGraphItem(**options)
            rendered.plot.addItem(preview)
            rendered.lithology_preview = preview
            self._overlay_layers.register(
                OverlayLayerKind.PREVIEW, rendered.definition.track_id, preview
            )
        else:
            rendered.lithology_preview.setOpts(**options)

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
        self._layout_model.set_visible_depth(normalized_top, normalized_bottom)
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
        # setYRange changes the data-to-screen transform immediately. Remap the
        # annotation anchors before the next repaint so comments and callouts
        # scroll/zoom together with their depth or time coordinate.
        self._refresh_annotation_overlay_anchors()
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
            return format_unix_seconds(value)
        if descriptor.is_time:
            return format_elapsed_time(value, descriptor.unit)
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
        title, width, grid_x, grid_y, grid_alpha, x_axis_label = self._track_static_descriptor(
            definition
        )
        if isinstance(rendered.widget, TabletTrackWidget):
            rendered.widget.definition = definition
            rendered.widget.title.setText(self._localized_track_title(definition))
            rendered.widget.set_track_width(int(width))
        if rendered.plot is not None:
            rendered.plot.showGrid(x=bool(grid_x), y=bool(grid_y), alpha=float(grid_alpha))
            rendered.plot.setLabel("bottom", str(x_axis_label))

    def _apply_curve_styles(self, rendered: RenderedTrack, definition: TrackDefinition) -> None:
        relative_gas = is_relative_gas_track(definition.curve_mnemonics)
        if rendered.plot is not None:
            rendered.plot.setLogMode(x=False, y=False)
            rendered.plot.setXRange(
                0.0,
                100.0 if definition.kind is TrackKind.CALCIMETRY or relative_gas else 1.0,
                padding=0,
            )
        header_rows: list[tuple[str, str, str]] = []
        for index, (mnemonic, item) in enumerate((rendered.curve_items or {}).items()):
            style = definition.curve_style(mnemonic)
            if style is None:
                style = CurveStyle(
                    color=pg.intColor(index, hues=max(1, len(definition.curve_mnemonics))).name(),
                    width=1.5,
                )
            item.setPen(
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
            )
            fill = (rendered.relative_fill_items or {}).get(mnemonic)
            if fill is not None:
                color = pg.mkColor(style.color)
                color.setAlpha(135)
                fill.setBrush(pg.mkBrush(color))
            if self._dataset is None:
                continue
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                continue
            settings = definition.curve_display_settings(mnemonic)
            display_name = self._curve_display_name(definition, mnemonic, curve)
            unit = (curve.metadata.unit or "").strip()
            if relative_gas:
                text = f"{display_name}\n0 … 100 % · Σ=100%"
            else:
                minimum, maximum = self._curve_display_range(
                    definition, mnemonic, np.asarray(curve.values, dtype=float)
                )
                scale_marker = self._localizer.text(
                    "curve_settings.scale_short.logarithmic"
                    if settings.x_scale is XScale.LOGARITHMIC
                    else "curve_settings.scale_short.linear"
                )
                text = f"{display_name}\n{minimum:g} … {maximum:g}"
                if unit:
                    text += f" {unit}"
                text += f" · {scale_marker}"
            header_rows.append((mnemonic, text, style.color))
        rendered.widget.set_curve_headers(header_rows)
        if rendered.curve_render_keys is not None:
            rendered.curve_render_keys.clear()

    def _refresh_rendered_track(self, rendered: RenderedTrack, reasons: DirtyReason) -> None:
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
        self._apply_curve_selection_style()
        if self._cursor_depth is not None:
            self._update_cursor_labels(self._cursor_depth)
        if rendered.plot is not None:
            rendered.plot.viewport().update()

    def _update_rendered_track_curve_data(
        self, rendered: RenderedTrack, top: float, bottom: float
    ) -> None:
        if self._dataset is None:
            return
        if is_relative_gas_track(rendered.definition.curve_mnemonics):
            self._update_relative_gas_track_data(rendered, top, bottom)
            return
        depth = self._axis_values()
        for mnemonic, item in (rendered.curve_items or {}).items():
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                item.setData([], [])
                continue
            source_values = np.asarray(curve.values, dtype=float)
            settings = rendered.definition.curve_display_settings(mnemonic)
            logarithmic = settings.x_scale is XScale.LOGARITHMIC
            budget = self._lod_point_budget(
                rendered.plot.viewport().height() if rendered.plot is not None else 1000
            )
            key = self._curve_geometry_key(
                mnemonic, depth, source_values, top, bottom, budget, logarithmic
            )
            render_keys = rendered.curve_render_keys
            if render_keys is not None and render_keys.get(mnemonic) == key:
                continue
            values, visible_depth = self._geometry_cache.get_or_build(key, depth, source_values)
            minimum, maximum = self._curve_display_range(
                rendered.definition, mnemonic, source_values
            )
            if rendered.definition.kind is TrackKind.CALCIMETRY:
                normalized = np.where(np.isfinite(values), np.clip(values, 0.0, 100.0), np.nan)
            else:
                normalized = self._normalize_curve_values(
                    values, settings.x_scale, minimum, maximum
                )
            item.setData(normalized, visible_depth, connect="finite")
            if render_keys is not None:
                render_keys[mnemonic] = key

    def _update_relative_gas_track_data(
        self, rendered: RenderedTrack, top: float, bottom: float
    ) -> None:
        """Refresh all cumulative boundaries from one shared viewport geometry."""

        if self._dataset is None:
            return
        available: dict[str, np.ndarray] = {}
        for mnemonic in rendered.definition.curve_mnemonics:
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is not None and mnemonic in (rendered.curve_items or {}):
                available[mnemonic] = np.asarray(curve.values, dtype=np.float64)
        if not available:
            if rendered.relative_baseline_item is not None:
                rendered.relative_baseline_item.setData([], [])
            for item in (rendered.curve_items or {}).values():
                item.setData([], [])
            return

        stack = build_relative_gas_stack(
            self._axis_values(),
            available,
            top,
            bottom,
            max_points=self._lod_point_budget(
                rendered.plot.viewport().height() if rendered.plot is not None else 1000
            ),
        )
        if rendered.relative_baseline_item is not None:
            rendered.relative_baseline_item.setData(stack.baseline, stack.depth, connect="finite")
        bands = {band.mnemonic: band for band in stack.bands}
        for mnemonic, item in (rendered.curve_items or {}).items():
            band = bands.get(mnemonic)
            if band is None:
                item.setData([], [])
            else:
                item.setData(band.upper, stack.depth, connect="finite")
        if rendered.curve_render_keys is not None:
            rendered.curve_render_keys.clear()

    def _populate_track(
        self,
        track: TabletTrackWidget,
        definition: TrackDefinition,
        visible_top: float | None,
        visible_bottom: float | None,
    ) -> tuple[
        tuple[str, ...],
        dict[str, pg.PlotDataItem],
        dict[str, pg.FillBetweenItem],
        pg.PlotDataItem | None,
    ]:
        assert self._dataset is not None
        depth = self._axis_values()

        if definition.kind == TrackKind.DEPTH:
            descriptor = self._axis_descriptor()
            track.plot.showAxis("left")
            if descriptor is not None and descriptor.is_time:
                label = self._localizer.text("tablet.track.time")
            else:
                label = self._localizer.text("tablet.track.depth")
            unit = (
                descriptor.unit
                if descriptor is not None
                else self._localizer.text("tablet.depth_span_unit")
            )
            track.title.setText(f"{label}, {unit}" if unit else label)
            # The title already explains the axis. A second rotated axis label
            # consumed most of the narrow depth column and made it look broken.
            axis = track.plot.getAxis("left")
            axis.setLabel(text="")
            axis.setStyle(
                autoExpandTextSpace=False,
                tickTextWidth=max(48, min(track.width() - 16, 88)),
                tickLength=-6,
            )
            axis.setWidth(max(54, min(track.width() - 12, 92)))
            track.plot.hideAxis("bottom")
            track.plot.showGrid(x=False, y=True, alpha=0.25)
            track.plot.setXRange(0.0, 1.0, padding=0)
            track.plot.getViewBox().setDefaultPadding(0.0)
            track.plot.setMouseEnabled(x=False, y=False)
            return (), {}, {}, None

        if definition.kind is TrackKind.CALCIMETRY:
            track.plot.hideAxis("bottom")
            track.plot.setXRange(0.0, 100.0, padding=0)
            track.plot.setMouseEnabled(x=False, y=True)
            calc_curve_items: dict[str, pg.PlotDataItem] = {}
            calc_header_rows: list[tuple[str, str, str]] = []
            calc_legend_labels: list[str] = []
            for index, mnemonic in enumerate(definition.curve_mnemonics):
                curve = self._dataset.curve_by_mnemonic(mnemonic)
                if curve is None:
                    continue
                source_values = np.asarray(curve.values, dtype=np.float64)
                if not np.any(np.isfinite(source_values) & np.isfinite(depth)):
                    continue
                style = definition.curve_style(mnemonic) or CurveStyle(
                    color=("#06b6d4" if index == 0 else "#8b5cf6"),
                    width=2.0,
                )
                if visible_top is None or visible_bottom is None:
                    visible_values = np.array([], dtype=np.float64)
                    visible_depth = np.array([], dtype=np.float64)
                else:
                    budget = self._lod_point_budget(track.plot.viewport().height())
                    key = self._curve_geometry_key(
                        mnemonic,
                        depth,
                        source_values,
                        visible_top,
                        visible_bottom,
                        budget,
                        False,
                    )
                    visible_values, visible_depth = self._geometry_cache.get_or_build(
                        key, depth, source_values
                    )
                    visible_values = np.where(
                        np.isfinite(visible_values),
                        np.clip(visible_values, 0.0, 100.0),
                        np.nan,
                    )
                item = track.plot.plot(
                    visible_values,
                    visible_depth,
                    pen=pg.mkPen(
                        style.color,
                        width=style.width,
                        style={
                            CurveLineStyle.SOLID: Qt.PenStyle.SolidLine,
                            CurveLineStyle.DASH: Qt.PenStyle.DashLine,
                            CurveLineStyle.DOT: Qt.PenStyle.DotLine,
                            CurveLineStyle.DASH_DOT: Qt.PenStyle.DashDotLine,
                        }[style.line_style],
                    ),
                    connect="finite",
                )
                display_name = self._curve_display_name(definition, mnemonic, curve)
                unit = (curve.metadata.unit or "%").strip() or "%"
                calc_header_rows.append(
                    (mnemonic, f"{display_name}\n0 … 100 {unit}", style.color)
                )
                calc_legend_labels.append(display_name)
                calc_curve_items[mnemonic] = item
            track.set_curve_headers(calc_header_rows)
            return tuple(calc_legend_labels), calc_curve_items, {}, None

        if definition.kind in (
            TrackKind.LITHOLOGY,
            TrackKind.CUTTINGS,
            TrackKind.LBA,
            TrackKind.STRATIGRAPHY,
            TrackKind.INTERPRETATION,
            TrackKind.TEXT,
        ):
            track.plot.hideAxis("bottom")
            track.plot.setXRange(0.0, 1.0, padding=0)
            track.plot.setMouseEnabled(x=False, y=True)
            return (), {}, {}, None

        if is_relative_gas_track(definition.curve_mnemonics):
            return self._populate_relative_gas_track(track, definition, visible_top, visible_bottom)

        track.plot.hideAxis("bottom")
        track.plot.setMouseEnabled(x=False, y=True)
        track.plot.setLogMode(x=False, y=False)
        track.plot.setXRange(0.0, 1.0, padding=0)
        track.plot.getViewBox().setDefaultPadding(0.0)
        legend_labels: list[str] = []
        curve_items: dict[str, pg.PlotDataItem] = {}
        header_rows: list[tuple[str, str, str]] = []
        for index, mnemonic in enumerate(definition.curve_mnemonics):
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                continue
            values = np.asarray(curve.values, dtype=float)
            settings = definition.curve_display_settings(mnemonic)
            logarithmic = settings.x_scale is XScale.LOGARITHMIC
            valid = np.isfinite(values) & np.isfinite(depth)
            if logarithmic:
                valid &= values > 0
            if not np.any(valid):
                continue
            resolved_style = definition.curve_style(mnemonic)
            if resolved_style is None:
                resolved_style = CurveStyle(
                    color=pg.intColor(index, hues=max(1, len(definition.curve_mnemonics))).name(),
                    width=1.5,
                )
            pen = pg.mkPen(
                resolved_style.color,
                width=resolved_style.width,
                style={
                    CurveLineStyle.SOLID: Qt.PenStyle.SolidLine,
                    CurveLineStyle.DASH: Qt.PenStyle.DashLine,
                    CurveLineStyle.DOT: Qt.PenStyle.DotLine,
                    CurveLineStyle.DASH_DOT: Qt.PenStyle.DashDotLine,
                }[resolved_style.line_style],
            )
            minimum, maximum = self._curve_display_range(definition, mnemonic, values)
            if visible_top is None or visible_bottom is None:
                visible_values = np.array([], dtype=np.float64)
                visible_depth = np.array([], dtype=np.float64)
            else:
                budget = self._lod_point_budget(track.plot.viewport().height())
                key = self._curve_geometry_key(
                    mnemonic, depth, values, visible_top, visible_bottom, budget, logarithmic
                )
                raw_visible, visible_depth = self._geometry_cache.get_or_build(key, depth, values)
                visible_values = self._normalize_curve_values(
                    raw_visible, settings.x_scale, minimum, maximum
                )
            display_name = self._curve_display_name(definition, mnemonic, curve)
            unit = (curve.metadata.unit or "").strip()
            scale_marker = self._localizer.text(
                "curve_settings.scale_short.logarithmic"
                if logarithmic
                else "curve_settings.scale_short.linear"
            )
            range_text = f"{minimum:g} … {maximum:g}"
            header_text = f"{display_name}\n{range_text}"
            if unit:
                header_text += f" {unit}"
            header_text += f" · {scale_marker}"
            # The geometry cache already supplies only the visible depth window.
            # Do not pass clipToView at construction time: pyqtgraph 0.14 with
            # PySide6 6.11 may query the temporary PlotWidget before the item is
            # parented to its ViewBox and raise AttributeError(autoRangeEnabled).
            item = track.plot.plot(
                visible_values,
                visible_depth,
                pen=pen,
                connect="finite",
            )
            curve_items[mnemonic] = item
            legend_labels.append(display_name)
            header_rows.append((mnemonic, header_text, resolved_style.color))
        track.set_curve_headers(header_rows)
        if not curve_items:
            track.title.setText(
                self._localizer.text("tablet.no_numeric_data", title=definition.title)
            )
            message = pg.TextItem(
                self._localizer.text("tablet.no_numeric_data_short"),
                color="#64748b",
                anchor=(0.5, 0.5),
            )
            depth_bounds = self._depth_bounds()
            center_depth = sum(depth_bounds) / 2.0 if depth_bounds is not None else 0.0
            message.setPos(0.5, center_depth)
            track.plot.addItem(message)
        return tuple(legend_labels), curve_items, {}, None

    def _populate_relative_gas_track(
        self,
        track: TabletTrackWidget,
        definition: TrackDefinition,
        visible_top: float | None,
        visible_bottom: float | None,
    ) -> tuple[
        tuple[str, ...],
        dict[str, pg.PlotDataItem],
        dict[str, pg.FillBetweenItem],
        pg.PlotDataItem | None,
    ]:
        """Render C1_REL…C5_REL as a cumulative 0–100% composition fill.

        Each component occupies the horizontal band between two cumulative
        boundaries. Missing rows remain gaps; measured values are normalized to
        100% defensively so vendor relative curves can be displayed consistently.
        """

        assert self._dataset is not None
        track.plot.hideAxis("bottom")
        track.plot.setMouseEnabled(x=False, y=True)
        track.plot.setLogMode(x=False, y=False)
        track.plot.setXRange(0.0, 100.0, padding=0)
        track.plot.getViewBox().setDefaultPadding(0.0)

        available: dict[str, np.ndarray] = {}
        styles: dict[str, CurveStyle] = {}
        header_rows: list[tuple[str, str, str]] = []
        legend_labels: list[str] = []
        for index, mnemonic in enumerate(definition.curve_mnemonics):
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                continue
            values = np.asarray(curve.values, dtype=np.float64)
            if not np.any(np.isfinite(values)):
                continue
            style = definition.curve_style(mnemonic) or CurveStyle(
                color=pg.intColor(index, hues=max(1, len(definition.curve_mnemonics))).name(),
                width=1.25,
            )
            available[mnemonic] = values
            styles[mnemonic] = style
            display_name = self._curve_display_name(definition, mnemonic, curve)
            header_rows.append((mnemonic, f"{display_name}\n0 … 100 % · Σ=100%", style.color))
            legend_labels.append(display_name)

        if not available:
            track.set_curve_headers([])
            track.title.setText(
                self._localizer.text("tablet.no_numeric_data", title=definition.title)
            )
            message = pg.TextItem(
                self._localizer.text("tablet.no_numeric_data_short"),
                color="#64748b",
                anchor=(0.5, 0.5),
            )
            bounds = self._depth_bounds()
            message.setPos(50.0, sum(bounds) / 2.0 if bounds is not None else 0.0)
            track.plot.addItem(message)
            return (), {}, {}, None

        depth = self._axis_values()
        if visible_top is None or visible_bottom is None:
            stack = build_relative_gas_stack(depth, available, 0.0, -1.0, max_points=2)
        else:
            stack = build_relative_gas_stack(
                depth,
                available,
                visible_top,
                visible_bottom,
                max_points=self._lod_point_budget(track.plot.viewport().height()),
            )

        baseline = pg.PlotDataItem(
            stack.baseline,
            stack.depth,
            pen=None,
            connect="finite",
        )
        baseline.setZValue(-20)
        track.plot.addItem(baseline)

        curve_items: dict[str, pg.PlotDataItem] = {}
        fill_items: dict[str, pg.FillBetweenItem] = {}
        lower_curve: pg.PlotDataItem = baseline
        band_by_name = {band.mnemonic: band for band in stack.bands}
        for mnemonic in available:
            band = band_by_name[mnemonic]
            style = styles[mnemonic]
            upper_curve = pg.PlotDataItem(
                band.upper,
                stack.depth,
                pen=pg.mkPen(style.color, width=style.width),
                connect="finite",
            )
            upper_curve.setZValue(2)
            track.plot.addItem(upper_curve)
            color = pg.mkColor(style.color)
            color.setAlpha(135)
            fill = pg.FillBetweenItem(lower_curve, upper_curve, brush=pg.mkBrush(color), pen=None)
            fill.setZValue(-10)
            fill.setToolTip(
                self._localizer.text("tablet.relative_gas_fill_tooltip", component=mnemonic)
            )
            track.plot.addItem(fill)
            curve_items[mnemonic] = upper_curve
            fill_items[mnemonic] = fill
            lower_curve = upper_curve

        track.set_curve_headers(header_rows)
        return tuple(legend_labels), curve_items, fill_items, baseline

    def _curve_display_name(
        self, definition: TrackDefinition, mnemonic: str, curve: CurveData
    ) -> str:
        metadata = curve.metadata
        return localized_curve_name(
            metadata.original_mnemonic or mnemonic,
            description=metadata.description or "",
            unit=metadata.unit or "",
            language=self._localizer.language,
            configured=definition.curve_display_settings(mnemonic).display_name,
        )

    def _localized_track_title(self, definition: TrackDefinition) -> str:
        standard = {
            TrackKind.DEPTH: "tablet.track.depth",
            TrackKind.GAS: "tablet.track.gas",
            TrackKind.LITHOLOGY: "tablet.track.lithology",
            TrackKind.CUTTINGS: "tablet.track.cuttings",
            TrackKind.CALCIMETRY: "tablet.track.calcimetry",
            TrackKind.LBA: "tablet.track.lba",
            TrackKind.STRATIGRAPHY: "tablet.track.stratigraphy",
            TrackKind.INTERPRETATION: "tablet.track.interpretation",
            TrackKind.TEXT: "tablet.track.description",
        }
        key = standard.get(definition.kind)
        if key is not None:
            return self._localizer.text(key)
        if definition.kind in {TrackKind.CURVE, TrackKind.DEXP} and definition.curve_mnemonics:
            generated = " / ".join(definition.curve_mnemonics)
            if definition.title.strip() == generated or len(definition.title.strip()) > 64:
                return self._localizer.text(
                    "tablet.track.parameters_count", count=len(definition.curve_mnemonics)
                )
        return definition.title

    def _curve_display_range(
        self, definition: TrackDefinition, mnemonic: str, values: np.ndarray
    ) -> tuple[float, float]:
        settings = definition.curve_display_settings(mnemonic)
        if settings.x_min is not None and settings.x_max is not None:
            return float(settings.x_min), float(settings.x_max)
        return automatic_curve_range(values, settings.x_scale)

    @staticmethod
    def _normalize_curve_values(
        values: np.ndarray, scale: XScale, minimum: float, maximum: float
    ) -> np.ndarray:
        return normalize_curve_values(values, scale, minimum, maximum)

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
            minimum, maximum = (float(value) for value in np.nanpercentile(combined, [1.0, 99.0]))
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
            item = DeviceTiledRectItem(
                QRectF(
                    0.0,
                    axis_top,
                    1.0,
                    max(axis_bottom - axis_top, np.finfo(float).eps),
                ),
                lithology_brush(color, pattern),
                pg.mkPen("#303030", width=0.7),
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
            label = pg.TextItem(
                label_text,
                color="#0f172a",
                anchor=stratigraphy_text_anchor(interval.text_orientation, interval.text_position),
                angle=stratigraphy_text_angle(interval.text_orientation),
            )
            label_position = stratigraphy_text_position_fraction(interval.text_position)
            label.setPos(
                lane + 0.5,
                axis_top + (axis_bottom - axis_top) * label_position,
            )
            label.setToolTip(f"{interval.top_depth:g}–{interval.bottom_depth:g} m\n{label_text}")
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

    def hit_test_interpretation(self, track_id: str, x_value: float, depth: float) -> str | None:
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
        self._interval_gesture.current_depth = self._snap_depth(self._axis_to_depth_value(depth))
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
    def _mouse_event_view_point(rendered: RenderedTrack, event: QMouseEvent) -> QPointF:
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
            self._axis_to_depth_value(center + axis_tolerance) - self._axis_to_depth_value(center)
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
            key=lambda item: min(abs(depth - item.top_depth), abs(depth - item.bottom_depth)),
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
        self.set_selected_interval(interpretation.interpretation_id, interval_id, emit_signal=True)

    def _apply_interpretation_selection_style(self) -> None:
        self._overlay_layers.mark_dirty(OverlayLayerKind.SELECTION)
        interpretation = self._current_interpretation()
        selected = None
        if interpretation is not None and self._selected_interval_id is not None:
            selected = next(
                (
                    item
                    for item in interpretation.intervals
                    if item.interval_id == self._selected_interval_id
                ),
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
                item = DeviceTiledRectItem(
                    QRectF(
                        left,
                        axis_top,
                        width,
                        max(axis_bottom - axis_top, np.finfo(float).eps),
                    ),
                    lithology_brush(color, pattern),
                    pg.mkPen("#303030", width=0.7),
                )
                track.plot.addItem(item)
                items.append(item)
                left += width
            rendered[sample.sample_id] = tuple(items)
        return rendered

    def _populate_sample_analysis(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, tuple[object, ...]]:
        """Render discrete calcimetry and LBA samples as interval observations.

        These laboratory results are not continuous LAS curves.  They belong to
        cuttings sample intervals, therefore they are drawn as bounded sample
        blocks and symbols and are never interpolated between neighbouring
        samples.
        """
        if definition.kind not in {TrackKind.CALCIMETRY, TrackKind.LBA}:
            return {}

        track.plot.hideAxis("bottom")
        if definition.kind is TrackKind.CALCIMETRY:
            track.plot.setXRange(0.0, 100.0, padding=0)
            if not definition.curve_mnemonics:
                track.set_curve_headers(
                    [
                        (
                            "__calcite__",
                            self._localizer.text("tablet.calcimetry_header_calcite"),
                            "#06b6d4",
                        ),
                        (
                            "__dolomite__",
                            self._localizer.text("tablet.calcimetry_header_dolomite"),
                            "#8b5cf6",
                        ),
                        (
                            "__residue__",
                            self._localizer.text("tablet.calcimetry_header_residue"),
                            "#94a3b8",
                        ),
                    ]
                )
        else:
            # GeoData-style LBA track: three synchronized subcolumns for
            # score, fluorescence color and bitumoid type.  This is a
            # discrete laboratory observation, not a continuous curve.
            track.plot.setXRange(0.0, 3.0, padding=0)
            track.set_curve_headers(
                [
                    (
                        "__lba_legend__",
                        self._localizer.text("tablet.lba_columns"),
                        "#f97316",
                    )
                ]
            )
            for divider in (1.0, 2.0):
                track.plot.addItem(
                    pg.InfiniteLine(
                        pos=divider,
                        angle=90,
                        movable=False,
                        pen=pg.mkPen("#94a3b8", width=0.8),
                    )
                )
        track.plot.setMouseEnabled(x=False, y=True)

        rendered: dict[str, tuple[object, ...]] = {}
        for sample in self._cuttings:
            axis_top, axis_bottom = self._depth_interval_to_axis(
                sample.top_depth, sample.bottom_depth
            )
            center = (axis_top + axis_bottom) / 2.0
            height = max(axis_bottom - axis_top, np.finfo(float).eps)
            items: list[object] = []

            if definition.kind is TrackKind.CALCIMETRY:
                if sample.calcite_percent is None and sample.dolomite_percent is None:
                    continue
                calcite = sample.calcite_percent
                dolomite = sample.dolomite_percent
                residue = sample.insoluble_residue_percent
                tooltip_parts = [
                    self._localizer.text(
                        "tablet.sample_interval",
                        top=f"{sample.top_depth:g}",
                        bottom=f"{sample.bottom_depth:g}",
                    )
                ]
                if calcite is not None:
                    tooltip_parts.append(
                        f"{self._localizer.text('tablet.calcimetry_calcite')}: {calcite:g} %"
                    )
                if dolomite is not None:
                    tooltip_parts.append(
                        f"{self._localizer.text('tablet.calcimetry_dolomite')}: {dolomite:g} %"
                    )
                if residue is not None:
                    tooltip_parts.append(
                        f"{self._localizer.text('tablet.calcimetry_residue')}: {residue:g} %"
                    )
                tooltip = "\n".join(tooltip_parts)

                frame = pg.BarGraphItem(
                    x=[50.0],
                    y=[center],
                    width=100.0,
                    height=height,
                    brush=pg.mkBrush(255, 255, 255, 0),
                    pen=pg.mkPen("#64748b", width=0.8),
                )
                frame.setToolTip(tooltip)
                track.plot.addItem(frame)
                items.append(frame)

                left = 0.0
                for label, value, color in (
                    (self._localizer.text("tablet.calcimetry_calcite"), calcite, "#06b6d4"),
                    (self._localizer.text("tablet.calcimetry_dolomite"), dolomite, "#8b5cf6"),
                    (self._localizer.text("tablet.calcimetry_residue"), residue, "#cbd5e1"),
                ):
                    if value is None:
                        continue
                    numeric = min(100.0, max(0.0, float(value)))
                    if numeric > 0.0:
                        bar = pg.BarGraphItem(
                            x=[left + numeric / 2.0],
                            y=[center],
                            width=numeric,
                            height=height,
                            brush=pg.mkBrush(color),
                            pen=pg.mkPen("#334155", width=0.55),
                        )
                        bar.setToolTip(f"{tooltip}\n{label}: {numeric:g} %")
                        track.plot.addItem(bar)
                        items.append(bar)
                    else:
                        zero = pg.PlotDataItem(
                            [left, left],
                            [axis_top, axis_bottom],
                            pen=pg.mkPen(color, width=2.0),
                            connect="finite",
                        )
                        zero.setToolTip(f"{tooltip}\n{label}: 0 %")
                        track.plot.addItem(zero)
                        items.append(zero)
                    left += numeric

                text_values = []
                if calcite is not None:
                    text_values.append(f"Ca {calcite:g}")
                if dolomite is not None:
                    text_values.append(f"Do {dolomite:g}")
                label = pg.TextItem(
                    " / ".join(text_values),
                    color="#0f172a",
                    anchor=(0.5, 0.5),
                )
                label.setPos(50.0, center)
                label.setToolTip(tooltip)
                track.plot.addItem(label)
                items.append(label)
            else:
                fields = [
                    f"{self._localizer.text('tablet.lba_group')}: {sample.lba_group}"
                    if sample.lba_group is not None
                    else None,
                    f"{self._localizer.text('tablet.lba_type')}: {sample.lba_type_id}"
                    if sample.lba_type_id
                    else None,
                    f"{self._localizer.text('tablet.lba_intensity')}: {sample.lba_intensity}"
                    if sample.lba_intensity is not None
                    else None,
                    f"{self._localizer.text('tablet.lba_color')}: {sample.lba_color}"
                    if sample.lba_color
                    else None,
                    f"{self._localizer.text('tablet.lba_distribution')}: {sample.lba_distribution}"
                    if sample.lba_distribution
                    else None,
                    f"{self._localizer.text('tablet.lba_cut')}: {sample.lba_cut}"
                    if sample.lba_cut
                    else None,
                    f"{self._localizer.text('tablet.lba_cut_speed')}: {sample.lba_cut_speed}"
                    if sample.lba_cut_speed
                    else None,
                    f"{self._localizer.text('tablet.lba_cut_color')}: {sample.lba_cut_color}"
                    if sample.lba_cut_color
                    else None,
                    f"{self._localizer.text('tablet.lba_residue_type')}: {sample.lba_residue_type}"
                    if sample.lba_residue_type
                    else None,
                    f"{self._localizer.text('tablet.lba_residue_color')}: {sample.lba_residue_color}"
                    if sample.lba_residue_color
                    else None,
                    f"{self._localizer.text('tablet.lba_odour')}: {sample.lba_odour}"
                    if sample.lba_odour
                    else None,
                    f"{self._localizer.text('tablet.lba_stain')}: {sample.lba_stain}"
                    if sample.lba_stain
                    else None,
                    sample.lba_description,
                ]
                if not any(value not in (None, "") for value in fields):
                    continue
                tooltip = (
                    self._localizer.text(
                        "tablet.sample_interval",
                        top=f"{sample.top_depth:g}",
                        bottom=f"{sample.bottom_depth:g}",
                    )
                    + "\n"
                    + "\n".join(str(value) for value in fields if value not in (None, ""))
                )
                style = resolve_lba_type_style(sample.lba_type_id)
                intensity = normalized_lba_intensity(sample.lba_intensity)

                band = pg.BarGraphItem(
                    x=[1.5],
                    y=[center],
                    width=3.0,
                    height=height,
                    brush=pg.mkBrush(255, 255, 255, 0),
                    pen=pg.mkPen("#94a3b8", width=0.7),
                )
                band.setToolTip(tooltip)
                track.plot.addItem(band)
                items.append(band)

                # 1. BALЛЫ: larger ring/spot for a stronger 1–5 result.
                size = (
                    {1: 8.0, 2: 12.0, 3: 14.0, 4: 17.0, 5: 20.0}.get(
                        intensity, 10.0
                    )
                    if intensity is not None
                    else 10.0
                )
                line_width = 3.0 if intensity == 4 else 1.4
                line_style = Qt.PenStyle.DashLine if intensity == 2 else Qt.PenStyle.SolidLine
                brush = pg.mkBrush(style.color) if intensity in {1, 5} else pg.mkBrush(None)
                scatter = pg.ScatterPlotItem(
                    x=[0.5],
                    y=[center],
                    symbol="o",
                    size=size,
                    pen=pg.mkPen(style.color, width=line_width, style=line_style),
                    brush=brush,
                    pxMode=True,
                )
                scatter.setToolTip(tooltip)
                track.plot.addItem(scatter)
                items.append(scatter)
                if intensity is not None:
                    score = pg.TextItem(str(intensity), color="#0f172a", anchor=(0.5, 0.5))
                    score.setPos(0.5, center)
                    score.setToolTip(tooltip)
                    track.plot.addItem(score)
                    items.append(score)

                # 2. ЦВЕТ: fluorescence code entered by the geologist.
                fluorescence_colors = {
                    "БГ": "#e0f2fe",
                    "БЖ": "#fef9c3",
                    "СЖ": "#fde68a",
                    "ГЖ": "#bef264",
                    "Ж": "#facc15",
                    "ОЖ": "#fb923c",
                    "О": "#f97316",
                    "К": "#ef4444",
                    "ТК": "#991b1b",
                    "Ч": "#111827",
                }
                fluorescence_code = (sample.lba_color or "").strip().upper()
                fluorescence_color = fluorescence_colors.get(fluorescence_code, "#ffffff")
                color_cell = pg.BarGraphItem(
                    x=[1.5],
                    y=[center],
                    width=0.88,
                    height=height,
                    brush=pg.mkBrush(fluorescence_color),
                    pen=pg.mkPen("#64748b", width=0.6),
                )
                color_cell.setToolTip(tooltip)
                track.plot.addItem(color_cell)
                items.append(color_cell)
                if fluorescence_code:
                    foreground = "#ffffff" if fluorescence_code in {"ТК", "Ч"} else "#0f172a"
                    color_label = pg.TextItem(
                        fluorescence_code, color=foreground, anchor=(0.5, 0.5)
                    )
                    color_label.setPos(1.5, center)
                    color_label.setToolTip(tooltip)
                    track.plot.addItem(color_label)
                    items.append(color_label)

                # 3. БИТУМ: interval block colored by LB/MB/MSB/SB/SAB class.
                bitumen_cell = pg.BarGraphItem(
                    x=[2.5],
                    y=[center],
                    width=0.88,
                    height=height,
                    brush=pg.mkBrush(style.color),
                    pen=pg.mkPen("#475569", width=0.65),
                )
                bitumen_cell.setToolTip(tooltip)
                track.plot.addItem(bitumen_cell)
                items.append(bitumen_cell)
                label_color = "#0f172a" if style.code in {"ЛБ", "МБ", "МСБ"} else "#ffffff"
                label = pg.TextItem(style.code, color=label_color, anchor=(0.5, 0.5))
                label.setPos(2.5, center)
                label.setToolTip(tooltip)
                track.plot.addItem(label)
                items.append(label)

            if items:
                rendered[sample.sample_id] = tuple(items)

        if not rendered:
            has_curve_data = False
            if definition.kind is TrackKind.CALCIMETRY and self._dataset is not None:
                for mnemonic in definition.curve_mnemonics:
                    curve = self._dataset.curve_by_mnemonic(mnemonic)
                    if curve is not None and np.any(np.isfinite(curve.values)):
                        has_curve_data = True
                        break
            if not has_curve_data:
                message = pg.TextItem(
                    self._localizer.text(
                        "tablet.calcimetry_empty"
                        if definition.kind is TrackKind.CALCIMETRY
                        else "tablet.lba_empty"
                    ),
                    color="#64748b",
                    anchor=(0.5, 0.5),
                )
                bounds = self._depth_bounds()
                center_depth = sum(bounds) / 2.0 if bounds is not None else 0.0
                message.setPos(
                    50.0 if definition.kind is TrackKind.CALCIMETRY else 1.5, center_depth
                )
                track.plot.addItem(message)
                rendered["__empty__"] = (message,)
        return rendered

    def _populate_lithology_descriptions(
        self, track: TabletTrackWidget, definition: TrackDefinition
    ) -> dict[str, pg.TextItem]:
        """Render rich cuttings text and lithology fallback in one text track.

        Cuttings descriptions have priority because they are entered for an
        exact sample interval and may contain rich HTML or embedded images.
        Lithology text is used only when no cuttings description overlaps the
        interval, which keeps old projects readable without duplicating text.
        """
        if definition.kind is not TrackKind.TEXT:
            return {}
        rendered: dict[str, pg.TextItem] = {}
        # ``QGraphicsTextItem.setTextWidth`` looks attractive for wrapping, but
        # inside the vertically transformed pyqtgraph ViewBox it can collapse a
        # rich-text item to an invisible geometry.  Wrap plain text explicitly
        # and let rich HTML retain the formatting produced by QTextEdit.
        text_width = max(80, definition.width - 30)
        wrap_columns = max(18, int(text_width / 7.0))
        described_ranges: list[tuple[float, float]] = []

        def plain_html(value: str) -> str:
            paragraphs = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            lines: list[str] = []
            for paragraph in paragraphs:
                if not paragraph:
                    lines.append("")
                    continue
                wrapped = textwrap.wrap(
                    paragraph,
                    width=wrap_columns,
                    replace_whitespace=False,
                    drop_whitespace=True,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                lines.extend(wrapped or [paragraph])
            return "<br/>".join(escape(line) for line in lines)

        def rich_body(value: str) -> str:
            body_match = re.search(
                r"<body[^>]*>(?P<body>.*)</body>",
                value,
                flags=re.IGNORECASE | re.DOTALL,
            )
            return body_match.group("body") if body_match is not None else value

        for sample in self._cuttings:
            description = (sample.description or "").strip()
            if not description:
                continue
            label = pg.TextItem(anchor=(0.0, 0.5))
            body = (
                rich_body(description)
                if "<" in description and ">" in description
                else plain_html(description)
            )
            label.setHtml(f'<div style="color:#202020; margin:0; padding:0;">{body}</div>')
            label.textItem.setTextWidth(float(text_width))
            label.updateTextPos()
            axis_top, axis_bottom = self._depth_interval_to_axis(
                sample.top_depth, sample.bottom_depth
            )
            label.setPos(0.02, (axis_top + axis_bottom) / 2.0)
            label.setToolTip(
                self._localizer.text(
                    "tablet.sample_interval",
                    top=f"{sample.top_depth:g}",
                    bottom=f"{sample.bottom_depth:g}",
                )
            )
            track.plot.addItem(label)
            rendered[sample.sample_id] = label
            described_ranges.append((sample.top_depth, sample.bottom_depth))

        for interval in self._lithology:
            overlaps_sample_text = any(
                interval.top_depth < bottom and interval.bottom_depth > top
                for top, bottom in described_ranges
            )
            if overlaps_sample_text:
                continue
            lithotype = self._lithotype_catalog.get(interval.lithotype_id)
            fallback = lithotype.name_ru if lithotype is not None else interval.lithotype_id
            description = (interval.description or "").strip() or fallback
            label = pg.TextItem(anchor=(0.0, 0.5))
            label.setHtml(
                f'<div style="color:#202020; margin:0; padding:0;">{plain_html(description)}</div>'
            )
            label.textItem.setTextWidth(float(text_width))
            label.updateTextPos()
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
        if definition.kind is not TrackKind.LITHOLOGY or not definition.show_interval_labels:
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

    def _sync_annotation_overlay_geometry(self) -> None:
        self._annotation_overlay.setGeometry(self._tracks_container.rect())
        content_rect = QRectF()
        for rendered in self._rendered.values():
            plot = rendered.plot
            if plot is None:
                continue
            try:
                scene_rect = plot.getViewBox().sceneBoundingRect()
                top_left = plot.mapFromScene(scene_rect.topLeft())
                bottom_right = plot.mapFromScene(scene_rect.bottomRight())
                mapped_top_left = plot.mapTo(self._tracks_container, top_left)
                mapped_bottom_right = plot.mapTo(self._tracks_container, bottom_right)
                plot_rect = QRectF(
                    QPointF(mapped_top_left), QPointF(mapped_bottom_right)
                ).normalized()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                origin = plot.mapTo(self._tracks_container, QPoint(0, 0))
                plot_rect = QRectF(
                    QPointF(origin),
                    QPointF(origin.x() + plot.width(), origin.y() + plot.height()),
                )
            content_rect = plot_rect if content_rect.isEmpty() else content_rect.united(plot_rect)
            plot.viewport().setCursor(
                Qt.CursorShape.CrossCursor
                if self._annotation_tool is not None
                else Qt.CursorShape.ArrowCursor
            )
        self._annotation_overlay.set_content_rect(content_rect)
        self._annotation_overlay.raise_()

    def _annotation_target_track(self, record) -> RenderedTrack | None:
        if record.track_id and record.track_id in self._rendered:
            return self._rendered[record.track_id]
        # A legacy/all-tracks annotation is a single object, not one duplicate
        # per column. Prefer the currently selected track, then the first
        # visible non-depth track.
        selected = getattr(self, "_selected_track_id", None)
        if selected and selected in self._rendered:
            return self._rendered[selected]
        return next(
            (
                item
                for item in self._rendered.values()
                if item.definition.kind is not TrackKind.DEPTH
            ),
            next(iter(self._rendered.values()), None),
        )

    def _annotation_anchor_in_canvas(self, record) -> QPointF | None:
        rendered = self._annotation_target_track(record)
        if rendered is None or rendered.plot is None:
            return None
        axis_value = self._annotation_axis_value(record)
        if axis_value is None or not np.isfinite(axis_value):
            return None
        anchor_x = self._annotation_anchor_x(rendered.widget, record)
        try:
            scene_point = rendered.plot.getViewBox().mapViewToScene(
                QPointF(float(anchor_x), float(axis_value))
            )
            viewport_point = rendered.plot.mapFromScene(scene_point)
            return QPointF(
                rendered.plot.mapTo(self._tracks_container, viewport_point)
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None

    def _refresh_annotation_overlay(self) -> None:
        self._sync_annotation_overlay_geometry()
        entries: list[tuple[AnnotationRecord, QPointF, QPixmap | None]] = []
        for canvas_item in self._canvas_objects:
            if not is_annotation_object(canvas_item):
                continue
            record = annotation_from_canvas(canvas_item)
            anchor = self._annotation_anchor_in_canvas(record)
            if anchor is None:
                continue
            pixmap = None
            if record.asset_ref:
                asset = self._image_assets.get(record.asset_ref)
                if asset is not None:
                    pixmap = image_asset_pixmap(asset)
            entries.append((record, anchor, pixmap))
        self._annotation_overlay.set_entries(entries)
        self._annotation_overlay.set_edit_mode(self._form_edit_mode)
        self._annotation_overlay.set_print_mode(self._annotation_print_mode)
        self._annotation_overlay.raise_()

    def _refresh_annotation_overlay_anchors(self) -> None:
        """Remap data-bound annotations after scrolling or zooming the axis.

        Saved ``offset_x``/``offset_y`` values describe the callout box relative
        to its depth/time/curve anchor. Only the anchor's screen position changes
        during navigation. Updating just those positions preserves user geometry
        and avoids rebuilding the complete annotation layer on every wheel step.
        """

        if not self._canvas_objects:
            return
        anchors: dict[str, QPointF] = {}
        for canvas_item in self._canvas_objects:
            if not is_annotation_object(canvas_item):
                continue
            record = annotation_from_canvas(canvas_item)
            anchor = self._annotation_anchor_in_canvas(record)
            if anchor is not None:
                anchors[record.annotation_id] = anchor
        self._annotation_overlay.set_anchor_positions(anchors)

    @property
    def selected_annotation_id(self) -> str | None:
        return self._annotation_overlay.selected_annotation_id

    def select_annotation(self, annotation_id: str | None) -> None:
        self._annotation_overlay.select_annotation(annotation_id)

    def edit_selected_annotation(self) -> bool:
        return self._annotation_overlay.edit_selected()

    def delete_selected_annotation(self) -> bool:
        return self._annotation_overlay.delete_selected()

    def duplicate_selected_annotation(self) -> bool:
        return self._annotation_overlay.duplicate_selected()

    def paint_annotations_for_track(
        self,
        track_id: str,
        painter: QPainter,
    ) -> None:
        rendered = self._rendered.get(track_id)
        if rendered is None:
            return
        origin = QPointF(rendered.widget.mapTo(self._tracks_container, QPoint(0, 0)))
        self._annotation_overlay.paint_translated(painter, origin, print_mode=True)

    def _annotation_axis_value(self, record) -> float | None:
        if record.anchor is AnnotationAnchor.TIME:
            if (
                record.axis_value is not None
                and (record.axis_id is None or record.axis_id == self.vertical_index_id)
            ):
                return float(record.axis_value)
            if record.depth is not None:
                return self._depth_to_axis_value(float(record.depth))
            return None
        if record.depth is not None:
            return self._depth_to_axis_value(float(record.depth))
        if record.axis_value is not None:
            return float(record.axis_value)
        return None

    def _annotation_anchor_x(self, track: TabletTrackWidget, record) -> float:
        definition = track.definition
        if (
            record.anchor is AnnotationAnchor.CURVE
            and record.parameter_mnemonic
            and record.depth is not None
            and self._dataset is not None
        ):
            curve = self._dataset.curve_by_mnemonic(record.parameter_mnemonic)
            if curve is not None and curve.values.size == self._dataset.depth.size:
                finite = np.flatnonzero(
                    np.isfinite(self._dataset.depth) & np.isfinite(curve.values)
                )
                if finite.size:
                    index = int(
                        finite[
                            np.argmin(
                                np.abs(
                                    self._dataset.depth[finite] - float(record.depth)
                                )
                            )
                        ]
                    )
                    value = float(curve.values[index])
                    if np.isfinite(value):
                        return self._curve_pencil_display_x(
                            definition, record.parameter_mnemonic, value
                        )
        if definition.kind is TrackKind.CALCIMETRY:
            return float(record.x_fraction) * 100.0
        view_range = None
        track_range = track.plot.getViewBox().viewRange()[0]
        if track_range is not None:
            view_range = tuple(float(value) for value in track_range)
        if view_range is None:
            if definition.kind is TrackKind.STRATIGRAPHY:
                rank_count = len({item.rank or "" for item in self._stratigraphy})
                view_range = (0.0, float(max(1, rank_count)))
            elif definition.kind is TrackKind.INTERPRETATION:
                type_count = len(
                    {
                        interval.interval_type
                        for interpretation in self._interpretations
                        for interval in interpretation.intervals
                    }
                )
                view_range = (0.0, float(max(1, type_count)))
            else:
                view_range = (0.0, 1.0)
        return view_range[0] + float(record.x_fraction) * (view_range[1] - view_range[0])

    def _show_annotation_context_menu(self, annotation_id: str, global_pos: QPoint) -> None:
        menu = QMenu(self)
        edit_action = menu.addAction(self._localizer.text("annotations.edit_action"))
        duplicate_action = menu.addAction(
            self._localizer.text("annotations.duplicate_action")
        )
        menu.addSeparator()
        delete_action = menu.addAction(self._localizer.text("annotations.delete_action"))
        chosen = menu.exec(global_pos)
        if chosen == edit_action:
            self.annotation_edit_requested.emit(annotation_id)
        elif chosen == duplicate_action:
            self.annotation_duplicate_requested.emit(annotation_id)
        elif chosen == delete_action:
            self.annotation_delete_requested.emit(annotation_id)

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
        lithology_intervals = {item.interval_id: item for item in self._lithology}
        cuttings_intervals = {item.sample_id: item for item in self._cuttings}
        for rendered in self._rendered.values():
            if rendered.plot is None:
                continue
            viewport_height = rendered.plot.viewport().height()
            for items, minimum_pixels in (
                (rendered.lithology_label_items or {}, 16),
                (rendered.lithology_description_items or {}, 34),
            ):
                for interval_id, text_item in items.items():
                    lithology_interval = lithology_intervals.get(interval_id)
                    cuttings_interval = cuttings_intervals.get(interval_id)
                    interval_top = (
                        lithology_interval.top_depth
                        if lithology_interval is not None
                        else cuttings_interval.top_depth
                        if cuttings_interval is not None
                        else None
                    )
                    interval_bottom = (
                        lithology_interval.bottom_depth
                        if lithology_interval is not None
                        else cuttings_interval.bottom_depth
                        if cuttings_interval is not None
                        else None
                    )
                    axis_interval = (
                        self._depth_interval_to_axis(interval_top, interval_bottom)
                        if interval_top is not None and interval_bottom is not None
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
            top, bottom = self._normalize_depth_window(float(y_range[0]), float(y_range[1]))
            self._layout_model.set_visible_depth(top, bottom)
            self._update_visible_curve_data(top, bottom)
            self._synchronize_depth_ranges(top, bottom)
            self._update_lithology_text_visibility(top, bottom)
            self._update_stratigraphy_text_visibility(top, bottom)
            # A direct ViewBox gesture (wheel, pan or zoom) bypasses
            # _apply_visible_depth, so synchronize data-bound annotations here
            # as well. Otherwise their boxes stay at stale screen coordinates.
            self._refresh_annotation_overlay_anchors()
            self._update_navigation_controls()
            self.visible_depth_changed.emit(top, bottom)
        finally:
            self._sync_guard = False
