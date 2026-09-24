from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt, Signal
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
    AcquisitionLiveQuality,
    AcquisitionLiveSnapshot,
    AcquisitionLiveView,
    AcquisitionLiveViewConfig,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.acquisition.wits0_reliability import Wits0WorkspaceState
from geoworkbench.acquisition.wits0_live_forms import (
    CUSTOM_LIVE_FORM_ID,
    UNIVERSAL_LIVE_FORM_ID,
    Wits0LiveFormSettings,
    Wits0SavedLiveFormState,
    live_curve_priority,
    live_form,
    live_form_definitions,
    select_live_curve_ids,
)
from geoworkbench.ui.wits0_operator_dashboard import Wits0OperatorDashboard

if TYPE_CHECKING:
    from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime


class Wits0LiveViewWidget(QWidget):
    """Read-only current-values and live/history chart for a growing WITS0 Dataset.

    The widget owns only presentation state. Pausing freezes the
    :class:`AcquisitionLiveView` row boundary while the acquisition runtime continues
    to append records in the background.
    """

    fullScreenRequested = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self._language = language
        self.settings = QSettings()
        self.form_settings = Wits0LiveFormSettings(self.settings)
        self._runtime: Wits0AcquisitionRuntime | None = None
        self._view: AcquisitionLiveView | None = None
        self._preview_mode = False
        self._last_revision: tuple[int, int, bool, bool, str] | None = None
        self._updating_controls = False
        self._updating_plot_range = False
        self._fullscreen = False
        self._sidebar_user_override: bool | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addLayout(self._build_toolbar())

        self.form_description_label = QLabel("", self)
        self.form_description_label.setWordWrap(True)
        root.addWidget(self.form_description_label)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.left_panel = self._build_left_panel()
        self.plot_panel = self._build_plot_panel()
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.plot_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([330, 650])
        root.addWidget(self.splitter, 1)

        self._restore_last_form()
        self._update_form_description()
        self._set_empty_state()

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel(_live_form_selector_label(self._language), self))
        self.form_combo = QComboBox(self)
        for definition in live_form_definitions():
            self.form_combo.addItem(
                definition.title(self._language),
                definition.form_id,
            )
        universal_index = self.form_combo.findData(UNIVERSAL_LIVE_FORM_ID)
        if universal_index >= 0:
            self.form_combo.setCurrentIndex(universal_index)
        self.form_combo.setMinimumWidth(210)
        self.form_combo.currentIndexChanged.connect(self._form_changed)
        layout.addWidget(self.form_combo)

        self.save_form_button = QPushButton(
            _operator_text(self._language, "save_form"),
            self,
        )
        self.save_form_button.clicked.connect(self._save_current_form)
        layout.addWidget(self.save_form_button)

        self.reset_form_button = QPushButton(
            _operator_text(self._language, "reset_form"),
            self,
        )
        self.reset_form_button.clicked.connect(self._reset_current_form)
        layout.addWidget(self.reset_form_button)

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

        self.sidebar_button = QPushButton(
            _operator_text(self._language, "hide_sidebar"),
            self,
        )
        self.sidebar_button.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_button)

        self.fullscreen_button = QPushButton(
            _operator_text(self._language, "fullscreen"),
            self,
        )
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)
        layout.addWidget(self.fullscreen_button)
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

        self.dashboard = Wits0OperatorDashboard(
            panel,
            language=self._language,
        )
        self.dashboard.historyRangeChanged.connect(
            self._dashboard_range_changed
        )
        layout.addWidget(self.dashboard, 1)

        self.summary_label = QLabel("", panel)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        return panel

    def bind_runtime(
        self,
        runtime: Wits0AcquisitionRuntime | None,
        *,
        preview: bool = False,
    ) -> None:
        if runtime is None:
            self.clear_runtime()
            return
        previous_state = (
            self.workspace_state()
            if preview and self._preview_mode and self._view is not None
            else None
        )
        previous_form_id = str(
            self.form_combo.currentData() or UNIVERSAL_LIVE_FORM_ID
        )
        self._preview_mode = preview
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
        target_form_id = previous_form_id or UNIVERSAL_LIVE_FORM_ID
        target_form_index = self.form_combo.findData(target_form_id)
        if target_form_index < 0:
            target_form_index = self.form_combo.findData(UNIVERSAL_LIVE_FORM_ID)
        if target_form_index >= 0:
            self.form_combo.blockSignals(True)
            self.form_combo.setCurrentIndex(target_form_index)
            self.form_combo.blockSignals(False)
        for widget in (
            self.form_combo,
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
        if previous_state is not None:
            self.apply_workspace_state(previous_state)
            if previous_form_id != CUSTOM_LIVE_FORM_ID:
                form_index = self.form_combo.findData(previous_form_id)
                if form_index >= 0:
                    self.form_combo.blockSignals(True)
                    self.form_combo.setCurrentIndex(form_index)
                    self.form_combo.blockSignals(False)
                    self._apply_live_form_selection()
                    self._view.set_selected_curves(self._selected_curve_ids())
                    self._last_revision = None
                    self.refresh(force=True)
        else:
            self._apply_live_form_selection()
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
                self._runtime.session.session_id
                if self._runtime is not None and not self._preview_mode
                else None
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
        self._preview_mode = False
        self._last_revision = None
        self.curve_list.clear()
        self.values_table.setRowCount(0)
        self.dashboard.clear()
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
        curves.sort(
            key=lambda curve: (
                live_curve_priority(
                    curve.metadata.canonical_mnemonic,
                    curve.metadata.original_mnemonic,
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
            for curve in curves:
                metadata = curve.metadata
                mnemonic = metadata.canonical_mnemonic or metadata.original_mnemonic
                unit = (metadata.unit or "").strip()
                label = f"{mnemonic} [{unit}]" if unit else mnemonic
                item = QListWidgetItem(label, self.curve_list)
                item.setData(Qt.ItemDataRole.UserRole, metadata.curve_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setToolTip(metadata.description or metadata.provenance or "")
        finally:
            self._updating_controls = False
        self._apply_live_form_selection()

    def _apply_live_form_selection(self, *, factory_only: bool = False) -> None:
        view = self._view
        if view is None:
            return
        form_id = str(self.form_combo.currentData() or UNIVERSAL_LIVE_FORM_ID)
        curves = tuple(
            (
                curve.metadata.curve_id,
                curve.metadata.canonical_mnemonic,
                curve.metadata.original_mnemonic,
            )
            for curve in view.dataset.curves.values()
        )
        saved = None if factory_only else self.form_settings.load(form_id)
        if saved is not None:
            selected = set(self._curve_ids_for_mnemonics(saved.selected_mnemonics))
        else:
            selected = set(select_live_curve_ids(form_id, curves))
            if not selected and form_id == UNIVERSAL_LIVE_FORM_ID:
                selected = {
                    self.curve_list.item(row).data(Qt.ItemDataRole.UserRole)
                    for row in range(min(6, self.curve_list.count()))
                }
        self._updating_controls = True
        try:
            for row in range(self.curve_list.count()):
                item = self.curve_list.item(row)
                curve_id = item.data(Qt.ItemDataRole.UserRole)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if curve_id in selected
                    else Qt.CheckState.Unchecked
                )
            if saved is not None:
                self.max_points_spin.setValue(saved.max_points)
                axis_index = self.axis_combo.findData(saved.axis_mode)
                if axis_index >= 0:
                    self.axis_combo.setCurrentIndex(axis_index)
                self.auto_follow_check.setChecked(saved.auto_follow)
                self.window_spin.setValue(saved.follow_span)
                self._sidebar_user_override = saved.sidebar_visible
                self._set_sidebar_visible(saved.sidebar_visible)
        finally:
            self._updating_controls = False
        if saved is not None:
            try:
                view.set_axis_mode(AcquisitionLiveAxisMode(saved.axis_mode))
            except ValueError:
                view.set_axis_mode(AcquisitionLiveAxisMode.AUTO)
            view.set_auto_follow(saved.auto_follow)
            view.set_follow_span(saved.follow_span)
        view.set_selected_curves(self._selected_curve_ids())

    def _selected_curve_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for row in range(self.curve_list.count()):
            item = self.curve_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                curve_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(curve_id, str):
                    selected.append(curve_id)
        return tuple(selected)

    def _form_changed(self, _index: int) -> None:
        if self._updating_controls:
            return
        form_id = str(self.form_combo.currentData() or UNIVERSAL_LIVE_FORM_ID)
        self.settings.setValue("wits0/live-form/last-selected", form_id)
        self.settings.sync()
        self._update_form_description()
        if self._view is None:
            return
        self._apply_live_form_selection()
        self._last_revision = None
        self.refresh(force=True)

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

    def _dashboard_range_changed(self, start: float, end: float) -> None:
        view = self._view
        if view is None or view.auto_follow or self._updating_plot_range:
            return
        try:
            view.set_history_window(float(start), float(end))
        except ValueError:
            return
        self._last_revision = None
        self.refresh(force=True)

    def _render_snapshot(self, snapshot: AcquisitionLiveSnapshot) -> None:
        self._updating_plot_range = True
        try:
            self.dashboard.render_snapshot(snapshot)
        finally:
            self._updating_plot_range = False

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

        if snapshot.paused:
            state = self._t("wits0_live.state_paused")
        elif self._preview_mode:
            state = self._t("wits0_live.state_preview")
        else:
            state = self._t("wits0_live.state_live")
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
        self.dashboard.render_current_values(values)
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

    def _set_empty_state(self) -> None:
        self.state_label.setText(self._t("wits0_live.no_session"))
        self.summary_label.setText(self._t("wits0_live.no_data"))
        self.form_combo.setEnabled(True)
        self.fullscreen_button.setEnabled(True)
        self.sidebar_button.setEnabled(True)
        self.reset_form_button.setEnabled(True)
        for widget in (
            self.axis_combo,
            self.auto_follow_check,
            self.pause_button,
            self.window_spin,
            self.max_points_spin,
            self.refresh_button,
            self.curve_list,
            self.save_form_button,
        ):
            widget.setEnabled(self._view is not None)

    def _restore_last_form(self) -> None:
        form_id = str(
            self.settings.value(
                "wits0/live-form/last-selected",
                UNIVERSAL_LIVE_FORM_ID,
            )
        )
        index = self.form_combo.findData(form_id)
        if index < 0:
            index = self.form_combo.findData(UNIVERSAL_LIVE_FORM_ID)
        if index >= 0:
            self.form_combo.setCurrentIndex(index)

    def _update_form_description(self) -> None:
        form_id = str(self.form_combo.currentData() or UNIVERSAL_LIVE_FORM_ID)
        try:
            definition = live_form(form_id)
        except KeyError:
            self.form_description_label.setText("")
            return
        suffix = (
            _operator_text(self._language, "saved_override")
            if self.form_settings.load(form_id) is not None
            else _operator_text(self._language, "factory_template")
        )
        description = definition.description(self._language)
        self.form_description_label.setText(
            f"{description} · {suffix}" if description else suffix
        )

    def _selected_mnemonics(self) -> tuple[str, ...]:
        view = self._view
        if view is None:
            return ()
        selected_ids = set(self._selected_curve_ids())
        result: list[str] = []
        for curve in view.dataset.curves.values():
            if curve.metadata.curve_id not in selected_ids:
                continue
            mnemonic = (
                curve.metadata.canonical_mnemonic
                or curve.metadata.original_mnemonic
            ).strip()
            if mnemonic and mnemonic not in result:
                result.append(mnemonic)
        return tuple(result)

    def _curve_ids_for_mnemonics(
        self,
        mnemonics: tuple[str, ...],
    ) -> tuple[str, ...]:
        view = self._view
        if view is None:
            return ()
        wanted = {item.casefold() for item in mnemonics}
        selected: list[str] = []
        for curve in view.dataset.curves.values():
            metadata = curve.metadata
            candidates = {
                metadata.canonical_mnemonic.casefold()
                if metadata.canonical_mnemonic
                else "",
                metadata.original_mnemonic.casefold()
                if metadata.original_mnemonic
                else "",
            }
            if wanted.intersection(candidates):
                selected.append(metadata.curve_id)
        return tuple(selected)

    def _save_current_form(self) -> None:
        view = self._view
        if view is None:
            return
        form_id = str(self.form_combo.currentData() or UNIVERSAL_LIVE_FORM_ID)
        state = Wits0SavedLiveFormState(
            form_id=form_id,
            selected_mnemonics=self._selected_mnemonics(),
            axis_mode=str(self.axis_combo.currentData() or "auto"),
            auto_follow=self.auto_follow_check.isChecked(),
            follow_span=float(self.window_spin.value()),
            max_points=int(self.max_points_spin.value()),
            sidebar_visible=self.left_panel.isVisible(),
        )
        self.form_settings.save(state)
        self._update_form_description()
        self.state_label.setText(
            _operator_text(self._language, "form_saved").format(
                form=self.form_combo.currentText()
            )
        )

    def _reset_current_form(self) -> None:
        form_id = str(self.form_combo.currentData() or UNIVERSAL_LIVE_FORM_ID)
        self.form_settings.reset(form_id)
        self._sidebar_user_override = None
        self._update_form_description()
        if self._view is not None:
            self._updating_controls = True
            try:
                self.auto_follow_check.setChecked(True)
                self.max_points_spin.setValue(2_000)
                axis_index = self.axis_combo.findData("auto")
                if axis_index >= 0:
                    self.axis_combo.setCurrentIndex(axis_index)
            finally:
                self._updating_controls = False
            self._view.set_axis_mode(AcquisitionLiveAxisMode.AUTO)
            self._view.set_auto_follow(True)
            self._apply_live_form_selection(factory_only=True)
            self._last_revision = None
            self.refresh(force=True)

    def _set_sidebar_visible(self, visible: bool) -> None:
        self.left_panel.setVisible(bool(visible))
        self.sidebar_button.setText(
            _operator_text(
                self._language,
                "hide_sidebar" if visible else "show_sidebar",
            )
        )
        if visible:
            self.splitter.setSizes([330, max(650, self.width() - 330)])

    def _toggle_sidebar(self) -> None:
        visible = not self.left_panel.isVisible()
        self._sidebar_user_override = visible
        self._set_sidebar_visible(visible)

    def _toggle_fullscreen(self) -> None:
        self.fullScreenRequested.emit(not self._fullscreen)

    def set_fullscreen_state(self, enabled: bool) -> None:
        self._fullscreen = bool(enabled)
        self.fullscreen_button.setText(
            _operator_text(
                self._language,
                "exit_fullscreen" if enabled else "fullscreen",
            )
        )

    def resizeEvent(self, event: object) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._fullscreen or self._sidebar_user_override is not None:
            return
        self._set_sidebar_visible(self.width() >= 820)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)


def _live_form_selector_label(language: AppLanguage) -> str:
    return {
        AppLanguage.RU: "Форма",
        AppLanguage.KK: "Пішін",
        AppLanguage.EN: "Form",
    }.get(language, "Form")


def _operator_text(language: AppLanguage, key: str) -> str:
    translations = {
        AppLanguage.RU: {
            "save_form": "Сохранить форму",
            "reset_form": "Сбросить",
            "hide_sidebar": "Скрыть параметры",
            "show_sidebar": "Показать параметры",
            "fullscreen": "На весь экран",
            "exit_fullscreen": "Выйти из полного экрана",
            "saved_override": "сохранённая настройка",
            "factory_template": "заводской шаблон",
            "form_saved": "Форма «{form}» сохранена.",
        },
        AppLanguage.KK: {
            "save_form": "Пішінді сақтау",
            "reset_form": "Қалпына келтіру",
            "hide_sidebar": "Параметрлерді жасыру",
            "show_sidebar": "Параметрлерді көрсету",
            "fullscreen": "Толық экран",
            "exit_fullscreen": "Толық экраннан шығу",
            "saved_override": "сақталған баптау",
            "factory_template": "зауыттық үлгі",
            "form_saved": "«{form}» пішіні сақталды.",
        },
        AppLanguage.EN: {
            "save_form": "Save form",
            "reset_form": "Reset",
            "hide_sidebar": "Hide parameters",
            "show_sidebar": "Show parameters",
            "fullscreen": "Full screen",
            "exit_fullscreen": "Exit full screen",
            "saved_override": "saved setup",
            "factory_template": "factory template",
            "form_saved": "Form “{form}” saved.",
        },
    }
    return translations.get(language, translations[AppLanguage.EN]).get(key, key)


def _quality_color(quality: AcquisitionLiveQuality) -> QColor | None:
    return {
        AcquisitionLiveQuality.GOOD: QColor("#15803d"),
        AcquisitionLiveQuality.MISSING: QColor("#64748b"),
        AcquisitionLiveQuality.INVALID: QColor("#dc2626"),
        AcquisitionLiveQuality.SOURCE_GAP: QColor("#d97706"),
        AcquisitionLiveQuality.STALE: QColor("#7c3aed"),
    }.get(quality)
