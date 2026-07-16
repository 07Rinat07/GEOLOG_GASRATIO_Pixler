from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.curve_editing import DrawPoint, interpolate_drawn_curve
from geoworkbench.services.dataset_selection import DatasetIntervalSelection


class CurveView(QWidget):
    edit_requested = Signal(str, object, object)

    def __init__(self, selection: DatasetIntervalSelection | None = None) -> None:
        super().__init__()
        self.selection = selection or DatasetIntervalSelection()
        self.selection.changed.connect(self._apply_shared_selection)
        self._dataset: Dataset | None = None
        self._editable_curve: CurveData | None = None
        self._edit_mode = False
        self._draw_points: list[DrawPoint] = []
        self._displayed_curve_ids: tuple[str, ...] = ()
        self._selection_region: pg.LinearRegionItem | None = None
        self._applying_shared_selection = False
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("left", "Глубина", units="м")
        self._plot.setLabel("bottom", "Значение")
        self._plot.viewport().installEventFilter(self)
        self._plot.viewport().setMouseTracking(True)
        self._title = QLabel("Откройте LAS-файл")
        self._title.setStyleSheet("font-weight: 600; padding: 6px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(self._plot)

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def can_edit(self) -> bool:
        return self._dataset is not None and self._editable_curve is not None

    def clear(self) -> None:
        self._dataset = None
        self._editable_curve = None
        self._draw_points.clear()
        self._displayed_curve_ids = ()
        self._plot.clear()
        self._selection_region = None
        self._title.setText("Откройте LAS-файл")

    def set_edit_mode(self, enabled: bool) -> bool:
        self._edit_mode = enabled and self.can_edit
        cursor = Qt.CursorShape.CrossCursor if self._edit_mode else Qt.CursorShape.ArrowCursor
        self._plot.viewport().setCursor(cursor)
        return self._edit_mode

    def show_dataset(self, dataset: Dataset, selected: list[str] | None = None) -> None:
        self._dataset = dataset
        self._editable_curve = None
        self._draw_points.clear()
        self._displayed_curve_ids = ()
        self._plot.clear()
        self._selection_region = None
        selected_names = selected or [
            curve.metadata.original_mnemonic for curve in list(dataset.curves.values())[:6]
        ]
        if len(selected_names) == 1:
            self._editable_curve = dataset.curve_by_mnemonic(selected_names[0])
        count = 0
        displayed_curve_ids: list[str] = []
        for curve in dataset.curves.values():
            mnemonic = curve.metadata.original_mnemonic
            if mnemonic not in selected_names:
                continue
            values = np.asarray(curve.values, dtype=float)
            valid = np.isfinite(values) & np.isfinite(dataset.depth)
            if not np.any(valid):
                continue
            self._plot.plot(values[valid], dataset.depth[valid], name=mnemonic)
            count += 1
            displayed_curve_ids.append(curve.metadata.curve_id)
        self._displayed_curve_ids = tuple(displayed_curve_ids)
        self._plot.getViewBox().invertY(True)
        finite_depth = dataset.depth[np.isfinite(dataset.depth)]
        if finite_depth.size:
            self._selection_region = pg.LinearRegionItem(
                values=(float(np.min(finite_depth)), float(np.max(finite_depth))),
                orientation=pg.LinearRegionItem.Horizontal,
                movable=True,
                brush=pg.mkBrush(70, 130, 180, 35),
            )
            self._selection_region.setZValue(20)
            self._selection_region.sigRegionChangeFinished.connect(
                self._publish_region_selection
            )
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
            f"{dataset.name}: показано кривых — {count}, отсчётов — {len(dataset.depth)}"
        )
        if self._edit_mode and not self.can_edit:
            self.set_edit_mode(False)

    def _publish_region_selection(self) -> None:
        if (
            self._applying_shared_selection
            or self._dataset is None
            or self._selection_region is None
        ):
            return
        top, bottom = sorted(float(value) for value in self._selection_region.getRegion())
        try:
            self.selection.select(
                self._dataset, top, bottom, self._displayed_curve_ids
            )
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
        if watched is not self._plot.viewport() or not isinstance(event, QMouseEvent):
            return super().eventFilter(watched, event)
        if not self._edit_mode:
            return super().eventFilter(watched, event)
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._draw_points = [self._draw_point(event)]
            return True
        if event_type == QEvent.Type.MouseMove and self._draw_points:
            self._draw_points.append(self._draw_point(event))
            return True
        if (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._draw_points
        ):
            self._draw_points.append(self._draw_point(event))
            points = self._draw_points
            self._draw_points = []
            self.commit_draw_points(points)
            return True
        return True

    def _draw_point(self, event: QMouseEvent) -> DrawPoint:
        local_position = self._plot.mapFromGlobal(event.globalPosition().toPoint())
        scene_position = self._plot.mapToScene(local_position)
        view_position = self._plot.getViewBox().mapSceneToView(scene_position)
        return DrawPoint(depth=float(view_position.y()), value=float(view_position.x()))
