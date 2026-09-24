from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.acquisition.wits0_live_forms import (
    Wits0LivePanelDefinition,
    live_panel_definitions,
    live_panel_key,
)
from geoworkbench.services.acquisition_live_view import (
    AcquisitionCurrentValue,
    AcquisitionLiveMarkerKind,
    AcquisitionLiveQuality,
    AcquisitionLiveSeries,
    AcquisitionLiveSnapshot,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.grid_geometry import DEFAULT_GRID_ALPHA


class _DashboardAxisItem(pg.AxisItem):
    def __init__(self) -> None:
        super().__init__(orientation="left")
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


class _IndicatorCard(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(145)
        self.setMaximumWidth(220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)

        self.name_label = QLabel("—", self)
        self.name_label.setWordWrap(False)
        layout.addWidget(self.name_label)

        self.value_label = QLabel("—", self)
        font = QFont(self.value_label.font())
        font.setPointSize(max(14, font.pointSize() + 5))
        font.setBold(True)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)

        self.detail_label = QLabel("", self)
        self.detail_label.setWordWrap(False)
        layout.addWidget(self.detail_label)

    def update_value(
        self,
        value: AcquisitionCurrentValue,
        *,
        quality_text: str,
    ) -> None:
        self.name_label.setText(value.mnemonic)
        display = "—" if value.value is None else f"{value.value:.8g}"
        self.value_label.setText(display)
        unit = value.unit or ""
        self.detail_label.setText(
            f"{unit} · {quality_text}" if unit else quality_text
        )
        color = _quality_color(value.quality)
        self.value_label.setStyleSheet(
            f"color: {color.name()};" if color is not None else ""
        )
        tooltip = ", ".join(value.quality_codes)
        self.setToolTip(tooltip)


class _PlotPanel:
    def __init__(
        self,
        definition: Wits0LivePanelDefinition,
        *,
        language: AppLanguage,
        parent: QWidget,
    ) -> None:
        self.definition = definition
        self.box = QGroupBox(definition.title(language), parent)
        self.box.setMinimumWidth(260)
        self.box.setMinimumHeight(460)
        layout = QVBoxLayout(self.box)
        layout.setContentsMargins(4, 4, 4, 4)

        self.axis_item = _DashboardAxisItem()
        self.plot = pg.PlotWidget(
            axisItems={"left": self.axis_item},
            parent=self.box,
        )
        self.plot.getViewBox().invertY(True)
        self.plot.showGrid(x=True, y=True, alpha=DEFAULT_GRID_ALPHA)
        self.legend = self.plot.addLegend(offset=(6, 6))
        layout.addWidget(self.plot)
        self.box.hide()


class Wits0OperatorDashboard(QWidget):
    """Operator-oriented WITS dashboard with independent engineering scales."""

    historyRangeChanged = Signal(float, float)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self._language = language
        self._localizer = Localizer.create(language)
        self._updating_range = False
        self._indicator_cards: dict[str, _IndicatorCard] = {}
        self._unit_panels: dict[tuple[str, str], _PlotPanel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self.indicator_scroll = QScrollArea(self)
        self.indicator_scroll.setWidgetResizable(True)
        self.indicator_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.indicator_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.indicator_host = QWidget(self.indicator_scroll)
        self.indicator_layout = QHBoxLayout(self.indicator_host)
        self.indicator_layout.setContentsMargins(2, 2, 2, 2)
        self.indicator_layout.setSpacing(4)
        self.indicator_layout.addStretch(1)
        self.indicator_scroll.setWidget(self.indicator_host)
        self.indicator_scroll.setMinimumHeight(105)
        self.indicator_scroll.setMaximumHeight(125)
        root.addWidget(self.indicator_scroll)

        self.plot_scroll = QScrollArea(self)
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.plot_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.plot_host = QWidget(self.plot_scroll)
        self.plot_layout = QHBoxLayout(self.plot_host)
        self.plot_layout.setContentsMargins(2, 2, 2, 2)
        self.plot_layout.setSpacing(6)

        self.panels: dict[str, _PlotPanel] = {}
        for definition in live_panel_definitions():
            panel = _PlotPanel(
                definition,
                language=self._language,
                parent=self.plot_host,
            )
            panel.plot.getPlotItem().sigYRangeChanged.connect(
                self._plot_range_changed
            )
            self.panels[definition.panel_id] = panel
            self.plot_layout.addWidget(panel.box)

        self.other_panel = _PlotPanel(
            Wits0LivePanelDefinition(
                "other",
                "Прочие каналы",
                "Басқа арналар",
                "Other channels",
                (),
            ),
            language=self._language,
            parent=self.plot_host,
        )
        self.other_panel.plot.getPlotItem().sigYRangeChanged.connect(
            self._plot_range_changed
        )
        self.plot_layout.addWidget(self.other_panel.box)
        self.panels["other"] = self.other_panel

        self.plot_scroll.setWidget(self.plot_host)
        root.addWidget(self.plot_scroll, 1)

    def clear(self) -> None:
        self._clear_indicator_cards()
        self._clear_unit_panels()
        for panel in self.panels.values():
            panel.plot.clear()
            panel.legend.clear()
            panel.box.hide()

    def render_snapshot(self, snapshot: AcquisitionLiveSnapshot) -> None:
        self.render_current_values(snapshot.current_values)
        grouped: dict[str, list[AcquisitionLiveSeries]] = {
            panel_id: []
            for panel_id in self.panels
        }
        for series in snapshot.series:
            panel_id = live_panel_key(series.mnemonic) or "other"
            grouped.setdefault(panel_id, []).append(series)

        unit_groups = {
            panel_id: _group_series_by_unit(series_list)
            for panel_id, series_list in grouped.items()
            if series_list
        }
        self._sync_unit_panels(unit_groups)

        history_label = snapshot.index_mnemonic
        history_unit = snapshot.index_unit or ""
        if snapshot.axis_is_datetime:
            history_label = self._localizer.text("wits0_live.time_utc")

        render_targets: list[tuple[_PlotPanel, list[AcquisitionLiveSeries]]] = []
        for panel_id, panel in self.panels.items():
            groups = unit_groups.get(panel_id, [])
            if not groups:
                panel.plot.clear()
                panel.legend.clear()
                panel.box.hide()
                continue
            primary_unit, primary_series = groups[0]
            panel.box.setTitle(_panel_title(panel.definition, self._language, primary_unit, len(groups)))
            render_targets.append((panel, primary_series))
            for unit_key, series_list in groups[1:]:
                extra = self._unit_panels[(panel_id, unit_key)]
                render_targets.append((extra, series_list))

        for panel, series_list in render_targets:
            panel.plot.clear()
            panel.legend.clear()
            panel.box.show()
            panel.axis_item.set_datetime_mode(snapshot.axis_is_datetime)
            panel.plot.setLabel(
                "left",
                history_label,
                units=history_unit or None,
            )
            panel.plot.setLabel("bottom", _panel_axis_label(series_list))

            for index, series in enumerate(series_list):
                x = np.asarray(series.values, dtype=np.float64)
                y = np.asarray(series.axis_values, dtype=np.float64)
                unit = f" [{series.unit}]" if series.unit else ""
                panel.plot.plot(
                    x,
                    y,
                    pen=pg.mkPen(
                        pg.intColor(index, hues=max(1, len(series_list))),
                        width=1.7,
                    ),
                    name=f"{series.mnemonic}{unit}",
                    connect="finite",
                    skipFiniteCheck=False,
                )

            curve_ids = {series.curve_id for series in series_list}
            self._render_markers(panel.plot, snapshot, curve_ids)

            if snapshot.window_start is not None and snapshot.window_end is not None:
                self._updating_range = True
                try:
                    panel.plot.setYRange(
                        snapshot.window_start,
                        snapshot.window_end,
                        padding=0.01,
                    )
                finally:
                    self._updating_range = False
            panel.plot.enableAutoRange(axis="x", enable=True)

    def _sync_unit_panels(
        self,
        unit_groups: dict[str, list[tuple[str, list[AcquisitionLiveSeries]]]],
    ) -> None:
        wanted = {
            (panel_id, unit_key)
            for panel_id, groups in unit_groups.items()
            for unit_key, _series in groups[1:]
        }
        for key in tuple(self._unit_panels):
            if key in wanted:
                continue
            panel = self._unit_panels.pop(key)
            self.plot_layout.removeWidget(panel.box)
            panel.box.deleteLater()

        for panel_id, groups in unit_groups.items():
            if len(groups) <= 1:
                continue
            base_panel = self.panels[panel_id]
            base_index = self.plot_layout.indexOf(base_panel.box)
            insert_offset = 1
            for unit_key, _series in groups[1:]:
                key = (panel_id, unit_key)
                panel = self._unit_panels.get(key)
                if panel is None:
                    definition = Wits0LivePanelDefinition(
                        f"{panel_id}:{unit_key or 'unitless'}",
                        base_panel.definition.title_ru,
                        base_panel.definition.title_kk,
                        base_panel.definition.title_en,
                        base_panel.definition.channel_keys,
                    )
                    panel = _PlotPanel(
                        definition,
                        language=self._language,
                        parent=self.plot_host,
                    )
                    panel.plot.getPlotItem().sigYRangeChanged.connect(
                        self._plot_range_changed
                    )
                    self._unit_panels[key] = panel
                panel.box.setTitle(
                    _panel_title(base_panel.definition, self._language, unit_key, len(groups))
                )
                current_index = self.plot_layout.indexOf(panel.box)
                target_index = base_index + insert_offset
                if current_index != target_index:
                    if current_index >= 0:
                        self.plot_layout.removeWidget(panel.box)
                    self.plot_layout.insertWidget(target_index, panel.box)
                insert_offset += 1

    def _clear_unit_panels(self) -> None:
        for panel in self._unit_panels.values():
            self.plot_layout.removeWidget(panel.box)
            panel.box.deleteLater()
        self._unit_panels.clear()

    def render_current_values(
        self,
        values: tuple[AcquisitionCurrentValue, ...],
    ) -> None:
        curve_ids = tuple(item.curve_id for item in values)
        if tuple(self._indicator_cards) != curve_ids:
            self._rebuild_indicator_cards(values)
        for item in values:
            card = self._indicator_cards.get(item.curve_id)
            if card is None:
                continue
            card.update_value(
                item,
                quality_text=self._localizer.text(
                    f"wits0_live.quality_{item.quality.value}"
                ),
            )

    def _rebuild_indicator_cards(
        self,
        values: tuple[AcquisitionCurrentValue, ...],
    ) -> None:
        self._clear_indicator_cards()
        for item in values:
            card = _IndicatorCard(self.indicator_host)
            self._indicator_cards[item.curve_id] = card
            self.indicator_layout.insertWidget(
                max(0, self.indicator_layout.count() - 1),
                card,
            )

    def _clear_indicator_cards(self) -> None:
        for card in self._indicator_cards.values():
            self.indicator_layout.removeWidget(card)
            card.deleteLater()
        self._indicator_cards.clear()

    def _plot_range_changed(
        self,
        _plot_item: object,
        ranges: tuple[tuple[float, float], tuple[float, float]],
    ) -> None:
        if self._updating_range or len(ranges) < 2 or len(ranges[1]) != 2:
            return
        first, second = ranges[1]
        start = min(float(first), float(second))
        end = max(float(first), float(second))
        if np.isfinite(start) and np.isfinite(end) and end > start:
            self.historyRangeChanged.emit(start, end)

    @staticmethod
    def _render_markers(
        plot: pg.PlotWidget,
        snapshot: AcquisitionLiveSnapshot,
        curve_ids: set[str],
    ) -> None:
        for marker in snapshot.markers:
            if marker.curve_id is not None and marker.curve_id not in curve_ids:
                continue
            if marker.kind is AcquisitionLiveMarkerKind.MISSING_SPAN:
                end = marker.axis_end if marker.axis_end is not None else marker.axis_start
                if end > marker.axis_start:
                    region = pg.LinearRegionItem(
                        values=(marker.axis_start, end),
                        orientation="horizontal",
                        movable=False,
                        brush=pg.mkBrush(148, 163, 184, 35),
                        pen=pg.mkPen(148, 163, 184, 90),
                    )
                    region.setZValue(-10)
                    plot.addItem(region)
                    continue
            line = pg.InfiniteLine(
                pos=marker.axis_start,
                angle=0,
                movable=False,
                pen=_marker_pen(marker.kind),
            )
            line.setToolTip(marker.label)
            line.setZValue(20)
            plot.addItem(line)


def _normalized_unit(unit: str | None) -> str:
    return (unit or "").strip().casefold()


def _group_series_by_unit(
    series_list: list[AcquisitionLiveSeries],
) -> list[tuple[str, list[AcquisitionLiveSeries]]]:
    grouped: dict[str, list[AcquisitionLiveSeries]] = {}
    display_units: dict[str, str] = {}
    for series in series_list:
        key = _normalized_unit(series.unit)
        grouped.setdefault(key, []).append(series)
        if key not in display_units:
            display_units[key] = (series.unit or "").strip()
    return [
        (display_units[key], grouped[key])
        for key in grouped
    ]


def _panel_title(
    definition: Wits0LivePanelDefinition,
    language: AppLanguage,
    unit: str,
    group_count: int,
) -> str:
    title = definition.title(language)
    if group_count <= 1 or not unit:
        return title
    return f"{title} [{unit}]"


def _panel_axis_label(series_list: list[AcquisitionLiveSeries]) -> str:
    units = sorted(
        {
            (series.unit or "").strip()
            for series in series_list
            if (series.unit or "").strip()
        }
    )
    if not units:
        return "Value"
    if len(units) == 1:
        return units[0]
    return " / ".join(units)


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
        AcquisitionLiveMarkerKind.AXIS_GAP: (
            "#ef4444",
            Qt.PenStyle.DashDotLine,
        ),
        AcquisitionLiveMarkerKind.INVALID_VALUE: (
            "#dc2626",
            Qt.PenStyle.DotLine,
        ),
        AcquisitionLiveMarkerKind.MISSING_SPAN: (
            "#94a3b8",
            Qt.PenStyle.DotLine,
        ),
    }[kind]
    return pg.mkPen(color, width=1.4, style=style)
