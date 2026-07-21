from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.curve_editing import DrawPoint, interpolate_drawn_curve
from geoworkbench.services.channel_groups import default_curve_mnemonics
from geoworkbench.services.dataset_selection import DatasetIntervalSelection
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.sampling import MAX_RENDERED_POINTS, select_visible_samples


class CurveView(QWidget):
    edit_requested = Signal(str, object, object)
    edit_target_changed = Signal(str)

    CURVE_COLORS = (
        "#f8fafc",
        "#22d3ee",
        "#facc15",
        "#4ade80",
        "#fb7185",
        "#c084fc",
    )

    def __init__(
        self,
        selection: DatasetIntervalSelection | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__()
        self.localizer = Localizer.create(language)
        self.selection = selection or DatasetIntervalSelection()
        self.selection.changed.connect(self._apply_shared_selection)
        self._dataset: Dataset | None = None
        self._editable_curve: CurveData | None = None
        self._edit_mode = False
        self._draw_points: list[DrawPoint] = []
        self._displayed_curve_ids: tuple[str, ...] = ()
        self._curve_items: dict[str, pg.PlotDataItem] = {}
        self._edit_preview_item: pg.PlotDataItem | None = None
        self._pencil_cursor = self._build_pencil_cursor()
        self._selection_region: pg.LinearRegionItem | None = None
        self._cursor_horizontal: pg.InfiniteLine | None = None
        self._cursor_vertical: pg.InfiniteLine | None = None
        self._applying_shared_selection = False
        self._depth_range_guard = False
        self._last_cursor_depth: float | None = None
        self._last_cursor_value: float | None = None
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("left", self._t("curve.axis.depth"), units="m")
        self._plot.getAxis("left").enableAutoSIPrefix(False)
        self._plot.setLabel("bottom", self._t("curve.axis.value"))
        self._legend = self._plot.addLegend(offset=(8, 8))
        self._plot.sigYRangeChanged.connect(self._on_depth_range_changed)
        self._plot.viewport().installEventFilter(self)
        self._plot.viewport().setMouseTracking(True)
        self._title = QLabel(self._t("curve.empty"))
        self._title.setStyleSheet("font-weight: 600; padding: 6px;")
        self._edit_target_label = QLabel(self._t("curve.edit_target"))
        self._curve_selector = QComboBox()
        self._curve_selector.setMinimumWidth(220)
        self._curve_selector.setToolTip(self._t("curve.edit_target_tooltip"))
        self._curve_selector.currentIndexChanged.connect(self._on_curve_selector_changed)
        self._edit_status = QLabel(self._t("curve.edit_inactive"))
        self._edit_status.setStyleSheet("padding: 3px 8px; color:#475569;")
        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(6, 0, 6, 0)
        edit_row.addWidget(self._edit_target_label)
        edit_row.addWidget(self._curve_selector, 1)
        edit_row.addWidget(self._edit_status)
        self._cursor_label = QLabel(self._t("curve.cursor_empty"))
        self._cursor_label.setObjectName("curve-cursor-values")
        self._cursor_label.setStyleSheet("padding: 4px 6px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addLayout(edit_row)
        layout.addWidget(self._cursor_label)
        layout.addWidget(self._plot)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @staticmethod
    def _build_pencil_cursor() -> QCursor:
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#0f172a"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(6, 22, 21, 7)
        painter.setPen(QPen(QColor("#f59e0b"), 5.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(9, 20, 20, 9)
        painter.setPen(QPen(QColor("#0f172a"), 1.5))
        painter.drawLine(5, 23, 10, 21)
        painter.end()
        return QCursor(pixmap, 5, 23)

    @staticmethod
    def _curve_is_directly_editable(curve: CurveData) -> bool:
        provenance = (curve.metadata.provenance or "").strip().casefold()
        description = (curve.metadata.description or "").strip().casefold()
        calculated_prefixes = ("calculation:", "custom-formula:")
        # Older project snapshots sometimes stored the calculation marker in
        # description before the dedicated provenance field was introduced.
        # Treat both representations as derived data: pencil editing must only
        # target source curves, otherwise recalculation contracts are bypassed.
        return (
            not provenance.startswith(calculated_prefixes)
            and not description.startswith(calculated_prefixes)
            and provenance != "derived"
        )

    def _populate_curve_selector(self) -> None:
        current_id = self._editable_curve.metadata.curve_id if self._editable_curve else None
        self._curve_selector.blockSignals(True)
        self._curve_selector.clear()
        self._curve_selector.addItem(self._t("curve.edit_choose"), None)
        if self._dataset is not None:
            curves = sorted(
                (
                    curve
                    for curve in self._dataset.curves.values()
                    if self._curve_is_directly_editable(curve)
                ),
                key=lambda item: item.metadata.original_mnemonic.casefold(),
            )
            for curve in curves:
                mnemonic = curve.metadata.original_mnemonic
                unit = (curve.metadata.unit or "").strip()
                label = f"{mnemonic} [{unit}]" if unit else mnemonic
                self._curve_selector.addItem(label, mnemonic)
                if curve.metadata.curve_id == current_id:
                    self._curve_selector.setCurrentIndex(self._curve_selector.count() - 1)
        self._curve_selector.blockSignals(False)

    def _on_curve_selector_changed(self, index: int) -> None:
        if self._dataset is None or index <= 0:
            return
        mnemonic = self._curve_selector.itemData(index)
        if not isinstance(mnemonic, str) or not mnemonic:
            return
        was_editing = self._edit_mode
        dataset = self._dataset
        self.show_dataset(dataset, [mnemonic])
        self.edit_target_changed.emit(mnemonic)
        if was_editing:
            self.set_edit_mode(True)

    def set_language(self, language: AppLanguage) -> None:
        self.localizer = Localizer.create(language)
        self._plot.setLabel("left", self._t("curve.axis.depth"), units="m")
        self._plot.setLabel("bottom", self._t("curve.axis.value"))
        self._edit_target_label.setText(self._t("curve.edit_target"))
        self._curve_selector.setToolTip(self._t("curve.edit_target_tooltip"))
        self._edit_status.setText(
            self._t("curve.edit_active") if self._edit_mode else self._t("curve.edit_inactive")
        )
        self._populate_curve_selector()
        if self._dataset is None:
            self._title.setText(self._t("curve.empty"))
        else:
            self._title.setText(
                self._t(
                    "curve.title_summary",
                    dataset=self._dataset.name,
                    count=len(self._displayed_curve_ids),
                    samples=len(self._dataset.depth),
                )
            )
        if self._last_cursor_depth is None:
            self._cursor_label.setText(self._t("curve.cursor_empty"))
        else:
            self.show_cursor_at_depth(
                self._last_cursor_depth,
                self._last_cursor_value,
            )

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def can_edit(self) -> bool:
        return self._dataset is not None and self._editable_curve is not None

    @property
    def editable_mnemonic(self) -> str | None:
        if self._editable_curve is None:
            return None
        return self._editable_curve.metadata.original_mnemonic

    @property
    def cursor_text(self) -> str:
        return self._cursor_label.text()

    @property
    def displayed_mnemonics(self) -> tuple[str, ...]:
        if self._dataset is None:
            return ()
        return tuple(
            curve.metadata.original_mnemonic
            for curve_id in self._displayed_curve_ids
            if (curve := self._dataset.curves.get(curve_id)) is not None
        )

    def clear(self) -> None:
        self._dataset = None
        self._editable_curve = None
        self._edit_mode = False
        self._draw_points.clear()
        self._displayed_curve_ids = ()
        self._curve_items.clear()
        self._edit_preview_item = None
        self._plot.clear()
        self._legend.clear()
        self._selection_region = None
        self._cursor_horizontal = None
        self._cursor_vertical = None
        self._last_cursor_depth = None
        self._last_cursor_value = None
        self._cursor_label.setText(self._t("curve.cursor_empty"))
        self._title.setText(self._t("curve.empty"))
        self._plot.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self._edit_status.setText(self._t("curve.edit_inactive"))
        self._populate_curve_selector()

    def set_edit_mode(self, enabled: bool) -> bool:
        self._edit_mode = enabled and self.can_edit
        self._draw_points.clear()
        self._clear_edit_preview()
        self._plot.viewport().setCursor(
            self._pencil_cursor if self._edit_mode else Qt.CursorShape.ArrowCursor
        )
        self._edit_status.setText(
            self._t("curve.edit_active") if self._edit_mode else self._t("curve.edit_inactive")
        )
        self._edit_status.setStyleSheet(
            "padding: 3px 8px; font-weight:600; color:#166534;"
            if self._edit_mode
            else "padding: 3px 8px; color:#475569;"
        )
        return self._edit_mode

    def select_editable_curve(self, mnemonic: str, *, enable_edit: bool = False) -> bool:
        if self._dataset is None:
            return False
        curve = self._dataset.curve_by_mnemonic(mnemonic)
        if curve is None or not self._curve_is_directly_editable(curve):
            return False
        dataset = self._dataset
        self.show_dataset(dataset, [mnemonic])
        return self.set_edit_mode(True) if enable_edit else True

    def _update_edit_preview(self) -> None:
        if not self._draw_points:
            self._clear_edit_preview()
            return
        if self._edit_preview_item is None:
            self._edit_preview_item = pg.PlotDataItem(
                pen=pg.mkPen("#f97316", width=2.5),
                symbol="o",
                symbolSize=4,
                symbolBrush=pg.mkBrush("#f97316"),
                connect="finite",
            )
            self._edit_preview_item.setZValue(100)
            self._plot.addItem(self._edit_preview_item)
        self._edit_preview_item.setData(
            [point.value for point in self._draw_points],
            [point.depth for point in self._draw_points],
            connect="finite",
        )

    def _clear_edit_preview(self) -> None:
        if self._edit_preview_item is not None:
            try:
                self._plot.removeItem(self._edit_preview_item)
            except RuntimeError:
                pass
            self._edit_preview_item = None

    def show_dataset(self, dataset: Dataset, selected: list[str] | None = None) -> None:
        self._depth_range_guard = True
        self._dataset = dataset
        self._editable_curve = None
        self._draw_points.clear()
        self._displayed_curve_ids = ()
        self._curve_items.clear()
        self._edit_preview_item = None
        self._plot.clear()
        self._legend.clear()
        self._plot.getViewBox().disableAutoRange(axis=pg.ViewBox.YAxis)
        self._selection_region = None
        self._cursor_horizontal = None
        self._cursor_vertical = None
        self._last_cursor_depth = None
        self._last_cursor_value = None
        self._cursor_label.setText(self._t("curve.cursor_empty"))
        selected_names = default_curve_mnemonics(dataset) if selected is None else selected
        finite_depth = dataset.depth[np.isfinite(dataset.depth)]
        if len(selected_names) == 1:
            candidate = dataset.curve_by_mnemonic(selected_names[0])
            if candidate is not None and self._curve_is_directly_editable(candidate):
                self._editable_curve = candidate
        self._populate_curve_selector()
        count = 0
        displayed_curve_ids: list[str] = []
        for selected_mnemonic in selected_names:
            curve = dataset.curve_by_mnemonic(selected_mnemonic)
            if curve is None or curve.metadata.curve_id in displayed_curve_ids:
                continue
            mnemonic = curve.metadata.original_mnemonic
            values = np.asarray(curve.values, dtype=np.float64)
            if finite_depth.size == 0:
                continue
            visible_values, visible_depth = select_visible_samples(
                np.asarray(dataset.depth, dtype=np.float64),
                values,
                float(np.min(finite_depth)),
                float(np.max(finite_depth)),
                max_points=MAX_RENDERED_POINTS,
            )
            if visible_depth.size == 0 or not np.any(np.isfinite(visible_values)):
                continue
            unit = (curve.metadata.unit or "").strip()
            legend = f"{mnemonic} [{unit}]" if unit else mnemonic
            color = self.CURVE_COLORS[count % len(self.CURVE_COLORS)]
            self._curve_items[curve.metadata.curve_id] = self._plot.plot(
                visible_values,
                visible_depth,
                name=legend,
                pen=pg.mkPen(color, width=1.2),
                connect="finite",
            )
            count += 1
            displayed_curve_ids.append(curve.metadata.curve_id)
        self._displayed_curve_ids = tuple(displayed_curve_ids)
        self._plot.getViewBox().invertY(True)
        if finite_depth.size:
            self._plot.setYRange(
                float(np.min(finite_depth)),
                float(np.max(finite_depth)),
                padding=0,
            )
        self._depth_range_guard = False
        self._create_cursor_lines()
        if finite_depth.size:
            self._selection_region = pg.LinearRegionItem(
                values=(float(np.min(finite_depth)), float(np.max(finite_depth))),
                orientation=pg.LinearRegionItem.Horizontal,
                movable=True,
                brush=pg.mkBrush(70, 130, 180, 35),
            )
            self._selection_region.setZValue(20)
            self._selection_region.sigRegionChangeFinished.connect(self._publish_region_selection)
            self._plot.addItem(self._selection_region)
            if self.selection.dataset_id != dataset.dataset_id:
                self.selection.select(
                    dataset,
                    float(np.min(finite_depth)),
                    float(np.max(finite_depth)),
                    self._displayed_curve_ids,
                )
            self._apply_shared_selection()
        self._title.setText(
            self._t(
                "curve.title_summary",
                dataset=dataset.name,
                count=count,
                samples=len(dataset.depth),
            )
        )
        if self._edit_mode and not self.can_edit:
            self.set_edit_mode(False)

    def _update_visible_curve_data(self, top: float, bottom: float) -> None:
        if self._dataset is None:
            return
        depth = np.asarray(self._dataset.depth, dtype=np.float64)
        for curve_id, item in self._curve_items.items():
            curve = self._dataset.curves.get(curve_id)
            if curve is None:
                item.setData([], [])
                continue
            values, visible_depth = select_visible_samples(
                depth,
                np.asarray(curve.values, dtype=np.float64),
                top,
                bottom,
                max_points=MAX_RENDERED_POINTS,
            )
            item.setData(values, visible_depth, connect="finite")

    def _on_depth_range_changed(self, _view_box, y_range) -> None:
        if self._depth_range_guard:
            return
        top, bottom = sorted((float(y_range[0]), float(y_range[1])))
        self._depth_range_guard = True
        try:
            self._update_visible_curve_data(top, bottom)
        finally:
            self._depth_range_guard = False

    def show_cursor_at_depth(self, depth: float, value: float | None = None) -> bool:
        dataset = self._dataset
        if dataset is None or not np.isfinite(depth):
            return False
        finite = np.flatnonzero(np.isfinite(dataset.depth))
        if finite.size == 0:
            return False
        nearest = int(finite[np.argmin(np.abs(dataset.depth[finite] - depth))])
        snapped_depth = float(dataset.depth[nearest])
        self._last_cursor_depth = snapped_depth
        self._last_cursor_value = value
        depth_unit = "ms" if dataset.depth_domain.value == "time" else "m"
        parts = [
            self._t(
                "curve.cursor_depth",
                depth=f"{snapped_depth:.8g}",
                unit=depth_unit,
            )
        ]
        for curve_id in self._displayed_curve_ids:
            curve = dataset.curves.get(curve_id)
            if curve is None:
                continue
            sample = float(curve.values[nearest])
            rendered = f"{sample:.8g}" if np.isfinite(sample) else "—"
            unit = f" {curve.metadata.unit}" if curve.metadata.unit else ""
            parts.append(f"{curve.metadata.original_mnemonic}: {rendered}{unit}")
        self._cursor_label.setText("  |  ".join(parts))
        if self._cursor_horizontal is not None:
            self._cursor_horizontal.setPos(snapped_depth)
            self._cursor_horizontal.show()
        if self._cursor_vertical is not None:
            if value is not None and np.isfinite(value):
                self._cursor_vertical.setPos(value)
                self._cursor_vertical.show()
            else:
                self._cursor_vertical.hide()
        return True

    def _create_cursor_lines(self) -> None:
        pen = pg.mkPen((90, 90, 90, 170), width=1, style=Qt.PenStyle.DashLine)
        self._cursor_horizontal = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        self._cursor_vertical = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._cursor_horizontal.setZValue(30)
        self._cursor_vertical.setZValue(30)
        self._plot.addItem(self._cursor_horizontal)
        self._plot.addItem(self._cursor_vertical)
        self._cursor_horizontal.hide()
        self._cursor_vertical.hide()

    def _hide_cursor(self) -> None:
        self._last_cursor_depth = None
        self._last_cursor_value = None
        if self._cursor_horizontal is not None:
            self._cursor_horizontal.hide()
        if self._cursor_vertical is not None:
            self._cursor_vertical.hide()
        self._cursor_label.setText(self._t("curve.cursor_empty"))

    def _publish_region_selection(self) -> None:
        if (
            self._applying_shared_selection
            or self._dataset is None
            or self._selection_region is None
        ):
            return
        top, bottom = sorted(float(value) for value in self._selection_region.getRegion())
        try:
            self.selection.select(self._dataset, top, bottom, self._displayed_curve_ids)
        except ValueError:
            return

    def _apply_shared_selection(self) -> None:
        if self._dataset is None or self._selection_region is None:
            return
        interval = self.selection.interval
        if interval is None or self.selection.dataset_id != self._dataset.dataset_id:
            self._selection_region.hide()
            return
        self._applying_shared_selection = True
        try:
            self._selection_region.setRegion(interval)
            self._selection_region.show()
        finally:
            self._applying_shared_selection = False

    def commit_draw_points(self, points: list[DrawPoint]) -> bool:
        if not self._edit_mode or self._dataset is None or self._editable_curve is None:
            return False
        unique_by_depth = {point.depth: point for point in points}
        normalized_points = list(unique_by_depth.values())
        if len(normalized_points) < 2:
            return False
        top = min(point.depth for point in normalized_points)
        bottom = max(point.depth for point in normalized_points)
        depth = np.asarray(self._dataset.depth, dtype=np.float64)
        indices = np.flatnonzero(np.isfinite(depth) & (depth >= top) & (depth <= bottom))
        if indices.size == 0:
            return False
        try:
            new_values = interpolate_drawn_curve(depth[indices], normalized_points)
        except ValueError:
            return False
        self.edit_requested.emit(self._editable_curve.metadata.curve_id, indices, new_values)
        return True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is not self._plot.viewport():
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.Leave:
            self._hide_cursor()
            return super().eventFilter(watched, event)
        if not isinstance(event, QMouseEvent):
            return super().eventFilter(watched, event)
        if not self._edit_mode:
            if event.type() == QEvent.Type.MouseMove:
                position = self._view_position(event)
                self.show_cursor_at_depth(float(position.y()), float(position.x()))
            return super().eventFilter(watched, event)
        event_type = event.type()
        if (
            event_type == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._draw_points = [self._draw_point(event)]
            self._update_edit_preview()
            return True
        if event_type == QEvent.Type.MouseMove and self._draw_points:
            self._draw_points.append(self._draw_point(event))
            self._update_edit_preview()
            return True
        if (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._draw_points
        ):
            self._draw_points.append(self._draw_point(event))
            points = self._draw_points
            self._draw_points = []
            self._clear_edit_preview()
            self.commit_draw_points(points)
            return True
        return True

    def _draw_point(self, event: QMouseEvent) -> DrawPoint:
        view_position = self._view_position(event)
        return DrawPoint(depth=float(view_position.y()), value=float(view_position.x()))

    def _view_position(self, event: QMouseEvent):
        local_position = self._plot.mapFromGlobal(event.globalPosition().toPoint())
        scene_position = self._plot.mapToScene(local_position)
        return self._plot.getViewBox().mapSceneToView(scene_position)
