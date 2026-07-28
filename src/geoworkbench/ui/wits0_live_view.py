from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.acquisition_live_view import (
    AcquisitionLiveAxisMode,
    AcquisitionLiveMarkerKind,
    AcquisitionLiveQuality,
    AcquisitionLiveSnapshot,
    AcquisitionLiveView,
    AcquisitionLiveViewConfig,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.acquisition.wits0_reliability import Wits0WorkspaceState

if TYPE_CHECKING:
    from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime


class _LiveAxisItem(pg.AxisItem):
    """Bottom axis that can switch between UTC timestamps and numeric depth."""

    def __init__(self) -> None:
        super().__init__(orientation="bottom")
        self._datetime_mode = False

    def set_datetime_mode(self, enabled: bool) -> None:
        self._datetime_mode = bool(enabled)
        self.picture = None
        self.update()

    def tickStrings(  # noqa: N802 - pyqtgraph virtual method
        self,
        values: list[float],
        scale: float,
        spacing: float,
    ) -> list[str]:
        if not self._datetime_mode:
            return [f"{value:g}" for value in values]
        labels: list[str] = []
        for value in values:
            try:
                timestamp = datetime.fromtimestamp(float(value), tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                labels.append("")
                continue
            if spacing >= 86_400:
                labels.append(timestamp.strftime("%d.%m.%Y"))
            elif spacing >= 60:
                labels.append(timestamp.strftime("%H:%M"))
            else:
                labels.append(timestamp.strftime("%H:%M:%S"))
        return labels


class Wits0LiveViewWidget(QWidget):
    """Read-only current-values and live/history chart for a growing WITS0 Dataset.

    The widget owns only presentation state. Pausing freezes the
    :class:`AcquisitionLiveView` row boundary while the acquisition runtime continues
    to append records in the background.
    """

    _DEFAULT_CURVE_PRIORITY = (
        "HOLE_DEPTH",
        "BIT_DEPTH",
        "ROP",
        "WOB",
        "RPM",
        "TORQUE",
        "SPP",
        "FLOW_IN",
        "FLOW_OUT",
        "PIT_VOLUME",
        "TOTAL_GAS",
        "C1",
        "C2",
        "C3",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "CO2",
        "H2S",
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self._runtime: Wits0AcquisitionRuntime | None = None
        self._view: AcquisitionLiveView | None = None
        self._last_revision: tuple[int, int, bool, bool, str] | None = None
        self._updating_controls = False
        self._updating_plot_range = False

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_plot_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([330, 650])
        root.addWidget(splitter, 1)

        self._set_empty_state()

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel(self._t("wits0_live.axis"), self))
        self.axis_combo = QComboBox(self)
        self.axis_combo.currentIndexChanged.connect(self._axis_changed)
        layout.addWidget(self.axis_combo)

        self.auto_follow_check = QCheckBox(self._t("wits0_live.auto_follow"), self)
        self.auto_follow_check.setChecked(True)
        self.auto_follow_check.toggled.connect(self._auto_follow_changed)
        layout.addWidget(self.auto_follow_check)

        self.pause_button = QPushButton(self._t("wits0_live.pause_view"), self)
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self._pause_changed)
        layout.addWidget(self.pause_button)

        layout.addWidget(QLabel(self._t("wits0_live.window"), self))
        self.window_spin = QDoubleSpinBox(self)
        self.window_spin.setDecimals(1)
        self.window_spin.setRange(0.1, 86_400.0)
        self.window_spin.setValue(600.0)
        self.window_spin.setSuffix(self._t("wits0_live.seconds_suffix"))
        self.window_spin.valueChanged.connect(self._follow_span_changed)
        layout.addWidget(self.window_spin)

        layout.addWidget(QLabel(self._t("wits0_live.max_points"), self))
        self.max_points_spin = QSpinBox(self)
        self.max_points_spin.setRange(100, 20_000)
        self.max_points_spin.setSingleStep(100)
        self.max_points_spin.setValue(2_000)
        self.max_points_spin.valueChanged.connect(self.refresh)
        layout.addWidget(self.max_points_spin)

        self.refresh_button = QPushButton(self._t("wits0_live.refresh"), self)
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        layout.addStretch(1)
        return layout

    def _build_left_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 6, 0)

        curve_group = QGroupBox(self._t("wits0_live.curves"), panel)
        curve_layout = QVBoxLayout(curve_group)
        self.curve_list = QListWidget(curve_group)
        self.curve_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.curve_list.itemChanged.connect(self._curve_selection_changed)
        curve_layout.addWidget(self.curve_list)
        layout.addWidget(curve_group, 2)

        values_group = QGroupBox(self._t("wits0_live.current_values"), panel)
        values_layout = QVBoxLayout(values_group)
        self.values_table = QTableWidget(0, 4, values_group)
        self.values_table.setHorizontalHeaderLabels(
            (
                self._t("wits0_live.channel"),
                self._t("wits0_live.value"),
                self._t("wits0_live.unit"),
                self._t("wits0_live.quality"),
            )
        )
        self.values_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.values_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.values_table.verticalHeader().setVisible(False)
        self.values_table.horizontalHeader().setStretchLastSection(True)
        self.values_table.setAlternatingRowColors(True)
        values_layout.addWidget(self.values_table)
        layout.addWidget(values_group, 3)
        return panel

    def _build_plot_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.state_label = QLabel(self._t("wits0_live.no_session"), panel)
        self.state_label.setWordWrap(True)
        layout.addWidget(self.state_label)

        self.axis_item = _LiveAxisItem()
        self.plot = pg.PlotWidget(axisItems={"bottom": self.axis_item}, parent=panel)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("left", self._t("wits0_live.measured_value"))
        self.plot.setLabel("bottom", self._t("wits0_live.index"))
        self.legend = self.plot.addLegend(offset=(8, 8))
        self.plot.getPlotItem().sigXRangeChanged.connect(self._plot_range_changed)
        layout.addWidget(self.plot, 1)

        self.summary_label = QLabel("", panel)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        return panel

    def bind_runtime(self, runtime: Wits0AcquisitionRuntime | None) -> None:
        if runtime is None:
            self.clear_runtime()
            return
        if self._runtime is runtime and self._view is not None:
            self.refresh()
            return
        self._runtime = runtime
        self._view = AcquisitionLiveView(
            runtime.controller.dataset,
            runtime.session,
            config=AcquisitionLiveViewConfig(
                max_points_per_curve=self.max_points_spin.value(),
                time_window_seconds=600.0,
                depth_window=100.0,
                axis_gap_factor=5.0,
                stale_after_seconds=10.0,
                max_markers=500,
            ),
        )
        self._last_revision = None
        for widget in (
            self.axis_combo,
            self.auto_follow_check,
            self.pause_button,
            self.window_spin,
            self.max_points_spin,
            self.refresh_button,
            self.curve_list,
        ):
            widget.setEnabled(True)
        self._populate_axes()
        self._populate_curves()
        self.refresh(force=True)

    def workspace_state(self) -> Wits0WorkspaceState:
        view = self._view
        history = view.history_window if view is not None else None
        axis_mode = (
            view.axis_mode.value
            if view is not None
            else str(self.axis_combo.currentData() or "auto")
        )
        return Wits0WorkspaceState(
            axis_mode=axis_mode,
            auto_follow=(view.auto_follow if view is not None else self.auto_follow_check.isChecked()),
            paused=(view.paused if view is not None else self.pause_button.isChecked()),
            follow_span=float(self.window_spin.value()),
            max_points=int(self.max_points_spin.value()),
            selected_curve_ids=self._selected_curve_ids(),
            history_start=history[0] if history is not None else None,
            history_end=history[1] if history is not None else None,
            acquisition_session_id=(
                self._runtime.session.session_id if self._runtime is not None else None
            ),
        )

    def apply_workspace_state(self, state: Wits0WorkspaceState) -> None:
        if not isinstance(state, Wits0WorkspaceState):
            raise TypeError("state must use Wits0WorkspaceState")
        view = self._view
        self._updating_controls = True
        try:
            self.max_points_spin.setValue(state.max_points)
            axis_index = self.axis_combo.findData(state.axis_mode)
            if axis_index >= 0:
                self.axis_combo.setCurrentIndex(axis_index)
            self.auto_follow_check.setChecked(state.auto_follow)
            self.window_spin.setValue(state.follow_span)
            selected = set(state.selected_curve_ids)
            if selected:
                for row in range(self.curve_list.count()):
                    item = self.curve_list.item(row)
                    curve_id = item.data(Qt.ItemDataRole.UserRole)
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if curve_id in selected
                        else Qt.CheckState.Unchecked
                    )
            self.pause_button.setChecked(state.paused)
        finally:
            self._updating_controls = False
        if view is not None:
            try:
                view.set_axis_mode(AcquisitionLiveAxisMode(state.axis_mode))
            except ValueError:
                view.set_axis_mode(AcquisitionLiveAxisMode.AUTO)
            view.set_selected_curves(self._selected_curve_ids())
            view.set_follow_span(state.follow_span)
            view.set_auto_follow(state.auto_follow)
            if not state.auto_follow and state.history_start is not None and state.history_end is not None:
                view.set_history_window(state.history_start, state.history_end)
            if state.paused:
                view.pause()
                self.pause_button.setText(self._t("wits0_live.resume_view"))
            else:
                view.resume()
                self.pause_button.setText(self._t("wits0_live.pause_view"))
        self._last_revision = None
        self._update_span_controls()
        self.refresh(force=True)

    def clear_runtime(self) -> None:
        self._runtime = None
        self._view = None
        self._last_revision = None
        self.curve_list.clear()
        self.values_table.setRowCount(0)
        self.plot.clear()
        self.legend.clear()
        self._set_empty_state()

    def refresh(self, _value: object = None, *, force: bool = False) -> None:
        view = self._view
        if view is None:
            self._set_empty_state()
            return
        selected = self._selected_curve_ids()
        view.set_selected_curves(selected)
        try:
            snapshot = view.snapshot(
                max_points_per_curve=self.max_points_spin.value(),
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            self.state_label.setText(self._t("wits0_live.error", error=str(exc)))
            return
        if not force and snapshot.revision == self._last_revision:
            self._render_current_values(snapshot)
            return
        self._last_revision = snapshot.revision
        self._render_snapshot(snapshot)

    def _populate_axes(self) -> None:
        view = self._view
        if view is None:
            return
        available = set(view.available_axis_modes())
        self._updating_controls = True
        try:
            self.axis_combo.clear()
            self.axis_combo.addItem(
                self._t("wits0_live.axis_auto"),
                AcquisitionLiveAxisMode.AUTO.value,
            )
            if AcquisitionLiveAxisMode.TIME in available:
                self.axis_combo.addItem(
                    self._t("wits0_live.axis_time"),
                    AcquisitionLiveAxisMode.TIME.value,
                )
            if AcquisitionLiveAxisMode.DEPTH in available:
                self.axis_combo.addItem(
                    self._t("wits0_live.axis_depth"),
                    AcquisitionLiveAxisMode.DEPTH.value,
                )
            self.axis_combo.setCurrentIndex(0)
        finally:
            self._updating_controls = False
        self._update_span_controls()

    def _populate_curves(self) -> None:
        view = self._view
        if view is None:
            return
        curves = list(view.dataset.curves.values())
        priority = {
            mnemonic: index
            for index, mnemonic in enumerate(self._DEFAULT_CURVE_PRIORITY)
        }
        curves.sort(
            key=lambda curve: (
                priority.get(
                    (
                        curve.metadata.canonical_mnemonic
                        or curve.metadata.original_mnemonic
                    ).upper(),
                    len(priority),
                ),
                (
                    curve.metadata.canonical_mnemonic
                    or curve.metadata.original_mnemonic
                ).casefold(),
            )
        )
        self._updating_controls = True
        try:
            self.curve_list.clear()
            for index, curve in enumerate(curves):
                metadata = curve.metadata
                mnemonic = metadata.canonical_mnemonic or metadata.original_mnemonic
                unit = (metadata.unit or "").strip()
                label = f"{mnemonic} [{unit}]" if unit else mnemonic
                item = QListWidgetItem(label, self.curve_list)
                item.setData(Qt.ItemDataRole.UserRole, metadata.curve_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if index < min(6, len(curves))
                    else Qt.CheckState.Unchecked
                )
                item.setToolTip(metadata.description or metadata.provenance or "")
        finally:
            self._updating_controls = False

    def _selected_curve_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for row in range(self.curve_list.count()):
            item = self.curve_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                curve_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(curve_id, str):
                    selected.append(curve_id)
        return tuple(selected)

    def _axis_changed(self, _index: int) -> None:
        if self._updating_controls or self._view is None:
            return
        raw_mode = self.axis_combo.currentData()
        try:
            self._view.set_axis_mode(AcquisitionLiveAxisMode(str(raw_mode)))
        except ValueError as exc:
            self.state_label.setText(self._t("wits0_live.error", error=str(exc)))
            return
        self._last_revision = None
        self._update_span_controls()
        self.refresh(force=True)

    def _update_span_controls(self) -> None:
        view = self._view
        if view is None:
            return
        try:
            snapshot = view.snapshot(curve_ids=(), max_points_per_curve=100)
        except (RuntimeError, ValueError):
            return
        self._updating_controls = True
        try:
            if snapshot.axis_mode is AcquisitionLiveAxisMode.TIME:
                self.window_spin.setRange(0.1, 86_400.0)
                self.window_spin.setSuffix(self._t("wits0_live.seconds_suffix"))
                self.window_spin.setValue(view.config.time_window_seconds)
            else:
                self.window_spin.setRange(0.1, 100_000.0)
                self.window_spin.setSuffix(self._t("wits0_live.metres_suffix"))
                self.window_spin.setValue(view.config.depth_window)
        finally:
            self._updating_controls = False

    def _auto_follow_changed(self, enabled: bool) -> None:
        if self._updating_controls or self._view is None:
            return
        self._view.set_auto_follow(enabled)
        self._last_revision = None
        self.refresh(force=True)

    def _pause_changed(self, paused: bool) -> None:
        view = self._view
        if view is None:
            return
        if paused:
            view.pause()
            self.pause_button.setText(self._t("wits0_live.resume_view"))
        else:
            view.resume()
            self.pause_button.setText(self._t("wits0_live.pause_view"))
        self._last_revision = None
        self.refresh(force=True)

    def _follow_span_changed(self, value: float) -> None:
        if self._updating_controls or self._view is None:
            return
        try:
            self._view.set_follow_span(value)
        except ValueError as exc:
            self.state_label.setText(self._t("wits0_live.error", error=str(exc)))
            return
        self._last_revision = None
        self.refresh(force=True)

    def _curve_selection_changed(self, _item: QListWidgetItem) -> None:
        if self._updating_controls:
            return
        self._last_revision = None
        self.refresh(force=True)

    def _plot_range_changed(
        self,
        _plot_item: object,
        ranges: tuple[tuple[float, float], tuple[float, float]],
    ) -> None:
        view = self._view
        if (
            view is None
            or view.auto_follow
            or self._updating_plot_range
            or not ranges
        ):
            return
        x_range = ranges[0]
        if len(x_range) != 2:
            return
        try:
            view.set_history_window(float(x_range[0]), float(x_range[1]))
        except ValueError:
            return
        self._last_revision = None
        self.refresh(force=True)

    def _render_snapshot(self, snapshot: AcquisitionLiveSnapshot) -> None:
        self.axis_item.set_datetime_mode(snapshot.axis_is_datetime)
        axis_unit = snapshot.index_unit or ""
        bottom_label = snapshot.index_mnemonic
        if snapshot.axis_is_datetime:
            bottom_label = self._t("wits0_live.time_utc")
        self.plot.setLabel("bottom", bottom_label, units=axis_unit or None)

        self.plot.clear()
        self.legend.clear()
        for index, series in enumerate(snapshot.series):
            x = np.asarray(series.axis_values, dtype=np.float64)
            y = np.asarray(series.values, dtype=np.float64)
            unit = f" [{series.unit}]" if series.unit else ""
            self.plot.plot(
                x,
                y,
                pen=pg.mkPen(pg.intColor(index, hues=max(1, len(snapshot.series))), width=1.7),
                name=f"{series.mnemonic}{unit}",
                connect="finite",
                skipFiniteCheck=False,
            )
        self._render_markers(snapshot)

        if snapshot.window_start is not None and snapshot.window_end is not None:
            self._updating_plot_range = True
            try:
                self.plot.setXRange(
                    snapshot.window_start,
                    snapshot.window_end,
                    padding=0.01,
                )
            finally:
                self._updating_plot_range = False
        if snapshot.series:
            self.plot.enableAutoRange(axis="y", enable=True)

        self._render_current_values(snapshot)
        self.auto_follow_check.blockSignals(True)
        self.auto_follow_check.setChecked(snapshot.auto_follow)
        self.auto_follow_check.blockSignals(False)
        self.pause_button.blockSignals(True)
        self.pause_button.setChecked(snapshot.paused)
        self.pause_button.setText(
            self._t("wits0_live.resume_view")
            if snapshot.paused
            else self._t("wits0_live.pause_view")
        )
        self.pause_button.blockSignals(False)

        state = (
            self._t("wits0_live.state_paused")
            if snapshot.paused
            else self._t("wits0_live.state_live")
        )
        self.state_label.setText(
            self._t(
                "wits0_live.state_summary",
                state=state,
                dataset=snapshot.dataset_id,
                rows=snapshot.total_row_count,
                visible=snapshot.visible_row_count,
            )
        )
        self.summary_label.setText(
            self._t(
                "wits0_live.render_summary",
                source=snapshot.source_point_count,
                rendered=snapshot.rendered_point_count,
                markers=len(snapshot.markers),
            )
        )

    def _render_current_values(self, snapshot: AcquisitionLiveSnapshot) -> None:
        values = snapshot.current_values
        self.values_table.setRowCount(len(values))
        for row, item in enumerate(values):
            display_value = "—" if item.value is None else f"{item.value:.8g}"
            cells = (
                item.mnemonic,
                display_value,
                item.unit or "",
                self._t(f"wits0_live.quality_{item.quality.value}"),
            )
            tooltip = ", ".join(item.quality_codes)
            foreground = _quality_color(item.quality)
            for column, value in enumerate(cells):
                cell = QTableWidgetItem(value)
                cell.setToolTip(tooltip)
                if foreground is not None:
                    cell.setForeground(QBrush(foreground))
                self.values_table.setItem(row, column, cell)
        self.values_table.resizeColumnsToContents()

    def _render_markers(self, snapshot: AcquisitionLiveSnapshot) -> None:
        for marker in snapshot.markers:
            if marker.kind is AcquisitionLiveMarkerKind.MISSING_SPAN:
                end = marker.axis_end if marker.axis_end is not None else marker.axis_start
                if end > marker.axis_start:
                    region = pg.LinearRegionItem(
                        values=(marker.axis_start, end),
                        movable=False,
                        brush=pg.mkBrush(148, 163, 184, 35),
                        pen=pg.mkPen(148, 163, 184, 90),
                    )
                    region.setZValue(-10)
                    self.plot.addItem(region)
                    continue
            pen = _marker_pen(marker.kind)
            line = pg.InfiniteLine(
                pos=marker.axis_start,
                angle=90,
                movable=False,
                pen=pen,
            )
            line.setToolTip(marker.label)
            line.setZValue(20)
            self.plot.addItem(line)

    def _set_empty_state(self) -> None:
        self.state_label.setText(self._t("wits0_live.no_session"))
        self.summary_label.setText(self._t("wits0_live.no_data"))
        for widget in (
            self.axis_combo,
            self.auto_follow_check,
            self.pause_button,
            self.window_spin,
            self.max_points_spin,
            self.refresh_button,
            self.curve_list,
        ):
            widget.setEnabled(self._view is not None)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)


def _quality_color(quality: AcquisitionLiveQuality) -> QColor | None:
    return {
        AcquisitionLiveQuality.GOOD: QColor("#15803d"),
        AcquisitionLiveQuality.MISSING: QColor("#64748b"),
        AcquisitionLiveQuality.INVALID: QColor("#dc2626"),
        AcquisitionLiveQuality.SOURCE_GAP: QColor("#d97706"),
        AcquisitionLiveQuality.STALE: QColor("#7c3aed"),
    }.get(quality)


def _marker_pen(kind: AcquisitionLiveMarkerKind) -> pg.QtGui.QPen:
    color, style = {
        AcquisitionLiveMarkerKind.SOURCE_SEQUENCE_GAP: (
            "#f59e0b",
            Qt.PenStyle.DashLine,
        ),
        AcquisitionLiveMarkerKind.AXIS_GAP: ("#ef4444", Qt.PenStyle.DashDotLine),
        AcquisitionLiveMarkerKind.INVALID_VALUE: ("#dc2626", Qt.PenStyle.DotLine),
        AcquisitionLiveMarkerKind.MISSING_SPAN: ("#94a3b8", Qt.PenStyle.DotLine),
    }[kind]
    return pg.mkPen(color, width=1.4, style=style)
