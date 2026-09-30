from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.acquisition_live_view import (
    AcquisitionLiveAxisMode,
    AcquisitionLiveHealth,
    AcquisitionLiveQuality,
    AcquisitionLiveSnapshot,
    AcquisitionLiveView,
    AcquisitionLiveViewConfig,
)
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.wits0_live_derived import (
    Wits0DexpCorrectionConfig,
    Wits0LiveDerivedChannelService,
)
from geoworkbench.acquisition.wits0_reliability import Wits0WorkspaceState
from geoworkbench.acquisition.wits0_live_alarms import (
    Wits0LiveAlarmController,
    Wits0LiveAlarmStatus,
)
from geoworkbench.acquisition.wits0_live_forms import (
    UNIVERSAL_LIVE_FORM_ID,
    Wits0LiveFormSettings,
    Wits0SavedLiveFormState,
    live_curve_priority,
    live_form,
    live_form_definitions,
    select_live_curve_ids,
)
from geoworkbench.ui.wits0_alarm_settings_editor import Wits0AlarmSettingsEditor
from geoworkbench.ui.wits0_operator_dashboard import Wits0OperatorDashboard

if TYPE_CHECKING:
    from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime


_COMPACT_NAVIGATION_BREAKPOINT = 820
_WIDE_SIDEBAR_WIDTH = 330


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
        self._derived_service = Wits0LiveDerivedChannelService()
        self._virtual_curves: dict[str, CurveData] = {}
        self._preview_mode = False
        self._last_revision: tuple[int, int, bool, bool, str] | None = None
        self._last_plot_rendered_points = 0
        self._updating_controls = False
        self._updating_plot_range = False
        self._fullscreen = False
        self._sidebar_user_override: bool | None = None
        self._compact_parameters_open = False
        self._compact_navigation_active = False
        self._alarm_controller = Wits0LiveAlarmController()
        self._last_alarm_statuses: tuple[Wits0LiveAlarmStatus, ...] = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(self._build_toolbar())

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

        self._populate_panel_controls()
        self._restore_last_form()
        self._update_form_description()
        self._set_empty_state()

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget(self)
        toolbar.setObjectName("wits0LiveToolbar")
        layout = QGridLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(5)

        form_label = QLabel(_live_form_selector_label(self._language), toolbar)
        form_label.setObjectName("wits0LiveFormLabel")
        layout.addWidget(form_label, 0, 0)

        self.form_combo = QComboBox(toolbar)
        for definition in live_form_definitions():
            self.form_combo.addItem(
                definition.title(self._language),
                definition.form_id,
            )
        universal_index = self.form_combo.findData(UNIVERSAL_LIVE_FORM_ID)
        if universal_index >= 0:
            self.form_combo.setCurrentIndex(universal_index)
        self.form_combo.setMinimumWidth(160)
        self.form_combo.currentIndexChanged.connect(self._form_changed)
        layout.addWidget(self.form_combo, 0, 1, 1, 2)

        self.save_form_button = QPushButton(
            _operator_text(self._language, "save_form"),
            toolbar,
        )
        self.save_form_button.setProperty("uiRole", "primary")
        self.save_form_button.setMinimumWidth(0)
        self.save_form_button.clicked.connect(self._save_current_form)
        layout.addWidget(self.save_form_button, 0, 3)

        self.reset_form_button = QPushButton(
            _operator_text(self._language, "reset_form"),
            toolbar,
        )
        self.reset_form_button.setProperty("uiRole", "quiet")
        self.reset_form_button.setMinimumWidth(0)
        self.reset_form_button.clicked.connect(self._reset_current_form)
        layout.addWidget(self.reset_form_button, 0, 4)

        axis_label = QLabel(self._t("wits0_live.axis"), toolbar)
        axis_label.setObjectName("wits0LiveAxisLabel")
        layout.addWidget(axis_label, 1, 0)
        self.axis_combo = QComboBox(toolbar)
        self.axis_combo.currentIndexChanged.connect(self._axis_changed)
        layout.addWidget(self.axis_combo, 1, 1)

        self.auto_follow_check = QCheckBox(self._t("wits0_live.auto_follow"), toolbar)
        self.auto_follow_check.setChecked(True)
        self.auto_follow_check.toggled.connect(self._auto_follow_changed)
        layout.addWidget(self.auto_follow_check, 1, 2)

        self.pause_button = QPushButton(self._t("wits0_live.pause_view"), toolbar)
        self.pause_button.setCheckable(True)
        self.pause_button.setMinimumWidth(0)
        self.pause_button.toggled.connect(self._pause_changed)
        layout.addWidget(self.pause_button, 1, 3, 1, 2)

        window_label = QLabel(self._t("wits0_live.window"), toolbar)
        window_label.setObjectName("wits0LiveWindowLabel")
        layout.addWidget(window_label, 2, 0)
        self.window_spin = QDoubleSpinBox(toolbar)
        self.window_spin.setDecimals(1)
        self.window_spin.setRange(0.1, 86_400.0)
        self.window_spin.setValue(600.0)
        self.window_spin.setSuffix(self._t("wits0_live.seconds_suffix"))
        self.window_spin.valueChanged.connect(self._follow_span_changed)
        layout.addWidget(self.window_spin, 2, 1)

        max_points_label = QLabel(self._t("wits0_live.max_points"), toolbar)
        max_points_label.setObjectName("wits0LiveMaxPointsLabel")
        layout.addWidget(max_points_label, 2, 2)
        self.max_points_spin = QSpinBox(toolbar)
        self.max_points_spin.setRange(100, 20_000)
        self.max_points_spin.setSingleStep(100)
        self.max_points_spin.setValue(2_000)
        self.max_points_spin.valueChanged.connect(self.refresh)
        layout.addWidget(self.max_points_spin, 2, 3)

        self.refresh_button = QPushButton(self._t("wits0_live.refresh"), toolbar)
        self.refresh_button.setMinimumWidth(0)
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button, 2, 4)

        self.sidebar_button = QPushButton(
            _operator_text(self._language, "hide_sidebar"),
            toolbar,
        )
        self.sidebar_button.setMinimumWidth(0)
        self.sidebar_button.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_button, 3, 0, 1, 2)

        self.fullscreen_button = QPushButton(
            _operator_text(self._language, "fullscreen"),
            toolbar,
        )
        self.fullscreen_button.setMinimumWidth(0)
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)
        layout.addWidget(self.fullscreen_button, 3, 2, 1, 2)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)
        layout.setColumnStretch(4, 1)
        return toolbar

    def _build_left_panel(self) -> QWidget:
        panel = QScrollArea(self)
        panel.setObjectName("wits0LiveSidebar")
        panel.setMinimumWidth(0)
        panel.setWidgetResizable(True)
        panel.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        panel.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        content = QWidget(panel)
        content.setMinimumWidth(0)
        panel.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 6, 0)

        curve_group = QGroupBox(self._t("wits0_live.curves"), content)
        curve_layout = QVBoxLayout(curve_group)
        self.curve_list = QListWidget(curve_group)
        self.curve_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.curve_list.itemChanged.connect(self._curve_selection_changed)
        curve_layout.addWidget(self.curve_list)
        layout.addWidget(curve_group, 2)

        panel_group = QGroupBox(
            _operator_text(self._language, "panel_layout_group"),
            content,
        )
        panel_layout = QVBoxLayout(panel_group)
        self.panel_list = QListWidget(panel_group)
        self.panel_list.setObjectName("wits0PanelLayoutList")
        self.panel_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.panel_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.panel_list.setMinimumHeight(120)
        self.panel_list.setMaximumHeight(180)
        self.panel_list.itemChanged.connect(self._panel_visibility_changed)
        self.panel_list.currentRowChanged.connect(
            self._panel_selection_changed
        )
        panel_layout.addWidget(self.panel_list)

        panel_actions = QGridLayout()
        panel_actions.setHorizontalSpacing(6)
        self.panel_up_button = QPushButton(
            _operator_text(self._language, "panel_up"),
            panel_group,
        )
        self.panel_up_button.setObjectName("wits0PanelUpButton")
        self.panel_up_button.setMinimumWidth(0)
        self.panel_up_button.clicked.connect(
            lambda: self._move_selected_panel(-1)
        )
        panel_actions.addWidget(self.panel_up_button, 0, 0)
        self.panel_down_button = QPushButton(
            _operator_text(self._language, "panel_down"),
            panel_group,
        )
        self.panel_down_button.setObjectName("wits0PanelDownButton")
        self.panel_down_button.setMinimumWidth(0)
        self.panel_down_button.clicked.connect(
            lambda: self._move_selected_panel(1)
        )
        panel_actions.addWidget(self.panel_down_button, 0, 1)
        panel_actions.setColumnStretch(0, 1)
        panel_actions.setColumnStretch(1, 1)
        panel_layout.addLayout(panel_actions)

        scale_grid = QGridLayout()
        scale_grid.setHorizontalSpacing(6)
        scale_grid.setVerticalSpacing(4)
        scale_label = QLabel(
            _operator_text(self._language, "panel_scale"),
            panel_group,
        )
        scale_grid.addWidget(scale_label, 0, 0)
        self.panel_scale_combo = QComboBox(panel_group)
        self.panel_scale_combo.setObjectName("wits0PanelScaleCombo")
        self.panel_scale_combo.setMinimumWidth(0)
        self.panel_scale_combo.currentIndexChanged.connect(
            self._panel_scale_target_changed
        )
        scale_grid.addWidget(self.panel_scale_combo, 0, 1, 1, 3)

        self.panel_x_auto_check = QCheckBox(
            _operator_text(self._language, "panel_x_auto"),
            panel_group,
        )
        self.panel_x_auto_check.setObjectName("wits0PanelXAutoCheck")
        self.panel_x_auto_check.toggled.connect(
            self._panel_x_auto_toggled
        )
        scale_grid.addWidget(self.panel_x_auto_check, 1, 0, 1, 2)

        minimum_label = QLabel(
            _operator_text(self._language, "panel_x_min"),
            panel_group,
        )
        scale_grid.addWidget(minimum_label, 2, 0)
        self.panel_x_min_spin = QDoubleSpinBox(panel_group)
        self.panel_x_min_spin.setObjectName("wits0PanelXMin")
        self.panel_x_min_spin.setDecimals(6)
        self.panel_x_min_spin.setRange(-1.0e15, 1.0e15)
        self.panel_x_min_spin.setKeyboardTracking(False)
        scale_grid.addWidget(self.panel_x_min_spin, 2, 1)

        maximum_label = QLabel(
            _operator_text(self._language, "panel_x_max"),
            panel_group,
        )
        scale_grid.addWidget(maximum_label, 2, 2)
        self.panel_x_max_spin = QDoubleSpinBox(panel_group)
        self.panel_x_max_spin.setObjectName("wits0PanelXMax")
        self.panel_x_max_spin.setDecimals(6)
        self.panel_x_max_spin.setRange(-1.0e15, 1.0e15)
        self.panel_x_max_spin.setKeyboardTracking(False)
        scale_grid.addWidget(self.panel_x_max_spin, 2, 3)

        self.panel_x_apply_button = QPushButton(
            _operator_text(self._language, "panel_x_apply"),
            panel_group,
        )
        self.panel_x_apply_button.setObjectName("wits0PanelXApply")
        self.panel_x_apply_button.setMinimumWidth(0)
        self.panel_x_apply_button.clicked.connect(
            self._apply_selected_panel_x_range
        )
        scale_grid.addWidget(self.panel_x_apply_button, 3, 0, 1, 4)
        scale_grid.setColumnStretch(1, 1)
        scale_grid.setColumnStretch(3, 1)
        panel_layout.addLayout(scale_grid)
        layout.addWidget(panel_group)

        self.alarm_editor = Wits0AlarmSettingsEditor(
            content,
            language=self._language,
        )
        self.alarm_editor.rulesChanged.connect(self._alarm_rules_changed)
        layout.addWidget(self.alarm_editor)

        alarm_runtime_group = QGroupBox(
            _operator_text(self._language, "alarm_runtime_group"),
            content,
        )
        alarm_runtime_layout = QVBoxLayout(alarm_runtime_group)
        self.alarm_summary_label = QLabel(
            _operator_text(self._language, "alarm_none"),
            alarm_runtime_group,
        )
        self.alarm_summary_label.setObjectName("wits0AlarmRuntimeSummary")
        self.alarm_summary_label.setWordWrap(True)
        alarm_runtime_layout.addWidget(self.alarm_summary_label)
        self.acknowledge_alarms_button = QPushButton(
            _operator_text(self._language, "alarm_ack_all"),
            alarm_runtime_group,
        )
        self.acknowledge_alarms_button.setObjectName("wits0AlarmAcknowledgeAll")
        self.acknowledge_alarms_button.setEnabled(False)
        self.acknowledge_alarms_button.clicked.connect(
            self._acknowledge_active_alarms
        )
        alarm_runtime_layout.addWidget(self.acknowledge_alarms_button)
        layout.addWidget(alarm_runtime_group)

        dexp_group = QGroupBox(
            _operator_text(self._language, "dexp_correction_group"),
            content,
        )
        dexp_layout = QVBoxLayout(dexp_group)
        self.dexp_correction_check = QCheckBox(
            _operator_text(self._language, "dexp_correction_enable"),
            dexp_group,
        )
        self.dexp_correction_check.setToolTip(
            _operator_text(self._language, "dexp_correction_help")
        )
        dexp_layout.addWidget(self.dexp_correction_check)

        density_grid = QGridLayout()
        density_label = QLabel(
            _operator_text(self._language, "normal_mud_density"),
            dexp_group,
        )
        density_label.setWordWrap(True)
        density_grid.addWidget(density_label, 0, 0, 1, 2)
        self.normal_mud_density_spin = QDoubleSpinBox(dexp_group)
        self.normal_mud_density_spin.setDecimals(3)
        self.normal_mud_density_spin.setRange(0.001, 5_000.0)
        self.normal_mud_density_spin.setValue(1.0)
        self.normal_mud_density_spin.setEnabled(False)
        density_grid.addWidget(self.normal_mud_density_spin, 1, 0)

        self.normal_mud_density_unit_combo = QComboBox(dexp_group)
        for unit in ("ppg", "kg/m3", "g/cm3"):
            self.normal_mud_density_unit_combo.addItem(unit, unit)
        self.normal_mud_density_unit_combo.setEnabled(False)
        density_grid.addWidget(self.normal_mud_density_unit_combo, 1, 1)
        density_grid.setColumnStretch(0, 1)
        dexp_layout.addLayout(density_grid)
        layout.addWidget(dexp_group)

        self.dexp_correction_check.toggled.connect(self._dexp_correction_changed)
        self.normal_mud_density_spin.valueChanged.connect(
            self._dexp_correction_changed
        )
        self.normal_mud_density_unit_combo.currentIndexChanged.connect(
            self._dexp_correction_changed
        )

        values_group = QGroupBox(
            self._t("wits0_live.current_values"),
            content,
        )
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
        values_header = self.values_table.horizontalHeader()
        values_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        values_header.setMinimumSectionSize(48)
        self.values_table.setAlternatingRowColors(True)
        values_layout.addWidget(self.values_table)
        layout.addWidget(values_group, 3)
        return panel

    def _build_plot_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("wits0LivePlotPanel")
        panel.setMinimumWidth(0)
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
        self.dashboard.scaleTargetsChanged.connect(
            self._sync_panel_scale_controls
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
            if self._preview_mode and self._view is not None
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
        self._alarm_controller.clear()
        self._last_alarm_statuses = ()
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
        self._virtual_curves = self._derived_curves_for_dataset(
            runtime.controller.dataset
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
            self.panel_list,
            self.panel_scale_combo,
            self.panel_x_auto_check,
            self.panel_x_min_spin,
            self.panel_x_max_spin,
            self.panel_x_apply_button,
            self.alarm_editor,
        ):
            widget.setEnabled(True)
        self._populate_axes()
        self._populate_curves()
        if previous_state is not None:
            # Preserve in-session edits while LIVE PREVIEW is rebound to the reviewed
            # persistent runtime. Explicit "Save form" controls cross-session persistence.
            self.apply_workspace_state(previous_state)
        else:
            self._apply_live_form_selection()
            self.refresh(force=True)

    def diagnostic_plotted_points(self) -> int:
        """Return the latest aggregate point count submitted to the live plot."""

        return self._last_plot_rendered_points

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
            selected_mnemonics=self._selected_mnemonics(),
            selected_curve_ids=(),
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
            selected = set(
                self._curve_ids_for_mnemonics(state.selected_mnemonics)
            )
            if not selected and state.selected_curve_ids:
                available_curve_ids = {
                    self.curve_list.item(row).data(Qt.ItemDataRole.UserRole)
                    for row in range(self.curve_list.count())
                }
                selected = set(state.selected_curve_ids).intersection(
                    available_curve_ids
                )
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
            self._set_view_source_selection(self._selected_curve_ids())
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
        self._virtual_curves = {}
        self._preview_mode = False
        self._last_revision = None
        self._last_plot_rendered_points = 0
        self._alarm_controller.clear()
        self._last_alarm_statuses = ()
        self.curve_list.clear()
        self.alarm_editor.set_channels(())
        self.alarm_editor.set_rules(())
        self.alarm_summary_label.setText(_operator_text(self._language, "alarm_none"))
        self.acknowledge_alarms_button.setEnabled(False)
        self.values_table.setRowCount(0)
        self.dashboard.clear()
        self._set_empty_state()

    def refresh(self, _value: object = None, *, force: bool = False) -> None:
        view = self._view
        if view is None:
            self._set_empty_state()
            return
        selected_mnemonics = self._selected_mnemonics()
        refreshed_virtual = self._derived_curves_for_dataset(view.dataset)
        if set(refreshed_virtual) != set(self._virtual_curves):
            self._virtual_curves = refreshed_virtual
            self._populate_curves(preserve_mnemonics=selected_mnemonics)
        else:
            self._virtual_curves = refreshed_virtual
        selected = self._selected_curve_ids()
        self._set_view_source_selection(selected)
        try:
            snapshot = view.snapshot(
                curve_ids=selected,
                virtual_curves=self._virtual_curves,
                max_points_per_curve=self.max_points_spin.value(),
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            self.state_label.setText(self._t("wits0_live.error", error=str(exc)))
            self.state_label.setToolTip(self._t("wits0_live.error_help"))
            self.summary_label.setText(self._t("wits0_live.error_view_only"))
            return
        alarm_statuses = self._alarm_controller.evaluate(
            view.session,
            snapshot.current_values,
            virtual_curves=self._virtual_curves,
            dataset_row_count=len(view.dataset.depth),
        )
        self._last_alarm_statuses = alarm_statuses
        if not force and snapshot.revision == self._last_revision:
            self._render_current_values(snapshot, alarm_statuses)
            self._render_alarm_summary(alarm_statuses)
            return
        self._last_revision = snapshot.revision
        self._render_snapshot(snapshot, alarm_statuses)

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

    def _populate_curves(
        self,
        *,
        preserve_mnemonics: tuple[str, ...] | None = None,
    ) -> None:
        view = self._view
        if view is None:
            return
        curves = list(self._all_curves())
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
        self.alarm_editor.set_channels(
            (
                (
                    curve.metadata.canonical_mnemonic
                    or curve.metadata.original_mnemonic,
                    curve.metadata.unit,
                )
                for curve in curves
            )
        )
        if preserve_mnemonics is None:
            self._apply_live_form_selection()
        else:
            selected = set(self._curve_ids_for_mnemonics(preserve_mnemonics))
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
            finally:
                self._updating_controls = False

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
            for curve in self._all_curves()
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
            self.dashboard.set_panel_layout(
                saved.panel_order,
                saved.hidden_panel_ids,
            )
            self.dashboard.set_panel_x_ranges(saved.panel_x_ranges)
            self.alarm_editor.set_rules(saved.alarm_rules)
            self._alarm_controller.set_rules(saved.alarm_rules)
            self._last_alarm_statuses = ()
            self._sync_panel_controls_from_dashboard()
            try:
                view.set_axis_mode(AcquisitionLiveAxisMode(saved.axis_mode))
            except ValueError:
                view.set_axis_mode(AcquisitionLiveAxisMode.AUTO)
            view.set_auto_follow(saved.auto_follow)
            view.set_follow_span(saved.follow_span)
        else:
            self.dashboard.set_panel_layout()
            self.dashboard.set_panel_x_ranges(())
            self.alarm_editor.set_rules(())
            self._alarm_controller.set_rules(())
            self._last_alarm_statuses = ()
            self._sync_panel_controls_from_dashboard()
        self._set_view_source_selection(self._selected_curve_ids())

    def _dexp_correction_config(self) -> Wits0DexpCorrectionConfig | None:
        if not self.dexp_correction_check.isChecked():
            return None
        unit = str(self.normal_mud_density_unit_combo.currentData() or "").strip()
        return Wits0DexpCorrectionConfig(
            normal_mud_density=float(self.normal_mud_density_spin.value()),
            unit=unit,
        )

    def _dexp_correction_changed(self, _value: object = None) -> None:
        enabled = self.dexp_correction_check.isChecked()
        self.normal_mud_density_spin.setEnabled(enabled)
        self.normal_mud_density_unit_combo.setEnabled(enabled)
        self._derived_service = Wits0LiveDerivedChannelService(
            dexp_correction=self._dexp_correction_config()
        )
        self._last_revision = None
        if self._view is not None:
            self.refresh(force=True)

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

    def _populate_panel_controls(self) -> None:
        """Build the operator editor from the dashboard's canonical panels."""

        self._sync_panel_controls_from_dashboard()

    def _sync_panel_controls_from_dashboard(self) -> None:
        current_id: str | None = None
        current_item = self.panel_list.currentItem()
        if current_item is not None:
            raw_current = current_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(raw_current, str):
                current_id = raw_current

        panel_order, hidden_panel_ids = self.dashboard.panel_layout()
        hidden = set(hidden_panel_ids)
        self.panel_list.blockSignals(True)
        try:
            self.panel_list.clear()
            selected_row = -1
            for row, panel_id in enumerate(panel_order):
                panel = self.dashboard.panels.get(panel_id)
                if panel is None:
                    continue
                title = panel.definition.title(self._language)
                item = QListWidgetItem(title, self.panel_list)
                item.setData(Qt.ItemDataRole.UserRole, panel_id)
                item.setToolTip(title)
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if panel_id in hidden
                    else Qt.CheckState.Checked
                )
                if panel_id == current_id:
                    selected_row = row
            if selected_row < 0 and self.panel_list.count():
                selected_row = 0
            if selected_row >= 0:
                self.panel_list.setCurrentRow(selected_row)
        finally:
            self.panel_list.blockSignals(False)
        self._refresh_panel_order_buttons()
        self._sync_panel_scale_controls()

    def _panel_layout_from_controls(
        self,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        order: list[str] = []
        hidden: list[str] = []
        for row in range(self.panel_list.count()):
            item = self.panel_list.item(row)
            panel_id = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(panel_id, str) or not panel_id:
                continue
            order.append(panel_id)
            if item.checkState() != Qt.CheckState.Checked:
                hidden.append(panel_id)
        return tuple(order), tuple(hidden)

    def _apply_panel_controls(self, *, refresh: bool) -> None:
        panel_order, hidden_panel_ids = self._panel_layout_from_controls()
        self.dashboard.set_panel_layout(panel_order, hidden_panel_ids)
        if refresh and self._view is not None:
            self._last_revision = None
            self.refresh(force=True)

    def _panel_visibility_changed(self, _item: QListWidgetItem) -> None:
        self._apply_panel_controls(refresh=True)

    def _move_selected_panel(self, offset: int) -> None:
        current_row = self.panel_list.currentRow()
        if current_row < 0 or offset == 0:
            return
        target_row = current_row + offset
        if not 0 <= target_row < self.panel_list.count():
            return
        item = self.panel_list.takeItem(current_row)
        if item is None:
            return
        self.panel_list.insertItem(target_row, item)
        self.panel_list.setCurrentRow(target_row)
        self._apply_panel_controls(refresh=False)
        self._refresh_panel_order_buttons()

    def _refresh_panel_order_buttons(self, _row: int = -1) -> None:
        row = self.panel_list.currentRow()
        count = self.panel_list.count()
        enabled = self._view is not None
        self.panel_up_button.setEnabled(enabled and row > 0)
        self.panel_down_button.setEnabled(
            enabled and 0 <= row < count - 1
        )

    def _panel_selection_changed(self, _row: int) -> None:
        self._refresh_panel_order_buttons()
        self._sync_panel_scale_controls()

    def _selected_panel_id(self) -> str | None:
        item = self.panel_list.currentItem()
        if item is None:
            return None
        panel_id = item.data(Qt.ItemDataRole.UserRole)
        return panel_id if isinstance(panel_id, str) else None

    def _sync_panel_scale_controls(self) -> None:
        panel_id = self._selected_panel_id()
        current_key = self.panel_scale_combo.currentData()
        targets = (
            self.dashboard.panel_scale_targets(panel_id)
            if panel_id is not None
            else ()
        )
        self.panel_scale_combo.blockSignals(True)
        try:
            self.panel_scale_combo.clear()
            selected_index = -1
            for index, target in enumerate(targets):
                self.panel_scale_combo.addItem(
                    target.title,
                    target.scale_key,
                )
                if target.scale_key == current_key:
                    selected_index = index
            if selected_index < 0 and targets:
                selected_index = 0
            if selected_index >= 0:
                self.panel_scale_combo.setCurrentIndex(selected_index)
        finally:
            self.panel_scale_combo.blockSignals(False)
        self._load_selected_panel_scale_target()

    def _panel_scale_target_changed(self, _index: int) -> None:
        self._load_selected_panel_scale_target()

    def _load_selected_panel_scale_target(self) -> None:
        panel_id = self._selected_panel_id()
        scale_key = self.panel_scale_combo.currentData()
        target = None
        if panel_id is not None and isinstance(scale_key, str):
            target = next(
                (
                    item
                    for item in self.dashboard.panel_scale_targets(panel_id)
                    if item.scale_key == scale_key
                ),
                None,
            )
        enabled = target is not None and self._view is not None
        self.panel_scale_combo.setEnabled(enabled)
        self.panel_x_auto_check.blockSignals(True)
        try:
            self.panel_x_auto_check.setChecked(
                True if target is None else target.auto_range
            )
        finally:
            self.panel_x_auto_check.blockSignals(False)
        if target is not None:
            self.panel_x_min_spin.setValue(target.minimum)
            self.panel_x_max_spin.setValue(target.maximum)
        manual_enabled = enabled and not self.panel_x_auto_check.isChecked()
        self.panel_x_auto_check.setEnabled(enabled)
        self.panel_x_min_spin.setEnabled(manual_enabled)
        self.panel_x_max_spin.setEnabled(manual_enabled)
        self.panel_x_apply_button.setEnabled(enabled)

    def _panel_x_auto_toggled(self, auto_range: bool) -> None:
        enabled = self._view is not None and not auto_range
        if enabled:
            panel_id = self._selected_panel_id()
            scale_key = self.panel_scale_combo.currentData()
            if panel_id is not None and isinstance(scale_key, str):
                target = next(
                    (
                        item
                        for item in self.dashboard.panel_scale_targets(
                            panel_id
                        )
                        if item.scale_key == scale_key
                    ),
                    None,
                )
                if target is not None:
                    self.panel_x_min_spin.setValue(target.minimum)
                    self.panel_x_max_spin.setValue(target.maximum)
        self.panel_x_min_spin.setEnabled(enabled)
        self.panel_x_max_spin.setEnabled(enabled)

    def _apply_selected_panel_x_range(self) -> None:
        scale_key = self.panel_scale_combo.currentData()
        if not isinstance(scale_key, str) or not scale_key:
            return
        if self.panel_x_auto_check.isChecked():
            self.dashboard.reset_panel_x_range(scale_key)
            self._sync_panel_scale_controls()
            return
        minimum = float(self.panel_x_min_spin.value())
        maximum = float(self.panel_x_max_spin.value())
        if minimum >= maximum:
            self.state_label.setText(
                _operator_text(self._language, "panel_x_invalid")
            )
            return
        self.dashboard.set_panel_x_range(
            scale_key,
            minimum,
            maximum,
        )
        self._sync_panel_scale_controls()

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

    def _render_snapshot(
        self,
        snapshot: AcquisitionLiveSnapshot,
        alarm_statuses: tuple[Wits0LiveAlarmStatus, ...],
    ) -> None:
        self._last_plot_rendered_points = snapshot.rendered_point_count
        self._updating_plot_range = True
        try:
            self.dashboard.render_snapshot(snapshot)
        finally:
            self._updating_plot_range = False

        self._render_current_values(snapshot, alarm_statuses)
        self._render_alarm_summary(alarm_statuses)
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
        health = snapshot.health
        health_text = self._t(f"wits0_live.health_{health.value}")
        self.state_label.setText(
            self._t(
                "wits0_live.state_summary",
                state=self._t(
                    "wits0_live.state_with_health",
                    state=state,
                    health=health_text,
                ),
                dataset=snapshot.dataset_id,
                rows=snapshot.total_row_count,
                visible=snapshot.visible_row_count,
            )
        )
        self.state_label.setToolTip(self._health_tooltip(health))
        self.summary_label.setText(
            self._t(
                "wits0_live.render_summary",
                source=snapshot.source_point_count,
                rendered=snapshot.rendered_point_count,
                markers=len(snapshot.markers),
            )
        )

    def _render_current_values(
        self,
        snapshot: AcquisitionLiveSnapshot,
        alarm_statuses: tuple[Wits0LiveAlarmStatus, ...],
    ) -> None:
        values = snapshot.current_values
        self.dashboard.render_current_values(values)
        self.dashboard.render_alarm_statuses(alarm_statuses)
        alarm_by_curve = {status.curve_id: status for status in alarm_statuses}
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
            alarm_status = alarm_by_curve.get(item.curve_id)
            alarm_background = _alarm_background(alarm_status)
            if alarm_status is not None and alarm_status.is_active:
                alarm_note = _alarm_status_text(self._language, alarm_status)
                tooltip = f"{tooltip}; {alarm_note}" if tooltip else alarm_note
            for column, value in enumerate(cells):
                cell = QTableWidgetItem(value)
                cell.setToolTip(tooltip)
                if foreground is not None:
                    cell.setForeground(QBrush(foreground))
                if alarm_background is not None:
                    cell.setBackground(QBrush(alarm_background))
                self.values_table.setItem(row, column, cell)

    def _render_alarm_summary(
        self,
        statuses: tuple[Wits0LiveAlarmStatus, ...],
    ) -> None:
        active = tuple(status for status in statuses if status.is_active)
        attention = tuple(status for status in active if status.needs_attention)
        if not active:
            self.alarm_summary_label.setText(
                _operator_text(self._language, "alarm_none")
            )
            self.acknowledge_alarms_button.setEnabled(False)
            return
        items = ", ".join(
            _alarm_status_text(self._language, status)
            for status in active
        )
        self.alarm_summary_label.setText(
            _operator_text(self._language, "alarm_active").format(items=items)
        )
        self.acknowledge_alarms_button.setEnabled(bool(attention))

    def _alarm_rules_changed(self) -> None:
        self._alarm_controller.set_rules(self.alarm_editor.rules())
        self._last_alarm_statuses = ()
        if self._view is not None:
            self._last_revision = None
            self.refresh(force=True)

    def _acknowledge_active_alarms(self) -> None:
        if self._alarm_controller.acknowledge_all() <= 0:
            return
        if self._view is not None:
            self.refresh(force=True)

    def _set_empty_state(self) -> None:
        self.state_label.setText(self._t("wits0_live.no_session"))
        self.state_label.setToolTip(self._t("wits0_live.no_session_help"))
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
            self.panel_list,
            self.panel_up_button,
            self.panel_down_button,
            self.panel_scale_combo,
            self.panel_x_auto_check,
            self.panel_x_min_spin,
            self.panel_x_max_spin,
            self.panel_x_apply_button,
            self.alarm_editor,
            self.acknowledge_alarms_button,
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
        for curve in self._all_curves():
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
        for curve in self._all_curves():
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

    def _all_curves(self) -> tuple[CurveData, ...]:
        view = self._view
        if view is None:
            return ()
        return (*view.dataset.curves.values(), *self._virtual_curves.values())

    def _derived_curves_for_dataset(self, dataset: object) -> dict[str, CurveData]:
        if not isinstance(dataset, Dataset):
            return {}
        return self._derived_service.virtual_curves(dataset)

    def _set_view_source_selection(self, curve_ids: tuple[str, ...]) -> None:
        view = self._view
        if view is None:
            return
        source_ids = tuple(
            curve_id for curve_id in curve_ids if curve_id in view.dataset.curves
        )
        view.set_selected_curves(source_ids)

    def _save_current_form(self) -> None:
        view = self._view
        if view is None:
            return
        form_id = str(self.form_combo.currentData() or UNIVERSAL_LIVE_FORM_ID)
        panel_order, hidden_panel_ids = self.dashboard.panel_layout()
        state = Wits0SavedLiveFormState(
            form_id=form_id,
            selected_mnemonics=self._selected_mnemonics(),
            axis_mode=str(self.axis_combo.currentData() or "auto"),
            auto_follow=self.auto_follow_check.isChecked(),
            follow_span=float(self.window_spin.value()),
            max_points=int(self.max_points_spin.value()),
            sidebar_visible=(
                True
                if self._sidebar_user_override is None
                else self._sidebar_user_override
            ),
            panel_order=panel_order,
            hidden_panel_ids=hidden_panel_ids,
            panel_x_ranges=self.dashboard.panel_x_ranges(),
            alarm_rules=self.alarm_editor.rules(),
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
        self._compact_parameters_open = False
        self.dashboard.set_panel_layout()
        self.dashboard.set_panel_x_ranges(())
        self.alarm_editor.clear_rules()
        self._sync_panel_controls_from_dashboard()
        self._apply_navigation_layout()
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

    def _is_compact_navigation(self) -> bool:
        return self._fullscreen or self.width() < _COMPACT_NAVIGATION_BREAKPOINT

    def _apply_navigation_layout(self) -> None:
        compact = self._is_compact_navigation()
        if compact != self._compact_navigation_active:
            self._compact_navigation_active = compact
            if compact:
                self._compact_parameters_open = False

        if compact:
            parameters_open = self._compact_parameters_open
            self.left_panel.setVisible(parameters_open)
            self.plot_panel.setVisible(not parameters_open)
            self.sidebar_button.setText(
                _operator_text(
                    self._language,
                    "back_to_monitor" if parameters_open else "show_sidebar",
                )
            )
            available = max(1, self.width())
            self.splitter.setSizes(
                [available, 0] if parameters_open else [0, available]
            )
            return

        self._compact_parameters_open = False
        self.plot_panel.setVisible(True)
        sidebar_visible = (
            True
            if self._sidebar_user_override is None
            else self._sidebar_user_override
        )
        self.left_panel.setVisible(sidebar_visible)
        self.sidebar_button.setText(
            _operator_text(
                self._language,
                "hide_sidebar" if sidebar_visible else "show_sidebar",
            )
        )
        available = max(1, self.width())
        if sidebar_visible:
            sidebar_width = min(
                _WIDE_SIDEBAR_WIDTH,
                max(240, available // 3),
            )
            self.splitter.setSizes(
                [sidebar_width, max(1, available - sidebar_width)]
            )
        else:
            self.splitter.setSizes([0, available])

    def _set_sidebar_visible(self, visible: bool) -> None:
        self._sidebar_user_override = bool(visible)
        self._apply_navigation_layout()

    def _toggle_sidebar(self) -> None:
        if self._is_compact_navigation():
            self._compact_parameters_open = not self._compact_parameters_open
            self._apply_navigation_layout()
            return
        self._set_sidebar_visible(not self.left_panel.isVisible())

    def _toggle_fullscreen(self) -> None:
        self.fullScreenRequested.emit(not self._fullscreen)

    def set_fullscreen_state(self, enabled: bool) -> None:
        self._fullscreen = bool(enabled)
        if enabled:
            self._compact_parameters_open = False
        self.fullscreen_button.setText(
            _operator_text(
                self._language,
                "exit_fullscreen" if enabled else "fullscreen",
            )
        )
        self._apply_navigation_layout()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_navigation_layout()

    def _health_tooltip(self, health: AcquisitionLiveHealth) -> str:
        return self._t(f"wits0_live.health_{health.value}_help")

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
            "back_to_monitor": "Назад к монитору",
            "fullscreen": "На весь экран",
            "exit_fullscreen": "Выйти из полного экрана",
            "saved_override": "сохранённая настройка",
            "factory_template": "заводской шаблон",
            "form_saved": "Форма «{form}» сохранена.",
            "dexp_correction_group": "Коррекция DEXP",
            "dexp_correction_enable": "Включить DEXPC",
            "dexp_correction_help": "DEXPC рассчитывается только после явного задания нормальной плотности бурового раствора.",
            "normal_mud_density": "Нормальная плотность раствора",
            "panel_layout_group": "Панели графиков",
            "panel_up": "Выше",
            "panel_down": "Ниже",
            "panel_scale": "Шкала X",
            "panel_x_auto": "Авто X",
            "panel_x_min": "Мин.",
            "panel_x_max": "Макс.",
            "panel_x_apply": "Применить X-диапазон",
            "panel_x_invalid": "Минимум X должен быть меньше максимума.",
            "alarm_runtime_group": "Активные тревоги",
            "alarm_none": "Активных тревог нет.",
            "alarm_active": "Активные тревоги: {items}",
            "alarm_ack_all": "Подтвердить активные тревоги",
            "alarm_ack": "подтверждено",
            "alarm_high": "выше максимума",
            "alarm_low": "ниже минимума",
        },
        AppLanguage.KK: {
            "save_form": "Пішінді сақтау",
            "reset_form": "Қалпына келтіру",
            "hide_sidebar": "Параметрлерді жасыру",
            "show_sidebar": "Параметрлерді көрсету",
            "back_to_monitor": "Мониторға қайту",
            "fullscreen": "Толық экран",
            "exit_fullscreen": "Толық экраннан шығу",
            "saved_override": "сақталған баптау",
            "factory_template": "зауыттық үлгі",
            "form_saved": "«{form}» пішіні сақталды.",
            "dexp_correction_group": "DEXP түзетуі",
            "dexp_correction_enable": "DEXPC қосу",
            "dexp_correction_help": "DEXPC бұрғылау ерітіндісінің қалыпты тығыздығы анық берілгеннен кейін ғана есептеледі.",
            "normal_mud_density": "Ерітіндінің қалыпты тығыздығы",
            "panel_layout_group": "График панельдері",
            "panel_up": "Жоғары",
            "panel_down": "Төмен",
            "panel_scale": "X шкаласы",
            "panel_x_auto": "Авто X",
            "panel_x_min": "Мин.",
            "panel_x_max": "Макс.",
            "panel_x_apply": "X ауқымын қолдану",
            "panel_x_invalid": "X минимумы максимумнан кіші болуы керек.",
            "alarm_runtime_group": "Белсенді дабылдар",
            "alarm_none": "Белсенді дабылдар жоқ.",
            "alarm_active": "Белсенді дабылдар: {items}",
            "alarm_ack_all": "Белсенді дабылдарды растау",
            "alarm_ack": "расталды",
            "alarm_high": "максимумнан жоғары",
            "alarm_low": "минимумнан төмен",
        },
        AppLanguage.EN: {
            "save_form": "Save form",
            "reset_form": "Reset",
            "hide_sidebar": "Hide parameters",
            "show_sidebar": "Show parameters",
            "back_to_monitor": "Back to monitor",
            "fullscreen": "Full screen",
            "exit_fullscreen": "Exit full screen",
            "saved_override": "saved setup",
            "factory_template": "factory template",
            "form_saved": "Form “{form}” saved.",
            "dexp_correction_group": "DEXP correction",
            "dexp_correction_enable": "Enable DEXPC",
            "dexp_correction_help": "DEXPC is calculated only after an explicit normal mud density is supplied.",
            "normal_mud_density": "Normal mud density",
            "panel_layout_group": "Plot panels",
            "panel_up": "Move up",
            "panel_down": "Move down",
            "panel_scale": "X scale",
            "panel_x_auto": "Auto X",
            "panel_x_min": "Min",
            "panel_x_max": "Max",
            "panel_x_apply": "Apply X range",
            "panel_x_invalid": "X minimum must be smaller than maximum.",
            "alarm_runtime_group": "Active alarms",
            "alarm_none": "No active alarms.",
            "alarm_active": "Active alarms: {items}",
            "alarm_ack_all": "Acknowledge active alarms",
            "alarm_ack": "acknowledged",
            "alarm_high": "above maximum",
            "alarm_low": "below minimum",
        },
    }
    return translations.get(language, translations[AppLanguage.EN]).get(key, key)


def _alarm_status_text(
    language: AppLanguage,
    status: Wits0LiveAlarmStatus,
) -> str:
    side = (
        _operator_text(language, "alarm_high")
        if status.active_side is not None and status.active_side.value == "high"
        else _operator_text(language, "alarm_low")
    )
    suffix = (
        f" ({_operator_text(language, 'alarm_ack')})"
        if status.acknowledged
        else ""
    )
    return f"{status.mnemonic}: {side}{suffix}"


def _alarm_background(
    status: Wits0LiveAlarmStatus | None,
) -> QColor | None:
    if status is None or not status.is_active or not status.visual_enabled:
        return None
    return QColor("#fef3c7" if status.acknowledged else "#fee2e2")


def _quality_color(quality: AcquisitionLiveQuality) -> QColor | None:
    return {
        AcquisitionLiveQuality.GOOD: QColor("#15803d"),
        AcquisitionLiveQuality.MISSING: QColor("#64748b"),
        AcquisitionLiveQuality.INVALID: QColor("#dc2626"),
        AcquisitionLiveQuality.SOURCE_GAP: QColor("#d97706"),
        AcquisitionLiveQuality.STALE: QColor("#7c3aed"),
    }.get(quality)
