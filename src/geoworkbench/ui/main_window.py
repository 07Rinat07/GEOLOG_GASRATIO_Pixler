from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, QStandardPaths, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPageLayout,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QColorDialog,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QStyle,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench import __version__
from geoworkbench.calculations.controller import FormulaExecutionController
from geoworkbench.catalogs.sensors import SensorCatalog, set_active_sensor_catalog
from geoworkbench.calculations.custom_formula import formula_inputs
from geoworkbench.calculations.interval_statistics import calculate_interval_statistics
from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
from geoworkbench.importers.skf_importer import import_skf_file
from geoworkbench.domain.models import IndexRole
from geoworkbench.data.las_adapter import (
    LasExportError,
    LasImportError,
    import_las_with_report,
)
from geoworkbench.data.las_import_report import LasIssueSeverity
from geoworkbench.data.las_import_policy import LasImportMode, evaluate_las_import
from geoworkbench.data.csv_adapter import CsvImportError, import_csv
from geoworkbench.data.excel_adapter import ExcelImportError, import_excel
from geoworkbench.data.las_export_plan import ExportIssueSeverity
from geoworkbench.data.selection_export import SelectionExportError
from geoworkbench.data.visualization_export import (
    VisualizationExportError,
    export_widget_pdf,
    export_widget_png,
    export_widget_svg,
)
from geoworkbench.data.dataset_json_export import DatasetJsonExportError
from geoworkbench.data.dataset_parquet_export import DatasetParquetExportError
from geoworkbench.forms import (
    FormApplyEngine,
    FormAxisKind,
    FormRepository,
    form_from_tablet_layout,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.data_inspector_controller import DataInspectorController
from geoworkbench.project.curve_metadata_controller import CurveMetadataController
from geoworkbench.project.curve_transfer_controller import CurveTransferController
from geoworkbench.project.external_las_insert_controller import ExternalLasInsertController
from geoworkbench.project.custom_formula_controller import CustomFormulaController
from geoworkbench.project.header_editing_controller import HeaderEditingController
from geoworkbench.project.description_template_controller import DescriptionTemplateController
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.curve_editing_controller import (
    CurveEditingController,
    CurveEditOutcome,
)
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.annotation_schema import (
    AnnotationKind,
    annotation_from_canvas,
    is_annotation_object,
)
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.project.stratigraphy_catalog_controller import StratigraphyCatalogController
from geoworkbench.project.nct_controller import NctCalculationController
from geoworkbench.project.new_las_controller import NewLasController
from geoworkbench.project.las_range_editor import LasRangeEditingController
from geoworkbench.project.dataset_export_controller import DatasetExportController
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.time_depth_mapping_controller import TimeDepthMappingController
from geoworkbench.project.time_to_depth_controller import TimeToDepthController
from geoworkbench.printing.document_export import (
    export_document_pages,
    export_document_pdf,
    render_document_to_printer,
)
from geoworkbench.printing.document_renderer import PrintDocumentContext
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.storage.project_codec import ProjectFormatError
from geoworkbench.tablet import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.render_invalidation import DirtyReason
from geoworkbench.tablet.models import (
    CurveLineStyle,
    CurveStyle,
)
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.interval_interaction import IntervalEditMode
from geoworkbench.tablet.lithology_legend import build_lithology_legend
from geoworkbench.tablet.tablet_view import GeologicalInputMode, TabletView
from geoworkbench.ui.track_inspector import TrackInspector
from geoworkbench.ui.time_depth_mapping_dialog import TimeDepthMappingDialog
from geoworkbench.ui.time_to_depth_dialog import TimeToDepthDialog
from geoworkbench.ui.branding import application_icon, logo_pixmap
from geoworkbench.ui.csv_import_dialog import CsvImportDialog
from geoworkbench.ui.curve_transfer_dialog import CurveTransferDialog
from geoworkbench.ui.external_las_insert_dialog import ExternalLasInsertDialog
from geoworkbench.ui.curve_settings_dialog import CurveSettingsDialog
from geoworkbench.ui.excel_import_dialog import ExcelImportDialog
from geoworkbench.ui.paradox_import_dialog import ParadoxImportDialog
from geoworkbench.ui.paradox_batch_dialog import ParadoxBatchDialog
from geoworkbench.ui.form_manager_dialog import FormManagerDialog
from geoworkbench.ui.constructor_dialog import UniversalConstructorDialog
from geoworkbench.ui.formula_dialog import FormulaExecutionDialog
from geoworkbench.ui.custom_formula_dialog import CustomFormulaDialog
from geoworkbench.ui.depth_annotations_dialog import DepthAnnotationsDialog
from geoworkbench.ui.depth_resample_dialog import DepthResampleDialog
from geoworkbench.ui.description_templates_dialog import DescriptionTemplatesDialog
from geoworkbench.ui.data_inspector_dialog import DataInspectorDialog
from geoworkbench.ui.dataset_merge_dialog import DatasetMergeDialog
from geoworkbench.ui.interval_statistics_dialog import IntervalStatisticsDialog
from geoworkbench.ui.interpretation_report_dialog import InterpretationReportDialog
from geoworkbench.ui.interpretation_intervals_dialog import InterpretationIntervalsDialog
from geoworkbench.ui.interpretation_properties import InterpretationPropertiesPanel
from geoworkbench.ui.lithology_dialog import LithologyDialog
from geoworkbench.ui.lithology_interval_dialog import LithologyIntervalDialog
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog
from geoworkbench.ui.lithology_legend_dialog import LithologyLegendDialog
from geoworkbench.ui.lithotype_catalog_dialog import LithotypeCatalogDialog
from geoworkbench.ui.sensor_catalog_dialog import SensorCatalogDialog
from geoworkbench.ui.stratigraphy_dialog import (
    StratigraphyCatalogDialog,
    StratigraphyDialog,
    StratigraphyIntervalDialog,
)
from geoworkbench.ui.tablet_track_editor_dialog import TabletTrackEditorDialog
from geoworkbench.ui.nct_dialog import NctCalculationDialog
from geoworkbench.ui.new_las_dialog import NewLasDialog
from geoworkbench.ui.las_table_editor import LasTableEditor
from geoworkbench.ui.las_export_dialog import LasExportPlanDialog
from geoworkbench.ui.las_editor_dialog import LasEditorDialog, LasEditorOperation
from geoworkbench.ui.las_curve_browser import LasCurveBrowser
from geoworkbench.ui.print_center_dialog import PrintCenterDialog
from geoworkbench.ui.print_page_dialog import PrintPageDialog
from geoworkbench.ui.masterlog_templates_dialog import MasterlogTemplatesDialog
from geoworkbench.visualization.curve_view import CurveView
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis
from geoworkbench.services.las_parameter_resolver import ParameterResolutionError
from geoworkbench.services.localization import (
    LANGUAGE_NAMES,
    AppLanguage,
    LanguageSettings,
    Localizer,
)
from geoworkbench.services.parameter_labels import localized_curve_name
from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic
from geoworkbench.services.dataset_selection import DatasetIntervalSelection
from geoworkbench.services.user_profiles import CursorLineSettings, UserProfileSettings
from geoworkbench.services.mnemonic_registry import UserMnemonicRegistry


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        language: AppLanguage = AppLanguage.RU,
        language_settings: LanguageSettings | None = None,
        user_profile_settings: UserProfileSettings | None = None,
    ) -> None:
        super().__init__()
        self.language = language
        self.localizer = Localizer.create(language)
        self.language_settings = language_settings or LanguageSettings.system()
        self.user_profile_settings = user_profile_settings or UserProfileSettings.system()
        self.mnemonic_registry = UserMnemonicRegistry()
        forms_root = (
            Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
            / "forms"
        )
        self.form_repository = FormRepository(forms_root)
        self.form_apply_engine = FormApplyEngine()
        set_active_sensor_catalog(self.mnemonic_registry.catalog())
        self.project_controller = ProjectController()
        self.tablet_controller = TabletController(self.session)
        self.curve_editing_controller = CurveEditingController(self.session)
        self.dataset_export_controller = DatasetExportController(self.session)
        self.dataset_merge_controller = DatasetMergeController(self.session)
        self.data_inspector_controller = DataInspectorController(self.session)
        self.header_editing_controller = HeaderEditingController(self.session)
        self.curve_metadata_controller = CurveMetadataController(self.session)
        self.curve_transfer_controller = CurveTransferController(self.session)
        self.external_las_insert_controller = ExternalLasInsertController(self.session)
        self.formula_registry = build_all_sourced_formula_registry()
        self.external_las_insert_controller.formula_registry = self.formula_registry
        self.formula_execution_controller = FormulaExecutionController(
            self.session, self.formula_registry
        )
        self.custom_formula_controller = CustomFormulaController(self.session)
        self.time_depth_mapping_controller = TimeDepthMappingController(self.session)
        self.time_to_depth_controller = TimeToDepthController(self.session)
        self.depth_annotation_controller = DepthAnnotationController(self.session)
        self._selected_annotation_id: str | None = None
        self.lithology_controller = LithologyController(self.session)
        self.cuttings_controller = CuttingsController(self.session)
        self.interpretation_controller = InterpretationController(self.session)
        self.stratigraphy_controller = StratigraphyController(self.session)
        self.stratigraphy_catalog_controller = StratigraphyCatalogController(self.session)
        self.lithotype_catalog_controller = LithotypeCatalogController(self.session)
        self.description_template_controller = DescriptionTemplateController(self.session)
        self.depth_axis_controller = DepthAxisController(self.session)
        self.nct_calculation_controller = NctCalculationController(self.session)
        self.new_las_controller = NewLasController(self.session)
        self.las_range_editing_controller = LasRangeEditingController(self.session)
        self._configure_edit_dependencies()
        self.masterlog_template_controller = MasterlogTemplateController(self.session)
        self.dataset_selection = DatasetIntervalSelection()
        self._selected_track_id: str | None = None
        self._interpretation_dialog: InterpretationIntervalsDialog | None = None
        self.print_page_settings = self.user_profile_settings.print_page_settings()
        self.print_export_preferences = self.user_profile_settings.print_export_preferences()
        self.cursor_line_settings = self.user_profile_settings.cursor_line_settings()
        self.setWindowIcon(application_icon())
        self.setWindowTitle(f"GEOLOG GASRATIO@Pixler {__version__}")
        self.setAcceptDrops(True)
        self._apply_adaptive_initial_geometry()

        self.tabs = QTabWidget()
        self.curve_view = CurveView(self.dataset_selection, language=self.language)
        self.curve_view.edit_requested.connect(self._apply_curve_draw_edit)
        self.tablet_view = TabletView(language=self.language)
        self.tablet_view.set_cursor_style(
            self.cursor_line_settings.color, self.cursor_line_settings.width
        )
        self.tablet_view.track_selected.connect(self._show_track_in_inspector)
        self.tablet_view.curve_selected.connect(self._show_tablet_curve_in_inspector)
        self.tablet_view.track_hide_requested.connect(self._hide_track_from_context)
        self.tablet_view.track_remove_requested.connect(self._remove_track_from_context)
        self.tablet_view.track_add_curves_requested.connect(self._add_curves_to_track_from_context)
        self.tablet_view.track_replace_curves_requested.connect(
            self._replace_track_curves_from_context
        )
        self.tablet_view.track_properties_requested.connect(
            self._show_track_properties_from_context
        )
        self.tablet_view.track_full_edit_requested.connect(self._edit_live_track)
        self.tablet_view.curve_pencil_requested.connect(self._start_curve_pencil_from_tablet)
        self.tablet_view.curve_edit_requested.connect(self._apply_curve_draw_edit)
        self.tablet_view.curve_pencil_mode_changed.connect(self._sync_pencil_action_from_tablet)
        self.tablet_view.curve_pencil_undo_requested.connect(self.undo_curve_edit)
        self.tablet_view.curve_pencil_redo_requested.connect(self.redo_curve_edit)
        self.tablet_view.track_rename_requested.connect(self._rename_live_track)
        self.tablet_view.track_group_rename_requested.connect(self._rename_live_track_group)
        self.tablet_view.track_curve_settings_requested.connect(
            self._show_curve_settings_from_context
        )
        self.tablet_view.save_layout_requested.connect(self.save_tablet_preset)
        self.tablet_view.track_width_change_requested.connect(self._change_track_width_from_drag)
        self.tablet_view.track_order_change_requested.connect(self._track_order_changed_from_drag)
        self.tablet_view.visible_depth_changed.connect(self._show_visible_depth)
        self.tablet_view.vertical_index_changed.connect(self._change_vertical_index_from_tablet)
        self.tablet_view.cursor_changed.connect(self._show_cursor_values)
        self.tablet_view.interpretation_selected.connect(self._select_interpretation_from_tablet)
        self.tablet_view.interval_selected.connect(self._select_interpretation_interval)
        self.tablet_view.interval_selection_cleared.connect(
            self._clear_interpretation_interval_selection
        )
        self.tablet_view.interval_create_requested.connect(self._create_interval_from_tablet)
        self.tablet_view.interval_resize_requested.connect(self._resize_interval_from_tablet)
        self.tablet_view.lithology_interval_requested.connect(
            self._create_lithology_interval_from_tablet
        )
        self.tablet_view.lithology_interval_edit_requested.connect(
            self._edit_lithology_interval_from_tablet
        )
        self.tablet_view.cuttings_interval_requested.connect(
            self._create_cuttings_sample_from_tablet
        )
        self.tablet_view.cuttings_sample_edit_requested.connect(
            self._edit_cuttings_sample_from_tablet
        )
        self.tablet_view.stratigraphy_interval_requested.connect(
            self._create_stratigraphy_interval_from_tablet
        )
        self.tablet_view.stratigraphy_interval_edit_requested.connect(
            self._edit_stratigraphy_interval_from_tablet
        )
        self.tablet_view.annotation_add_requested.connect(
            self._create_annotation_from_tablet
        )
        self.tablet_view.annotation_edit_requested.connect(
            self._edit_annotation_from_tablet
        )
        self.tablet_view.annotation_delete_requested.connect(
            self._delete_annotation_from_tablet
        )
        self.tablet_view.annotation_duplicate_requested.connect(
            self._duplicate_annotation_from_tablet
        )
        self.tablet_view.annotation_geometry_changed.connect(
            self._update_annotation_geometry_from_tablet
        )
        self.tablet_view.annotation_selection_changed.connect(
            self._annotation_selection_changed
        )
        self.tablet_view.annotation_tool_changed.connect(
            self._sync_annotation_tool_actions
        )
        self.tablet_view.curve_value_save_requested.connect(
            self._save_curve_value_annotation
        )
        self.las_table_editor = LasTableEditor(
            self.las_range_editing_controller,
            language=self.language,
            selection=self.dataset_selection,
            number_formats=self.user_profile_settings.table_number_formats(),
        )
        self.las_table_editor.dataset_edited.connect(self._after_table_edit)
        self.las_table_editor.number_formats_changed.connect(self._save_table_number_formats)
        self.las_table_editor.edit_failed.connect(
            lambda message: QMessageBox.warning(self, "LAS Editor", message)
        )
        self.tabs.addTab(self.curve_view, self._t("tab.curves"))
        self.tabs.addTab(self.las_table_editor, self._t("tab.table"))
        self.tabs.addTab(self.tablet_view, self._t("tab.tablet"))
        self.setCentralWidget(self.tabs)

        self._create_project_explorer()
        self._create_curve_browser()
        self._create_inspector()
        self._create_interpretation_properties_panel()
        self._create_issues_panel()
        self._create_cursor_panel()
        self._create_panel_rails()
        self._create_actions()
        self._create_toolbar()
        self.setStatusBar(QStatusBar())
        self._set_tablet_edit_mode(False)
        self.cursor_line_action.setChecked(self.cursor_line_settings.enabled)
        self.statusBar().showMessage(self._t("app.ready"))
        self._update_title()

    def _apply_adaptive_initial_geometry(self) -> None:
        """Fit the first window inside the active laptop/desktop work area."""

        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1280, 800)
            return
        available = screen.availableGeometry()
        width = max(720, min(1580, int(available.width() * 0.96)))
        height = max(540, min(960, int(available.height() * 0.92)))
        self.resize(width, height)
        self.move(
            available.x() + max(0, (available.width() - width) // 2),
            available.y() + max(0, (available.height() - height) // 2),
        )

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _localized_action(self, key: str, *, checkable: bool = False) -> QAction:
        action = QAction(self._t(key), self)
        action.setCheckable(checkable)
        action.setProperty("i18n_key", key)
        return action

    def _set_action_help(self, action: QAction, tooltip_key: str) -> QAction:
        """Attach one localized tooltip/status message to an action."""

        action.setProperty("i18n_tooltip_key", tooltip_key)
        text = self._t(tooltip_key)
        action.setToolTip(text)
        action.setStatusTip(text)
        return action

    def _localized_menu(self, key: str) -> QMenu:
        menu = QMenu(self._t(key), self)
        menu.menuAction().setProperty("i18n_key", key)
        return menu

    def _add_localized_menu(self, key: str) -> QMenu:
        menu = self._localized_menu(key)
        self.menuBar().addMenu(menu)
        return menu

    def _retranslate_registered_actions(self) -> None:
        for action in self.findChildren(QAction):
            text_key = action.property("i18n_key")
            if isinstance(text_key, str) and text_key:
                action.setText(self._t(text_key))
            tooltip_key = action.property("i18n_tooltip_key")
            if isinstance(tooltip_key, str) and tooltip_key:
                translated = self._t(tooltip_key)
                action.setToolTip(translated)
                action.setStatusTip(translated)
            elif not action.isSeparator() and action.text().strip():
                shortcut = action.shortcut().toString()
                translated = action.text().replace("&", "")
                if shortcut:
                    translated = f"{translated} ({shortcut})"
                action.setToolTip(translated)
                action.setStatusTip(translated)

    def _save_table_number_formats(self, formats: object) -> None:
        if not isinstance(formats, dict):
            return
        self.user_profile_settings.save_table_number_formats(formats)

    @property
    def session(self) -> ProjectSession:
        return self.project_controller.session

    @property
    def project_path(self) -> Path | None:
        return self.project_controller.project_path

    def _create_project_explorer(self) -> None:
        self.project_dock = QDockWidget(self._t("dock.project"), self)
        self.project_dock.setObjectName("projectDock")
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(self._t("explorer.title"))
        self.tree.itemDoubleClicked.connect(self._activate_tree_item)
        self.project_dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)
        self.project_dock.hide()
        self._refresh_tree()

    def _create_curve_browser(self) -> None:
        self.curve_browser_dock = QDockWidget(self._t("curve_browser.title"), self)
        self.curve_browser_dock.setObjectName("curveBrowserDock")
        self.curve_browser = LasCurveBrowser(language=self.language)
        self.curve_browser.set_sensor_catalog(self.mnemonic_registry.catalog())
        self.curve_browser.setMinimumWidth(320)
        self.curve_browser.build_requested.connect(self._build_tablet_from_curve_selection)
        self.curve_browser.add_requested.connect(self._add_curves_from_browser)
        self.curve_browser.replace_requested.connect(self._replace_selected_track_curves)
        self.curve_browser_dock.setWidget(self.curve_browser)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.curve_browser_dock)
        self.tabifyDockWidget(self.project_dock, self.curve_browser_dock)
        self.curve_browser_dock.hide()

    def _create_inspector(self) -> None:
        self.inspector_dock = QDockWidget(self._t("dock.inspector"), self)
        self.inspector_dock.setObjectName("inspectorDock")
        self.inspector = TrackInspector(language=self.language)
        self.inspector.collapse_requested.connect(self.inspector_dock.hide)
        self.inspector.settings_requested.connect(self._apply_inspector_track_settings)
        self.inspector.curve_style_requested.connect(self._apply_inspector_curve_style)
        self.inspector.grid_requested.connect(self._apply_inspector_grid)
        self.inspector.x_axis_label_requested.connect(self._apply_inspector_x_axis_label)
        self.inspector_dock.setWidget(self.inspector)
        self.inspector_dock.setMinimumWidth(260)
        self.inspector_dock.setMaximumWidth(420)
        self.inspector_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        self.inspector_dock.hide()

    def _create_interpretation_properties_panel(self) -> None:
        self.interpretation_properties_dock = QDockWidget(
            self._t("interpretations.properties_title"), self
        )
        self.interpretation_properties_dock.setObjectName("interpretationPropertiesDock")
        self.interpretation_properties = InterpretationPropertiesPanel(language=self.language)
        self.interpretation_properties.update_requested.connect(
            self._update_interval_from_properties
        )
        self.interpretation_properties.manager_requested.connect(self.show_interpretation_intervals)
        self.interpretation_properties_dock.setWidget(self.interpretation_properties)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.interpretation_properties_dock
        )
        self.interpretation_properties_dock.hide()

    def _create_issues_panel(self) -> None:
        self.issues_dock = QDockWidget(self._t("dock.log"), self)
        self.issues_dock.setObjectName("issuesDock")
        self.issues = QTextEdit()
        self.issues.setReadOnly(True)
        self.issues_dock.setWidget(self.issues)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.issues_dock)
        self.issues_dock.hide()

    def _create_cursor_panel(self) -> None:
        self.cursor_dock = QDockWidget(self._t("cursor.panel_title"), self)
        self.cursor_dock.setObjectName("cursorDock")
        self.cursor_values = QTextEdit()
        self.cursor_values.setReadOnly(True)
        self.cursor_dock.setWidget(self.cursor_values)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.cursor_dock)
        self.cursor_dock.hide()

    def _create_panel_rails(self) -> None:
        self.tabifyDockWidget(self.project_dock, self.curve_browser_dock)
        self.tabifyDockWidget(self.inspector_dock, self.interpretation_properties_dock)
        self.tabifyDockWidget(self.inspector_dock, self.cursor_dock)

        self.left_panel_rail = QToolBar(self._t("panel.left_rail"), self)
        self.left_panel_rail.setObjectName("leftPanelRail")
        self.left_panel_rail.setMovable(False)
        self.left_panel_rail.setFloatable(False)
        self.left_panel_rail.setIconSize(QSize(20, 20))
        self.left_panel_rail.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.left_panel_rail.setMinimumWidth(34)
        self.left_panel_rail.setMaximumWidth(38)
        self.left_panel_rail.setStyleSheet(
            "QToolBar { spacing: 3px; padding: 3px; border: 0; } "
            "QToolButton { min-width: 28px; min-height: 28px; border-radius: 4px; } "
            "QToolButton:hover { background: palette(midlight); } "
            "QToolButton:checked { background: palette(highlight); color: palette(highlighted-text); }"
        )
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.left_panel_rail)

        self.right_panel_rail = QToolBar(self._t("panel.right_rail"), self)
        self.right_panel_rail.setObjectName("rightPanelRail")
        self.right_panel_rail.setMovable(False)
        self.right_panel_rail.setFloatable(False)
        self.right_panel_rail.setIconSize(QSize(20, 20))
        self.right_panel_rail.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.right_panel_rail.setMinimumWidth(34)
        self.right_panel_rail.setMaximumWidth(38)
        self.right_panel_rail.setStyleSheet(self.left_panel_rail.styleSheet())
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.right_panel_rail)

        self.project_panel_action = self._panel_toggle_action(
            self.project_dock,
            "panel.project",
            "panel.project_tooltip",
            QStyle.StandardPixmap.SP_DirHomeIcon,
            "Ctrl+Alt+P",
        )
        self.curve_browser_action = self._panel_toggle_action(
            self.curve_browser_dock,
            "panel.curves",
            "panel.curves_tooltip",
            QStyle.StandardPixmap.SP_FileDialogListView,
            "Ctrl+Alt+C",
        )
        self.inspector_panel_action = self._panel_toggle_action(
            self.inspector_dock,
            "panel.inspector",
            "panel.inspector_tooltip",
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Ctrl+Alt+I",
        )
        self.interpretation_panel_action = self._panel_toggle_action(
            self.interpretation_properties_dock,
            "panel.interpretation",
            "panel.interpretation_tooltip",
            QStyle.StandardPixmap.SP_MessageBoxInformation,
            "Ctrl+Alt+N",
        )
        self.cursor_panel_action = self._panel_toggle_action(
            self.cursor_dock,
            "panel.cursor",
            "panel.cursor_tooltip",
            QStyle.StandardPixmap.SP_ArrowRight,
            "Ctrl+Alt+V",
        )

        self.left_panel_rail.addAction(self.project_panel_action)
        self.left_panel_rail.addAction(self.curve_browser_action)
        self.right_panel_rail.addAction(self.inspector_panel_action)
        self.right_panel_rail.addAction(self.interpretation_panel_action)
        self.right_panel_rail.addAction(self.cursor_panel_action)

        self.project_dock.visibilityChanged.connect(
            lambda visible: self._enforce_single_side_panel(
                visible, self.project_dock, (self.curve_browser_dock,)
            )
        )
        self.curve_browser_dock.visibilityChanged.connect(
            lambda visible: self._enforce_single_side_panel(
                visible, self.curve_browser_dock, (self.project_dock,)
            )
        )
        self.inspector_dock.visibilityChanged.connect(
            lambda visible: self._enforce_single_side_panel(
                visible,
                self.inspector_dock,
                (self.interpretation_properties_dock, self.cursor_dock),
            )
        )
        self.interpretation_properties_dock.visibilityChanged.connect(
            lambda visible: self._enforce_single_side_panel(
                visible,
                self.interpretation_properties_dock,
                (self.inspector_dock, self.cursor_dock),
            )
        )
        self.cursor_dock.visibilityChanged.connect(
            lambda visible: self._enforce_single_side_panel(
                visible,
                self.cursor_dock,
                (self.inspector_dock, self.interpretation_properties_dock),
            )
        )

    def _panel_toggle_action(
        self,
        dock: QDockWidget,
        text_key: str,
        tooltip_key: str,
        icon: QStyle.StandardPixmap,
        shortcut: str,
    ) -> QAction:
        action = dock.toggleViewAction()
        action.setProperty("i18n_key", text_key)
        action.setProperty("i18n_tooltip_key", tooltip_key)
        action.setText(self._t(text_key))
        action.setToolTip(self._t(tooltip_key))
        action.setStatusTip(self._t(tooltip_key))
        action.setIcon(self.style().standardIcon(icon))
        action.setShortcut(shortcut)
        return action

    @staticmethod
    def _enforce_single_side_panel(
        visible: bool, active: QDockWidget, siblings: tuple[QDockWidget, ...]
    ) -> None:
        if not visible or active.isFloating():
            return
        for sibling in siblings:
            if sibling.isVisible() and not sibling.isFloating():
                sibling.hide()

    def _hide_side_panels(self) -> None:
        for dock in (
            self.project_dock,
            self.curve_browser_dock,
            self.inspector_dock,
            self.interpretation_properties_dock,
            self.cursor_dock,
        ):
            dock.hide()

    def _create_actions(self) -> None:
        file_menu = self._add_localized_menu("menu.file")
        edit_menu = self._add_localized_menu("menu.edit")
        tools_menu = self._add_localized_menu("menu.tools")
        las_editor_menu = self._add_localized_menu("menu.las_editor")
        calc_menu = self._add_localized_menu("menu.calculations")
        tablet_menu = self._add_localized_menu("menu.tablet")
        view_menu = self._add_localized_menu("menu.view")
        forms_menu = self._add_localized_menu("forms.menu")
        constructor_menu = self._add_localized_menu("menu.constructor")
        print_menu = self._add_localized_menu("menu.print")
        language_menu = self._add_localized_menu("menu.language")
        help_menu = self._add_localized_menu("menu.help")

        self.las_editor_action = self._localized_action("las_editor.action")
        self.las_editor_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self.las_editor_action.setShortcut("Ctrl+Alt+E")
        self._set_action_help(self.las_editor_action, "ui.help.las_editor")
        self.las_editor_action.triggered.connect(self.show_las_editor)
        las_editor_menu.addAction(self.las_editor_action)
        las_editor_menu.addSeparator()

        self.open_project_action = self._localized_action("shell.open_project")
        self.open_project_action.setShortcut("Ctrl+O")
        self.open_project_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self._set_action_help(self.open_project_action, "ui.help.open_project")
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)

        self.new_las_action = self._localized_action("new_las.action")
        self.new_las_action.setShortcut("Ctrl+N")
        self.new_las_action.triggered.connect(self.create_new_las)
        file_menu.addAction(self.new_las_action)
        las_editor_menu.addAction(self.new_las_action)

        self.open_data_action = self._localized_action("import.universal")
        self.open_data_action.setShortcut("Ctrl+I")
        self.open_data_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self._set_action_help(self.open_data_action, "ui.help.import_data")
        self.open_data_action.triggered.connect(self.open_data)
        file_menu.addAction(self.open_data_action)
        file_menu.addSeparator()

        self.open_action = self._localized_action("shell.import_las")
        self.open_action.setShortcut("Ctrl+L")
        self.open_action.triggered.connect(self.open_las)
        file_menu.addAction(self.open_action)
        las_editor_menu.addAction(self.open_action)

        self.open_csv_action = self._localized_action("shell.import_csv")
        self.open_csv_action.triggered.connect(self.open_csv)
        file_menu.addAction(self.open_csv_action)

        self.open_excel_action = self._localized_action("shell.import_excel")
        self.open_excel_action.triggered.connect(self.open_excel)
        file_menu.addAction(self.open_excel_action)

        self.open_paradox_action = self._localized_action("shell.import_paradox")
        self.open_paradox_action.triggered.connect(lambda: self.open_paradox())
        file_menu.addAction(self.open_paradox_action)

        self.paradox_batch_action = self._localized_action("paradox.batch_action")
        self.paradox_batch_action.triggered.connect(self.open_paradox_batch)
        tools_menu.addAction(self.paradox_batch_action)

        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.language_actions: dict[AppLanguage, QAction] = {}
        for language, name in LANGUAGE_NAMES.items():
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(language is self.language)
            action.triggered.connect(
                lambda checked=False, value=language: self.change_language(value)
            )
            self.language_group.addAction(action)
            self.language_actions[language] = action
            language_menu.addAction(action)
        language_menu.addSeparator()
        self.user_profile_action = self._localized_action("profile.action")
        self.user_profile_action.triggered.connect(self.select_user_profile)
        language_menu.addAction(self.user_profile_action)

        self.save_action = self._localized_action("shell.save_project")
        self.save_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
        self.save_action.setShortcut("Ctrl+S")
        self._set_action_help(self.save_action, "ui.help.save_project")
        self.save_action.triggered.connect(self.save_project)
        file_menu.addAction(self.save_action)

        self.save_as_action = self._localized_action("shell.save_project_as")
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(self.save_as_action)

        self.export_las_action = self._localized_action("shell.export_las")
        self.export_las_action.triggered.connect(self.export_current_las)
        file_menu.addAction(self.export_las_action)
        las_editor_menu.addAction(self.export_las_action)

        export_csv_action = self._localized_action("selection_export.csv_action")
        export_csv_action.triggered.connect(self.export_selected_csv)
        file_menu.addAction(export_csv_action)
        export_excel_action = self._localized_action("selection_export.excel_action")
        export_excel_action.triggered.connect(self.export_selected_excel)
        file_menu.addAction(export_excel_action)
        self.print_center_action = self._localized_action("print_center.action")
        self.print_center_action.setShortcut("Ctrl+P")
        self.print_center_action.triggered.connect(self.open_print_center)
        file_menu.addAction(self.print_center_action)
        print_menu.addAction(self.print_center_action)
        export_png_action = self._localized_action("visual_export.png_action")
        export_png_action.triggered.connect(lambda: self.export_active_visualization("png"))
        file_menu.addAction(export_png_action)
        export_svg_action = self._localized_action("visual_export.svg_action")
        export_svg_action.triggered.connect(lambda: self.export_active_visualization("svg"))
        file_menu.addAction(export_svg_action)
        export_pdf_action = self._localized_action("visual_export.pdf_action")
        export_pdf_action.triggered.connect(lambda: self.export_active_visualization("pdf"))
        file_menu.addAction(export_pdf_action)
        print_preview_action = self._localized_action("print.preview_action")
        print_preview_action.triggered.connect(self.preview_active_visualization)
        file_menu.addAction(print_preview_action)
        page_setup_action = self._localized_action("print.page_setup_action")
        page_setup_action.triggered.connect(self.configure_print_page)
        file_menu.addAction(page_setup_action)
        templates_action = self._localized_action("masterlog_templates.action")
        templates_action.triggered.connect(self.show_masterlog_templates)
        print_menu.addAction(templates_action)
        self.interpretation_report_action = self._localized_action("interpretation_report.action")
        self.interpretation_report_action.triggered.connect(self.show_interpretation_report)
        print_menu.addAction(self.interpretation_report_action)
        file_menu.addSeparator()
        save_export_profile_action = self._localized_action("export_profile.save")
        save_export_profile_action.triggered.connect(self.save_export_profile)
        file_menu.addAction(save_export_profile_action)
        apply_export_profile_action = self._localized_action("export_profile.apply")
        apply_export_profile_action.triggered.connect(self.apply_export_profile)
        file_menu.addAction(apply_export_profile_action)
        delete_export_profile_action = self._localized_action("export_profile.delete")
        delete_export_profile_action.triggered.connect(self.delete_export_profile)
        file_menu.addAction(delete_export_profile_action)
        export_json_action = self._localized_action("json_export.action")
        export_json_action.triggered.connect(self.export_current_json)
        file_menu.addAction(export_json_action)
        export_parquet_action = self._localized_action("parquet_export.action")
        export_parquet_action.triggered.connect(self.export_current_parquet)
        file_menu.addAction(export_parquet_action)

        self.data_inspector_action = self._localized_action("data.action")
        self.data_inspector_action.triggered.connect(self.show_data_inspector)
        file_menu.addAction(self.data_inspector_action)

        self.pencil_action = self._localized_action("shell.curve_pencil")
        pencil_pixmap = QPixmap(24, 24)
        pencil_pixmap.fill(Qt.GlobalColor.transparent)
        pencil_painter = QPainter(pencil_pixmap)
        pencil_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pencil_painter.setPen(
            QPen(
                Qt.GlobalColor.darkGray,
                3,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        pencil_painter.drawLine(4, 20, 19, 5)
        pencil_painter.setPen(
            QPen(
                Qt.GlobalColor.darkYellow,
                5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        pencil_painter.drawLine(7, 18, 18, 7)
        pencil_painter.end()
        self.pencil_action.setIcon(QIcon(pencil_pixmap))
        self.pencil_action.setCheckable(True)
        self.pencil_action.setShortcut("E")
        self.pencil_action.setToolTip(self._t("shell.curve_pencil_tooltip"))
        self.pencil_action.setStatusTip(self._t("shell.curve_pencil_tooltip"))
        self.pencil_action.toggled.connect(self.toggle_curve_edit_mode)
        edit_menu.addAction(self.pencil_action)

        self.cursor_line_action = self._localized_action("cursor.line_action")
        cursor_icon = QPixmap(24, 24)
        cursor_icon.fill(Qt.GlobalColor.transparent)
        icon_painter = QPainter(cursor_icon)
        icon_painter.setPen(QPen(Qt.GlobalColor.red, 3))
        icon_painter.drawLine(2, 12, 22, 12)
        icon_painter.end()
        self.cursor_line_action.setIcon(QIcon(cursor_icon))
        self.cursor_line_action.setCheckable(True)
        self.cursor_line_action.setShortcut("V")
        self.cursor_line_action.toggled.connect(self.toggle_cursor_line)
        edit_menu.addAction(self.cursor_line_action)
        self.cursor_style_action = self._localized_action("cursor.configure_action")
        self.cursor_style_action.triggered.connect(self.configure_cursor_line)
        edit_menu.addAction(self.cursor_style_action)

        self.undo_action = self._localized_action("shell.undo_curve_edit")
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.undo_action.triggered.connect(self.undo_curve_edit)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)

        self.redo_action = self._localized_action("shell.redo_curve_edit")
        self.redo_action.setShortcut("Ctrl+Shift+Z")
        self.redo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.redo_action.triggered.connect(self.redo_curve_edit)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)

        self.annotations_action = self._localized_action("annotations.action")
        self.annotations_action.triggered.connect(self.show_depth_annotations)
        edit_menu.addAction(self.annotations_action)
        self.annotation_manager_toolbar_action = self._localized_action(
            "annotations.toolbar_manage"
        )
        self._set_action_help(
            self.annotation_manager_toolbar_action, "annotations.action"
        )
        self.annotation_manager_toolbar_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self.annotation_manager_toolbar_action.triggered.connect(
            self.show_depth_annotations
        )
        self.annotation_edit_selected_action = self._localized_action(
            "annotations.toolbar_edit_selected"
        )
        self._set_action_help(
            self.annotation_edit_selected_action, "annotations.edit_selected_hint"
        )
        self.annotation_edit_selected_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
        self.annotation_edit_selected_action.setEnabled(False)
        self.annotation_edit_selected_action.triggered.connect(
            self._edit_selected_annotation
        )
        self.annotation_delete_selected_action = self._localized_action(
            "annotations.toolbar_delete_selected"
        )
        self._set_action_help(
            self.annotation_delete_selected_action, "annotations.delete_selected_hint"
        )
        self.annotation_delete_selected_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        self.annotation_delete_selected_action.setEnabled(False)
        self.annotation_delete_selected_action.triggered.connect(
            self._delete_selected_annotation
        )
        self.annotation_callout_action = self._localized_action(
            "annotations.toolbar_callout"
        )
        self._set_action_help(
            self.annotation_callout_action, "annotations.tool_callout_hint"
        )
        self.annotation_callout_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        )
        self.annotation_callout_action.setEnabled(False)
        self.annotation_callout_action.setCheckable(True)
        self.annotation_callout_action.toggled.connect(
            lambda checked: self._toggle_annotation_tool(AnnotationKind.CALLOUT, checked)
        )
        edit_menu.addAction(self.annotation_callout_action)
        self.annotation_comment_action = self._localized_action(
            "annotations.toolbar_comment"
        )
        self._set_action_help(
            self.annotation_comment_action, "annotations.tool_comment_hint"
        )
        self.annotation_comment_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
        self.annotation_comment_action.setEnabled(False)
        self.annotation_comment_action.setCheckable(True)
        self.annotation_comment_action.toggled.connect(
            lambda checked: self._toggle_annotation_tool(AnnotationKind.COMMENT, checked)
        )
        edit_menu.addAction(self.annotation_comment_action)
        self.annotation_image_action = self._localized_action(
            "annotations.toolbar_image"
        )
        self._set_action_help(
            self.annotation_image_action, "annotations.tool_image_hint"
        )
        self.annotation_image_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        )
        self.annotation_image_action.setEnabled(False)
        self.annotation_image_action.setCheckable(True)
        self.annotation_image_action.toggled.connect(
            lambda checked: self._toggle_annotation_tool(AnnotationKind.IMAGE, checked)
        )
        edit_menu.addAction(self.annotation_image_action)

        self.lithology_action = self._localized_action("lithology.action")
        self.lithology_action.triggered.connect(self.show_lithology_editor)
        edit_menu.addAction(self.lithology_action)

        self.stratigraphy_action = self._localized_action("stratigraphy.action")
        self.stratigraphy_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView)
        )
        self.stratigraphy_action.triggered.connect(self.show_stratigraphy_editor)
        edit_menu.addAction(self.stratigraphy_action)
        self.stratigraphy_catalog_action = self._localized_action("stratigraphy.catalog_action")
        self.stratigraphy_catalog_action.triggered.connect(self.show_stratigraphy_catalog)
        edit_menu.addAction(self.stratigraphy_catalog_action)
        self.stratigraphy_mode_action = self._localized_action("stratigraphy.mode")
        self.stratigraphy_mode_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        )
        self.stratigraphy_mode_action.setCheckable(True)
        self.stratigraphy_mode_action.toggled.connect(self.toggle_stratigraphy_input_mode)
        edit_menu.addAction(self.stratigraphy_mode_action)
        self.edit_selected_track_action = self._localized_action("tablet.edit_current_track")
        self.edit_selected_track_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self._set_action_help(self.edit_selected_track_action, "ui.help.edit_track")
        self.edit_selected_track_action.triggered.connect(self.edit_selected_track)
        edit_menu.addAction(self.edit_selected_track_action)

        self.interpretation_intervals_action = self._localized_action("interpretations.action")
        self.interpretation_intervals_action.triggered.connect(self.show_interpretation_intervals)
        edit_menu.addAction(self.interpretation_intervals_action)

        self.lithotype_catalog_action = self._localized_action("catalog.action")
        self.lithotype_catalog_action.triggered.connect(self.show_lithotype_catalog)
        edit_menu.addAction(self.lithotype_catalog_action)

        self.sensor_catalog_action = self._localized_action("sensors.action")
        self.sensor_catalog_action.triggered.connect(self.show_sensor_catalog)
        edit_menu.addAction(self.sensor_catalog_action)

        self.description_templates_action = self._localized_action("templates.action")
        self.description_templates_action.triggered.connect(self.show_description_templates)
        edit_menu.addAction(self.description_templates_action)

        self.normalize_depth_action = self._localized_action("depth.create_copy_action")
        self.normalize_depth_action.triggered.connect(self.create_ascending_depth_copy)
        edit_menu.addAction(self.normalize_depth_action)
        las_editor_menu.addAction(self.normalize_depth_action)
        self.undo_normalize_depth_action = self._localized_action("depth.undo")
        self.undo_normalize_depth_action.triggered.connect(self.undo_ascending_depth_copy)
        self.undo_normalize_depth_action.setEnabled(False)
        edit_menu.addAction(self.undo_normalize_depth_action)
        self.redo_normalize_depth_action = self._localized_action("depth.redo")
        self.redo_normalize_depth_action.triggered.connect(self.redo_ascending_depth_copy)
        self.redo_normalize_depth_action.setEnabled(False)
        edit_menu.addAction(self.redo_normalize_depth_action)

        self.resample_depth_action = self._localized_action("resample.action")
        self.resample_depth_action.triggered.connect(self.create_resampled_depth_copy)
        edit_menu.addAction(self.resample_depth_action)
        las_editor_menu.addAction(self.resample_depth_action)
        self.undo_resample_action = self._localized_action("resample.undo")
        self.undo_resample_action.triggered.connect(self.undo_depth_resample)
        self.undo_resample_action.setEnabled(False)
        edit_menu.addAction(self.undo_resample_action)
        self.redo_resample_action = self._localized_action("resample.redo")
        self.redo_resample_action.triggered.connect(self.redo_depth_resample)
        self.redo_resample_action.setEnabled(False)
        edit_menu.addAction(self.redo_resample_action)

        self.transfer_curves_action = self._localized_action("transfer.action")
        self.transfer_curves_action.triggered.connect(self.show_curve_transfer)
        edit_menu.addAction(self.transfer_curves_action)
        self.undo_transfer_action = self._localized_action("transfer.undo")
        self.undo_transfer_action.triggered.connect(self.undo_curve_transfer)
        self.undo_transfer_action.setEnabled(False)
        edit_menu.addAction(self.undo_transfer_action)
        self.redo_transfer_action = self._localized_action("transfer.redo")
        self.redo_transfer_action.triggered.connect(self.redo_curve_transfer)
        self.redo_transfer_action.setEnabled(False)
        edit_menu.addAction(self.redo_transfer_action)

        self.external_las_insert_action = self._localized_action("external_las.action")
        self.external_las_insert_action.triggered.connect(self.show_external_las_insert)
        edit_menu.addAction(self.external_las_insert_action)
        las_editor_menu.addAction(self.external_las_insert_action)
        self.undo_external_las_insert_action = self._localized_action("external_las.undo")
        self.undo_external_las_insert_action.triggered.connect(self.undo_external_las_insert)
        self.undo_external_las_insert_action.setEnabled(False)
        edit_menu.addAction(self.undo_external_las_insert_action)
        self.redo_external_las_insert_action = self._localized_action("external_las.redo")
        self.redo_external_las_insert_action.triggered.connect(self.redo_external_las_insert)
        self.redo_external_las_insert_action.setEnabled(False)
        edit_menu.addAction(self.redo_external_las_insert_action)

        self.merge_datasets_action = self._localized_action("merge.action")
        self.merge_datasets_action.triggered.connect(self.show_dataset_merge)
        edit_menu.addAction(self.merge_datasets_action)
        las_editor_menu.addAction(self.merge_datasets_action)
        self.undo_merge_action = self._localized_action("merge.undo")
        self.undo_merge_action.triggered.connect(self.undo_dataset_merge)
        self.undo_merge_action.setEnabled(False)
        edit_menu.addAction(self.undo_merge_action)
        self.redo_merge_action = self._localized_action("merge.redo")
        self.redo_merge_action.triggered.connect(self.redo_dataset_merge)
        self.redo_merge_action.setEnabled(False)
        edit_menu.addAction(self.redo_merge_action)

        self.ratio_action = self._localized_action("ratio.action")
        self.ratio_action.triggered.connect(self.calculate_ratios)
        calc_menu.addAction(self.ratio_action)

        self.formula_action = self._localized_action("formula.action")
        self.formula_action.triggered.connect(self.show_formula_profiles)
        calc_menu.addAction(self.formula_action)

        self.custom_formula_action = self._localized_action("shell.custom_formulas")
        self.custom_formula_action.triggered.connect(self.show_custom_formulas)
        calc_menu.addAction(self.custom_formula_action)

        self.time_depth_mapping_action = self._localized_action("time_depth.action")
        self.time_depth_mapping_action.triggered.connect(self.show_time_depth_mapping)
        calc_menu.addAction(self.time_depth_mapping_action)

        self.time_to_depth_action = self._localized_action("time_to_depth.action")
        self.time_to_depth_action.triggered.connect(self.show_time_to_depth_conversion)
        calc_menu.addAction(self.time_to_depth_action)
        self.undo_time_to_depth_action = self._localized_action("time_to_depth.undo")
        self.undo_time_to_depth_action.triggered.connect(self.undo_time_to_depth_conversion)
        self.undo_time_to_depth_action.setEnabled(False)
        edit_menu.addAction(self.undo_time_to_depth_action)
        self.redo_time_to_depth_action = self._localized_action("time_to_depth.redo")
        self.redo_time_to_depth_action.triggered.connect(self.redo_time_to_depth_conversion)
        self.redo_time_to_depth_action.setEnabled(False)
        edit_menu.addAction(self.redo_time_to_depth_action)

        self.nct_action = self._localized_action("nct.action")
        self.nct_action.triggered.connect(self.calculate_nct)
        calc_menu.addAction(self.nct_action)

        self.interval_statistics_action = self._localized_action("statistics.action")
        self.interval_statistics_action.triggered.connect(self.show_interval_statistics)
        calc_menu.addAction(self.interval_statistics_action)

        view_menu.addAction(self.project_panel_action)
        view_menu.addAction(self.curve_browser_action)
        view_menu.addAction(self.inspector_panel_action)
        view_menu.addAction(self.interpretation_panel_action)
        view_menu.addAction(self.cursor_panel_action)
        view_menu.addSeparator()
        self.hide_side_panels_action = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
            self._t("panel.hide_all"),
            self,
        )
        self.hide_side_panels_action.setProperty("i18n_key", "panel.hide_all")
        self.hide_side_panels_action.setProperty("i18n_tooltip_key", "panel.hide_all_tooltip")
        self.hide_side_panels_action.setToolTip(self._t("panel.hide_all_tooltip"))
        self.hide_side_panels_action.setStatusTip(self._t("panel.hide_all_tooltip"))
        self.hide_side_panels_action.setShortcut("Ctrl+Alt+0")
        self.hide_side_panels_action.triggered.connect(self._hide_side_panels)
        view_menu.addAction(self.hide_side_panels_action)

        self.default_tablet_action = self._localized_action("tablet.build_default")
        self.default_tablet_action.triggered.connect(self.build_default_tablet)
        tablet_menu.addAction(self.default_tablet_action)

        tablet_menu.addAction(self.curve_browser_action)

        tablet_menu.addSeparator()
        self.interval_mode_group = QActionGroup(self)
        self.interval_mode_group.setExclusive(True)
        self.interval_select_action = self._localized_action(
            "interpretations.mode_select", checkable=True
        )
        self.interval_select_action.setChecked(True)
        self.interval_select_action.setShortcut("Alt+1")
        self.interval_select_action.triggered.connect(
            lambda: self.set_interval_interaction_mode(IntervalEditMode.SELECT)
        )
        self.interval_mode_group.addAction(self.interval_select_action)
        tablet_menu.addAction(self.interval_select_action)

        self.interval_create_action = self._localized_action(
            "interpretations.mode_create", checkable=True
        )
        self.interval_create_action.setShortcut("Alt+2")
        self.interval_create_action.triggered.connect(
            lambda: self.set_interval_interaction_mode(IntervalEditMode.CREATE)
        )
        self.interval_mode_group.addAction(self.interval_create_action)
        tablet_menu.addAction(self.interval_create_action)

        self.interval_resize_action = self._localized_action(
            "interpretations.mode_resize", checkable=True
        )
        self.interval_resize_action.setShortcut("Alt+3")
        self.interval_resize_action.triggered.connect(
            lambda: self.set_interval_interaction_mode(IntervalEditMode.RESIZE)
        )
        self.interval_mode_group.addAction(self.interval_resize_action)
        tablet_menu.addAction(self.interval_resize_action)

        self.undo_interpretation_action = self._localized_action("interpretations.undo")
        self.undo_interpretation_action.setShortcut("Ctrl+Alt+Z")
        self.undo_interpretation_action.triggered.connect(self.undo_interpretation_edit)
        tablet_menu.addAction(self.undo_interpretation_action)
        self.redo_interpretation_action = self._localized_action("interpretations.redo")
        self.redo_interpretation_action.setShortcut("Ctrl+Alt+Shift+Z")
        self.redo_interpretation_action.triggered.connect(self.redo_interpretation_edit)
        tablet_menu.addAction(self.redo_interpretation_action)
        self._update_interpretation_history_actions()

        self.tablet_edit_mode_action = self._localized_action("ui.tablet_edit_mode", checkable=True)
        self.tablet_edit_mode_action.setShortcut("F4")
        self.tablet_edit_mode_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self._set_action_help(self.tablet_edit_mode_action, "ui.help.tablet_edit_mode")
        self.tablet_edit_mode_action.toggled.connect(self._set_tablet_edit_mode)
        tablet_menu.addAction(self.tablet_edit_mode_action)
        tablet_menu.addSeparator()

        self.save_user_form_action = self._localized_action("ui.save_user_form")
        self.save_user_form_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
        self._set_action_help(self.save_user_form_action, "ui.help.save_user_form")
        self.save_user_form_action.triggered.connect(self.save_current_tablet_as_user_form)
        tablet_menu.addAction(self.save_user_form_action)

        self.save_preset_action = self._localized_action("tablet.preset_save")
        self.save_preset_action.triggered.connect(self.save_tablet_preset)
        tablet_menu.addAction(self.save_preset_action)
        self.apply_preset_action = self._localized_action("tablet.preset_apply")
        self.apply_preset_action.triggered.connect(self.apply_tablet_preset)
        tablet_menu.addAction(self.apply_preset_action)
        self.delete_preset_action = self._localized_action("tablet.preset_delete")
        self.delete_preset_action.triggered.connect(self.delete_tablet_preset)
        tablet_menu.addAction(self.delete_preset_action)

        self.form_manager_action = self._localized_action("forms.manager_action")
        self.form_manager_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView)
        )
        self._set_action_help(self.form_manager_action, "ui.help.form_manager")
        self.form_manager_action.triggered.connect(self.show_form_manager)
        forms_menu.addAction(self.form_manager_action)

        self.constructor_action = self._localized_action("constructor.open")
        self.constructor_action.setShortcut("Ctrl+Shift+K")
        self.constructor_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self._set_action_help(self.constructor_action, "ui.help.constructor")
        self.constructor_action.triggered.connect(self.show_constructor)
        constructor_menu.addAction(self.constructor_action)
        constructor_menu.addAction(self.form_manager_action)
        constructor_templates_action = self._localized_action("masterlog_templates.action")
        constructor_templates_action.triggered.connect(self.show_masterlog_templates)
        constructor_menu.addAction(constructor_templates_action)

        self.lithology_legend_action = self._localized_action("legend.action")
        self.lithology_legend_action.triggered.connect(self.show_lithology_legend)
        tablet_menu.addAction(self.lithology_legend_action)

        add_track_menu = self._localized_menu("tablet.add_track")
        tablet_menu.addMenu(add_track_menu)
        for title_key, kind in (
            ("tablet.track.depth", TrackKind.DEPTH),
            ("tablet.track.gas", TrackKind.GAS),
            ("tablet.track.dexp_nct", TrackKind.DEXP),
            ("tablet.track.lithology", TrackKind.LITHOLOGY),
            ("tablet.track.stratigraphy", TrackKind.STRATIGRAPHY),
            ("tablet.track.interpretation", TrackKind.INTERPRETATION),
            ("tablet.track.cuttings", TrackKind.CUTTINGS),
            ("tablet.track.calcimetry", TrackKind.CALCIMETRY),
            ("tablet.track.lba", TrackKind.LBA),
            ("tablet.track.description", TrackKind.TEXT),
            ("tablet.track.curve", TrackKind.CURVE),
        ):
            action = self._localized_action(title_key)
            action.triggered.connect(lambda _checked=False, value=kind: self.add_track(value))
            add_track_menu.addAction(action)
            if kind is TrackKind.CURVE:
                self.add_curve_track_action = action
                action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                self._set_action_help(action, "ui.help.add_curve_track")

        tablet_menu.addSeparator()
        width_action = self._localized_action("tablet.change_width")
        width_action.triggered.connect(self.change_selected_track_width)
        tablet_menu.addAction(width_action)

        linear_scale_action = self._localized_action("tablet.linear_scale")
        linear_scale_action.triggered.connect(
            lambda: self.set_selected_track_x_scale(XScale.LINEAR)
        )
        tablet_menu.addAction(linear_scale_action)

        log_scale_action = self._localized_action("tablet.log_scale")
        log_scale_action.triggered.connect(
            lambda: self.set_selected_track_x_scale(XScale.LOGARITHMIC)
        )
        tablet_menu.addAction(log_scale_action)

        range_action = self._localized_action("tablet.set_range")
        range_action.triggered.connect(self.change_selected_track_x_range)
        tablet_menu.addAction(range_action)

        auto_range_action = self._localized_action("tablet.auto_range")
        auto_range_action.triggered.connect(self.reset_selected_track_x_range)
        tablet_menu.addAction(auto_range_action)

        depth_range_action = self._localized_action("tablet.set_depth_range")
        depth_range_action.triggered.connect(self.change_visible_depth_range)
        tablet_menu.addAction(depth_range_action)

        full_depth_action = self._localized_action("tablet.full_depth_range")
        full_depth_action.triggered.connect(self.reset_visible_depth_range)
        tablet_menu.addAction(full_depth_action)

        self.move_left_action = self._localized_action("tablet.move_left")
        self.move_left_action.triggered.connect(lambda: self.move_selected_track(-1))
        self._set_action_help(self.move_left_action, "ui.help.move_left")
        tablet_menu.addAction(self.move_left_action)

        self.move_right_action = self._localized_action("tablet.move_right")
        self.move_right_action.triggered.connect(lambda: self.move_selected_track(1))
        self._set_action_help(self.move_right_action, "ui.help.move_right")
        tablet_menu.addAction(self.move_right_action)

        hide_action = self._localized_action("tablet.hide")
        hide_action.triggered.connect(self.hide_selected_track)
        tablet_menu.addAction(hide_action)

        show_all_action = self._localized_action("tablet.show_all")
        show_all_action.triggered.connect(self.show_all_tracks)
        tablet_menu.addAction(show_all_action)

        self.remove_track_action = self._localized_action("tablet.remove")
        self.remove_track_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        self._set_action_help(self.remove_track_action, "ui.help.remove_track")
        self.remove_track_action.triggered.connect(self.remove_selected_track)
        tablet_menu.addAction(self.remove_track_action)

        about_action = self._localized_action("shell.about")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _toolbar_button(
        self,
        toolbar: QToolBar,
        action: QAction,
        *,
        text_beside_icon: bool = True,
    ) -> QToolButton:
        button = QToolButton(toolbar)
        button.setDefaultAction(action)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
        button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            if text_beside_icon
            else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        button.setAutoRaise(False)
        return button

    def _create_toolbar(self) -> None:
        self.main_toolbar = QToolBar(self._t("toolbar.main"), self)
        self.main_toolbar.setObjectName("mainToolbar")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setFloatable(False)
        self.main_toolbar.setIconSize(QSize(20, 20))
        self.main_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.main_toolbar.setStyleSheet(
            "QToolBar#mainToolbar { spacing: 5px; padding: 5px; "
            "border-bottom: 1px solid #cbd5e1; background: #f8fafc; }"
            "QToolBar#mainToolbar QToolButton { min-height: 30px; padding: 3px 8px; "
            "border: 1px solid transparent; border-radius: 6px; }"
            "QToolBar#mainToolbar QToolButton:hover { background: #e2e8f0; "
            "border-color: #cbd5e1; }"
            "QToolBar#mainToolbar QToolButton:checked { background: #dbeafe; "
            "border-color: #60a5fa; color: #1e3a8a; }"
        )

        self.las_editor_button = self._toolbar_button(self.main_toolbar, self.las_editor_action)
        self.form_manager_button = self._toolbar_button(self.main_toolbar, self.form_manager_action)
        self.constructor_button = self._toolbar_button(self.main_toolbar, self.constructor_action)
        # These are ordinary direct buttons. No menu is attached to Form Manager.
        self.main_toolbar.addWidget(self.las_editor_button)
        self.main_toolbar.addWidget(self.form_manager_button)
        self.main_toolbar.addWidget(self.constructor_button)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.open_project_action)
        self.main_toolbar.addAction(self.open_data_action)
        self.main_toolbar.addAction(self.save_action)
        self.main_toolbar.addSeparator()
        # Keep the two high-frequency visual tools visible; the remaining
        # specialist actions stay in their menus and do not overload the bar.
        self.main_toolbar.addAction(self.pencil_action)
        self.main_toolbar.addAction(self.cursor_line_action)

        spacer = QWidget(self.main_toolbar)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.main_toolbar.addWidget(spacer)
        self.edit_mode_button = self._toolbar_button(
            self.main_toolbar, self.tablet_edit_mode_action
        )
        self.main_toolbar.addWidget(self.edit_mode_button)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.main_toolbar)

        self.form_edit_toolbar = QToolBar(self._t("ui.form_edit_toolbar"), self)
        self.form_edit_toolbar.setObjectName("formEditToolbar")
        self.form_edit_toolbar.setMovable(False)
        self.form_edit_toolbar.setFloatable(False)
        self.form_edit_toolbar.setIconSize(QSize(18, 18))
        self.form_edit_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.form_edit_toolbar.setStyleSheet(
            "QToolBar#formEditToolbar { spacing: 4px; padding: 4px 7px; "
            "background: #eff6ff; border-bottom: 1px solid #93c5fd; }"
            "QToolBar#formEditToolbar QToolButton { min-height: 28px; padding: 3px 7px; "
            "border-radius: 5px; }"
            "QToolBar#formEditToolbar QToolButton:hover { background: #dbeafe; }"
        )
        self.form_edit_caption = QLabel(self._t("ui.form_edit_toolbar"))
        self.form_edit_caption.setStyleSheet(
            "font-weight: 700; color: #1e3a8a; padding-right: 8px;"
        )
        self.form_edit_caption.setToolTip(self._t("ui.help.tablet_edit_mode"))
        self.form_edit_toolbar.addWidget(self.form_edit_caption)
        self.form_edit_toolbar.addAction(self.annotation_callout_action)
        self.form_edit_toolbar.addAction(self.annotation_comment_action)
        self.form_edit_toolbar.addAction(self.annotation_image_action)
        self.form_edit_toolbar.addAction(self.annotation_manager_toolbar_action)
        self.form_edit_toolbar.addAction(self.annotation_edit_selected_action)
        self.form_edit_toolbar.addAction(self.annotation_delete_selected_action)
        self.form_edit_toolbar.addSeparator()
        self.form_edit_toolbar.addAction(self.add_curve_track_action)
        self.form_edit_toolbar.addAction(self.edit_selected_track_action)
        self.form_edit_toolbar.addAction(self.move_left_action)
        self.form_edit_toolbar.addAction(self.move_right_action)
        self.form_edit_toolbar.addAction(self.remove_track_action)
        self.form_edit_toolbar.addSeparator()
        self.form_edit_toolbar.addAction(self.save_user_form_action)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.form_edit_toolbar)
        self.form_edit_toolbar.hide()
        # Every action receives at least a localized caption/shortcut tooltip;
        # high-value actions keep their more detailed help text above.
        self._retranslate_registered_actions()

    def toggle_cursor_line(self, enabled: bool) -> None:
        self.tablet_view.set_cursor_enabled(enabled)
        self.cursor_dock.setVisible(enabled)
        self.cursor_line_settings = CursorLineSettings(
            self.cursor_line_settings.color, self.cursor_line_settings.width, enabled
        )
        self.user_profile_settings.save_cursor_line_settings(self.cursor_line_settings)
        if enabled:
            self.tabs.setCurrentWidget(self.tablet_view)
        else:
            self.statusBar().clearMessage()

    def _show_cursor_values(self, depth: float, summary: str) -> None:
        if self.session.current_tablet_layout is not None:
            self.tablet_controller.set_cursor_depth(depth)
        if self.cursor_line_action.isChecked():
            self.statusBar().showMessage(summary)
            self.cursor_values.setPlainText(summary.replace(" | ", "\n"))

    def configure_cursor_line(self) -> None:
        color = QColorDialog.getColor(parent=self, title=self._t("cursor.color_title"))
        if not color.isValid():
            return
        width, accepted = QInputDialog.getDouble(
            self,
            self._t("cursor.width_title"),
            self._t("cursor.width_prompt"),
            2.0,
            0.5,
            10.0,
            1,
        )
        if accepted:
            self.tablet_view.set_cursor_style(color.name(), width)
            self.cursor_line_settings = CursorLineSettings(
                color.name(), width, self.cursor_line_action.isChecked()
            )
            self.user_profile_settings.save_cursor_line_settings(self.cursor_line_settings)

    def open_data(self) -> None:
        importers = {
            "LAS 1.2/2.0": self.open_las,
            "CSV/TXT": self.open_csv,
            "Excel XLS/XLSX/XLSM": self.open_excel,
            "GeoScape / Paradox DB": self.open_paradox,
        }
        selected, accepted = QInputDialog.getItem(
            self,
            self._t("import.title"),
            self._t("import.source_type"),
            list(importers),
            0,
            False,
        )
        if not accepted:
            return
        importer = importers.get(selected)
        if importer is None:
            QMessageBox.warning(self, "Универсальный импорт", "Неизвестный тип источника")
            return
        importer()

    def change_language(self, language: AppLanguage) -> None:
        if language is self.language:
            action = self.language_actions.get(language)
            if action is not None:
                action.setChecked(True)
            return

        self.language = language
        self.localizer = Localizer.create(language)
        self.language_settings.save(language)
        self._retranslate_ui()
        self.statusBar().showMessage(
            self._t(
                "language.changed.message",
                language=LANGUAGE_NAMES[language],
            ),
            5000,
        )

    def _retranslate_ui(self) -> None:
        self.tabs.setTabText(0, self._t("tab.curves"))
        self.tabs.setTabText(1, self._t("tab.table"))
        self.tabs.setTabText(2, self._t("tab.tablet"))

        self.project_dock.setWindowTitle(self._t("dock.project"))
        self.curve_browser_dock.setWindowTitle(self._t("curve_browser.title"))
        self.inspector_dock.setWindowTitle(self._t("dock.inspector"))
        self.interpretation_properties_dock.setWindowTitle(
            self._t("interpretations.properties_title")
        )
        self.issues_dock.setWindowTitle(self._t("dock.log"))
        self.cursor_dock.setWindowTitle(self._t("cursor.panel_title"))
        self.tree.setHeaderLabel(self._t("explorer.title"))
        self.left_panel_rail.setWindowTitle(self._t("panel.left_rail"))
        self.right_panel_rail.setWindowTitle(self._t("panel.right_rail"))
        self.main_toolbar.setWindowTitle(self._t("toolbar.main"))
        self.form_edit_toolbar.setWindowTitle(self._t("ui.form_edit_toolbar"))
        self.form_edit_caption.setText(self._t("ui.form_edit_toolbar"))
        self.form_edit_caption.setToolTip(self._t("ui.help.tablet_edit_mode"))

        self._retranslate_registered_actions()
        for current_language, action in self.language_actions.items():
            action.setChecked(current_language is self.language)

        for widget in (
            self.curve_view,
            self.las_table_editor,
            self.tablet_view,
            self.curve_browser,
            self.inspector,
            self.interpretation_properties,
        ):
            setter = getattr(widget, "set_language", None)
            if callable(setter):
                setter(self.language)

        if self._interpretation_dialog is not None:
            setter = getattr(self._interpretation_dialog, "set_language", None)
            if callable(setter):
                setter(self.language)

        self._refresh_tree()
        self._update_title()

    def select_user_profile(self) -> None:
        profiles = self.user_profile_settings.profiles()
        create_label = self._t("profile.create")
        labels = [f"{item.display_name} — {item.organization}" for item in profiles]
        selected, accepted = QInputDialog.getItem(
            self,
            self._t("profile.title"),
            self._t("profile.select"),
            [*labels, create_label],
            0,
            False,
        )
        if not accepted:
            return
        if selected == create_label:
            name, accepted = QInputDialog.getText(
                self, self._t("profile.title"), self._t("profile.name")
            )
            if not accepted:
                return
            organization, accepted = QInputDialog.getText(
                self, self._t("profile.title"), self._t("profile.organization")
            )
            if not accepted:
                return
            try:
                profile = self.user_profile_settings.create(name, organization)
            except ValueError as exc:
                QMessageBox.warning(self, self._t("profile.title"), str(exc))
                return
        else:
            index = labels.index(selected)
            profile = self.user_profile_settings.select(profiles[index].profile_id)
        self.statusBar().showMessage(self._t("profile.active", name=profile.display_name))
        self.print_page_settings = self.user_profile_settings.print_page_settings()
        self.print_export_preferences = self.user_profile_settings.print_export_preferences()
        self.las_table_editor.set_number_formats(self.user_profile_settings.table_number_formats())

    def open_las(self) -> None:
        mode_labels = {
            "Совместимый — открыть с предупреждениями": LasImportMode.COMPATIBLE,
            "Строгий — блокировать любые предупреждения": LasImportMode.STRICT,
            "Ручная проверка — подтверждать каждый проблемный файл": LasImportMode.MANUAL,
        }
        selected_mode, accepted = QInputDialog.getItem(
            self,
            "Режим импорта LAS",
            "Политика диагностических сообщений",
            list(mode_labels),
            0,
            False,
        )
        if not accepted:
            return
        import_mode = mode_labels[selected_mode]
        filenames, _ = QFileDialog.getOpenFileNames(self, "Открыть LAS", "", "LAS (*.las)")
        if not filenames:
            return
        self._open_las_files(tuple(Path(filename) for filename in filenames), import_mode)

    def _open_generated_las(self, payload: object) -> None:
        paths = tuple(
            Path(item).expanduser().resolve()
            for item in (payload if isinstance(payload, (tuple, list)) else (payload,))
            if item
        )
        if paths:
            self._open_las_files(paths, LasImportMode.COMPATIBLE)

    def _open_las_files(
        self,
        filenames: tuple[Path, ...],
        import_mode: LasImportMode,
    ) -> None:
        last_dataset = None
        last_well = None
        errors: list[str] = []
        descending_files: list[str] = []
        import_warnings: list[str] = []
        for source in filenames:
            filename = str(source)
            try:
                import_result = import_las_with_report(filename)
                decision = evaluate_las_import(import_result.report, import_mode)
                if not decision.accepted:
                    messages = "\n  ".join(issue.message for issue in decision.blocking_issues)
                    raise LasImportError(f"режим {import_mode.value} отклонил файл:\n  {messages}")
                if decision.requires_confirmation:
                    messages = "\n".join(f"• {issue.message}" for issue in decision.review_issues)
                    answer = QMessageBox.question(
                        self,
                        f"Ручная проверка: {source.name}",
                        messages + "\n\nОткрыть файл без автоматического исправления?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if answer is not QMessageBox.StandardButton.Yes:
                        self._log(f"LAS пропущен после ручной проверки: {filename}")
                        continue
                dataset = import_result.dataset
                well = self.session.add_dataset(
                    dataset,
                    source_document=import_result.source_document,
                    import_report=import_result.report,
                    create_new_well=True,
                )
                last_dataset = dataset
                last_well = well
                if (
                    import_mode is LasImportMode.COMPATIBLE
                    and analyze_depth_axis(dataset.depth).direction is DepthDirection.DESCENDING
                ):
                    descending_files.append(source.name)
                report_messages = tuple(
                    issue.message
                    for issue in import_result.report.issues
                    if issue.code != "index-descending"
                    and issue.severity is not LasIssueSeverity.INFO
                )
                if report_messages and import_mode is LasImportMode.COMPATIBLE:
                    import_warnings.append(
                        f"{source.name}:\n  " + "\n  ".join(report_messages)
                    )
                self._log(f"Загружен LAS: {filename}")
            except (OSError, LasImportError) as exc:
                errors.append(f"{source.name}: {exc}")
                self._log(f"ОШИБКА: {filename}: {exc}")

        if last_dataset is None or last_well is None:
            QMessageBox.critical(self, "Ошибка LAS", "\n".join(errors) or "Файлы не загружены")
            return

        # Activate through the common dataset-switch path.  Besides curves and
        # layout it resets every well-scoped overlay (lithology, cuttings,
        # stratigraphy, interpretations and depth annotations).
        self._show_current_dataset()
        self.inspector.setPlainText(
            f"{self._t('inspector.well')}: {last_well.name}\n"
            f"{self._t('inspector.dataset')}: {last_dataset.name}\n"
            f"{self._t('inspector.curves')}: {len(last_dataset.curves)}\n"
            f"{self._t('inspector.samples')}: {len(last_dataset.depth)}\n"
            f"{self._t('inspector.range')}: "
            f"{last_dataset.depth[0]:.2f}–{last_dataset.depth[-1]:.2f}"
        )
        if errors:
            QMessageBox.warning(self, "Часть LAS не загружена", "\n".join(errors))
        if import_warnings:
            QMessageBox.warning(
                self,
                "Диагностика LAS",
                "\n\n".join(import_warnings),
            )
        if descending_files:
            QMessageBox.warning(
                self,
                "Обратный порядок глубины",
                "Глубина записана по убыванию:\n"
                + "\n".join(descending_files)
                + "\n\nОригинал не изменён. Для исправления используйте: "
                "Правка → Создать копию с глубиной по возрастанию.",
            )
        self._refresh_tree()
        self._update_title()
        self.tabs.setCurrentWidget(self.tablet_view)
        self.statusBar().showMessage(f"Загружено LAS-файлов: {len(filenames) - len(errors)}")

    def open_csv(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Импортировать CSV/TXT",
            "",
            "Табличные данные (*.csv *.txt);;CSV (*.csv);;TXT (*.txt)",
        )
        if not filename:
            return
        dialog = CsvImportDialog(Path(filename), self, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            result = import_csv(filename, dialog.import_plan())
            self.session.add_dataset(result.dataset)
        except (CsvImportError, FileNotFoundError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Импорт CSV", str(exc))
            self._log(f"CSV не импортирован: {exc}")
            return
        self._refresh_tree()
        self._show_current_dataset()
        self._update_title()
        self._log(
            f"Импортирован CSV: {filename}; строк: {result.row_count}; "
            f"разделитель: {result.delimiter!r}; кодировка: {result.encoding}"
        )
        self.statusBar().showMessage(f"CSV импортирован: {Path(filename).name}")

    def open_excel(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Импортировать Excel",
            "",
            "Excel (*.xls *.xlsx *.xlsm)",
        )
        if not filename:
            return
        dialog = ExcelImportDialog(Path(filename), self, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            result = import_excel(filename, dialog.import_plan())
            self.session.add_dataset(result.dataset)
        except (ExcelImportError, FileNotFoundError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Импорт Excel", str(exc))
            self._log(f"Excel не импортирован: {exc}")
            return
        self._refresh_tree()
        self._show_current_dataset()
        self._update_title()
        self._log(f"Импортирован Excel: {filename}; строк: {result.row_count}")
        self.statusBar().showMessage(f"Excel импортирован: {Path(filename).name}")

    def open_paradox(self, source: str | Path | None = None) -> None:
        if source is None:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                self._t("paradox.title"),
                "",
                "Paradox DB (*.db *.DB);;All files (*)",
            )
            if not filename:
                return
            selected = Path(filename)
        else:
            selected = Path(source)
        dialog = ParadoxImportDialog(selected, self, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.import_result is None:
            return
        result = dialog.import_result
        self.session.add_dataset(result.dataset, create_new_well=True)
        self._refresh_tree()
        self._show_current_dataset()
        self._update_title()
        self._log(
            self._t(
                "paradox.import_log",
                file=selected.name,
                rows=result.table.rows_read,
                channels=result.imported_channels,
                warnings=len(result.quality.issues),
            )
        )
        self.statusBar().showMessage(
            self._t("paradox.imported", file=selected.name, rows=result.table.rows_read)
        )
        if dialog.requested_action == "save_las":
            self.export_current_las()

    def open_paradox_batch(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            self._t("paradox.batch_title"),
            "",
            "Paradox DB (*.db *.DB)",
        )
        if not filenames:
            return
        dialog = ParadoxBatchDialog(
            tuple(Path(filename) for filename in filenames),
            self,
            language=self.language,
        )
        dialog.open_las_requested.connect(self._open_generated_las)
        dialog.exec()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(Path(url.toLocalFile()).suffix.casefold() == ".db" for url in urls):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if Path(url.toLocalFile()).suffix.casefold() == ".db"
        ]
        if not paths:
            super().dropEvent(event)
            return
        event.acceptProposedAction()
        if len(paths) == 1:
            self.open_paradox(paths[0])
        else:
            dialog = ParadoxBatchDialog(tuple(paths), self, language=self.language)
            dialog.open_las_requested.connect(self._open_generated_las)
            dialog.exec()

    def open_project(self) -> None:
        if self.session.dirty:
            answer = QMessageBox.question(
                self,
                "Открытие проекта",
                "Несохранённые изменения будут потеряны. Продолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект",
            str(self.project_path or Path.cwd()),
            "GeoLog Project (*.geolog.json);;JSON (*.json)",
        )
        if not filename:
            return

        source = Path(filename)
        try:
            self.project_controller.open_project(source)
        except (OSError, ProjectFormatError) as exc:
            QMessageBox.critical(self, "Открытие проекта", str(exc))
            self._log(f"Проект не открыт: {source.name}: {exc}")
            return

        self.tablet_controller.session = self.session
        self.interpretation_controller.session = self.session
        self.interpretation_controller.history.clear()
        self.interpretation_controller.selected_interpretation_id = None
        self.interpretation_controller.selected_interval_id = None
        self.curve_editing_controller = CurveEditingController(self.session)
        self.las_range_editing_controller.session = self.session
        self._configure_edit_dependencies()
        self.dataset_export_controller.session = self.session
        self.dataset_merge_controller.session = self.session
        self.dataset_merge_controller.clear_history()
        self._update_merge_actions()
        self.data_inspector_controller.session = self.session
        self.header_editing_controller.session = self.session
        self.header_editing_controller.clear_history()
        self.curve_metadata_controller.session = self.session
        self.curve_metadata_controller.clear_history()
        self.curve_transfer_controller.session = self.session
        self.curve_transfer_controller.clear_history()
        self._update_transfer_actions()
        self.external_las_insert_controller.session = self.session
        self.external_las_insert_controller.formula_registry = self.formula_registry
        self.external_las_insert_controller.clear_history()
        self._update_external_las_insert_actions()
        self.formula_execution_controller.session = self.session
        self.custom_formula_controller.session = self.session
        self.custom_formula_controller.clear_history()
        self.depth_annotation_controller.session = self.session
        self.depth_annotation_controller.history.clear()
        self.lithology_controller.session = self.session
        self.cuttings_controller.session = self.session
        self.stratigraphy_controller.session = self.session
        self.stratigraphy_catalog_controller.session = self.session
        self.lithotype_catalog_controller.session = self.session
        self.description_template_controller.session = self.session
        self.depth_axis_controller.session = self.session
        self.depth_axis_controller.clear_history()
        self._update_depth_axis_actions()
        self.nct_calculation_controller.session = self.session
        self.new_las_controller.session = self.session
        self.las_range_editing_controller.session = self.session
        self.masterlog_template_controller.session = self.session
        self._update_curve_edit_actions()
        self._selected_track_id = None
        self._refresh_tree()
        self._show_current_dataset()
        self.session.dirty = False
        self._update_title()
        self._log(f"Проект открыт: {source}")
        self.statusBar().showMessage(f"Проект открыт: {source.name}")

    def _show_current_dataset(self) -> None:
        if hasattr(self, "pencil_action"):
            self.pencil_action.setChecked(False)
        dataset = self.session.current_dataset
        self._update_external_las_insert_actions()
        if dataset is None:
            self.curve_view.clear()
            self.las_table_editor.set_dataset(None)
            self.tablet_view.set_layout_model(TabletLayout())
            self.tablet_view.set_dataset(None)
            self.tablet_view.set_image_assets(self.session.image_assets)
            self.tablet_view.set_canvas_objects([])
            self.tablet_view.set_lithology([], self.lithotype_catalog_controller.available())
            self.tablet_view.set_cuttings([])
            self.tablet_view.set_stratigraphy([])
            self.tablet_view.set_interpretations([])
            self.curve_browser.set_dataset(None)
            self.curve_browser_dock.hide()
            self.interpretation_properties.clear()
            self.interpretation_properties_dock.hide()
            return
        self.curve_view.show_dataset(dataset)
        self.las_table_editor.set_dataset(dataset)
        self.tablet_view.set_dataset(dataset)
        self.tablet_view.set_image_assets(self.session.image_assets)
        self.curve_browser.set_dataset(dataset)
        self.curve_browser.select_recommended()
        self.curve_browser_dock.hide()
        well = self.session.current_well
        self.tablet_view.set_canvas_objects(well.canvas_objects if well is not None else [])
        self.tablet_view.set_lithology(
            well.lithology if well is not None else [],
            self.lithotype_catalog_controller.available(),
        )
        self.tablet_view.set_cuttings(well.cuttings if well is not None else [])
        self.tablet_view.set_stratigraphy(well.stratigraphy if well is not None else [])
        self.interpretation_controller.normalize_selection()
        self.tablet_view.set_interpretations(
            list(well.interpretations.values()) if well is not None else [],
            self.interpretation_controller.selected_interpretation_id,
        )
        selected_interpretation_id = self.interpretation_controller.selected_interpretation_id
        selected_interval_id = self.interpretation_controller.selected_interval_id
        if selected_interpretation_id and selected_interval_id:
            self._select_interpretation_interval(selected_interpretation_id, selected_interval_id)
        else:
            self._clear_interpretation_interval_selection()
        saved_layout = self.session.current_tablet_layout
        if saved_layout is None:
            self.build_default_tablet()
        else:
            self.tablet_view.set_layout_model(saved_layout)
        self.tabs.setCurrentWidget(self.tablet_view)

    def show_las_editor(self) -> None:
        dialog = LasEditorDialog(
            self.session.current_dataset,
            self,
            language=self.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.operation is None:
            return
        operation = dialog.operation
        if operation is LasEditorOperation.CREATE:
            self.create_new_las()
        elif operation is LasEditorOperation.OPEN:
            self.open_las()
        elif operation is LasEditorOperation.TABLE:
            self.tabs.setCurrentWidget(self.las_table_editor)
        elif operation is LasEditorOperation.REVERSE_DEPTH:
            self.create_ascending_depth_copy(save_as_las=True)
        elif operation is LasEditorOperation.RESAMPLE:
            self.create_resampled_depth_copy(save_as_las=True)
        elif operation is LasEditorOperation.INSERT_CURVES:
            self.show_external_las_insert()
        elif operation is LasEditorOperation.MERGE:
            self.show_dataset_merge()
        elif operation is LasEditorOperation.EXPORT_COPY:
            self.export_current_las()

    def create_new_las(self) -> None:
        dialog = NewLasDialog(self, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.plan is None:
            return
        try:
            dataset = self.new_las_controller.create(dialog.plan)
        except ValueError as exc:
            QMessageBox.warning(self, self._t("new_las.title"), str(exc))
            return
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._log(self._t("new_las.created", name=dataset.name))

    def export_current_las(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, self._t("export.title"), self._t("export.select_dataset"))
            return
        plan_dialog = LasExportPlanDialog(
            self,
            initial=self.dataset_export_controller.default_las_plan(),
            language=self.language,
        )
        if plan_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan = plan_dialog.export_plan()
        analysis = self.dataset_export_controller.analyze_current_las_export(plan)
        errors = [
            issue.message
            for issue in analysis.issues
            if issue.severity is ExportIssueSeverity.ERROR
        ]
        if errors:
            QMessageBox.critical(self, self._t("export.blocked"), "\n".join(errors))
            return
        warnings = [
            issue.message
            for issue in analysis.issues
            if issue.severity is ExportIssueSeverity.WARNING
        ]
        if warnings:
            answer = QMessageBox.question(
                self,
                self._t("export.warnings"),
                "\n".join(warnings) + "\n\n" + self._t("export.continue_question"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
        initial = Path.cwd() / f"{dataset.name}_edited.las"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("export.save_title"),
            str(initial),
            "LAS (*.las)",
        )
        if not filename:
            return
        target = Path(filename)
        overwrite = False
        if target.exists():
            answer = QMessageBox.question(
                self,
                self._t("export.title"),
                self._t("export.overwrite_question", name=target.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        try:
            exported = self.dataset_export_controller.export_current_las(
                target,
                overwrite=overwrite,
                plan=plan,
            )
        except (FileExistsError, LasExportError, OSError, RuntimeError) as exc:
            QMessageBox.critical(self, self._t("export.title"), str(exc))
            self._log(f"LAS не экспортирован: {exc}")
            return
        self._log(f"LAS экспортирован: {exported}")
        self.statusBar().showMessage(self._t("export.success", name=exported.name))

    def _export_current_dataset_to_path(self, target: Path) -> Path:
        destination = target if target.suffix.casefold() == ".las" else target.with_suffix(".las")
        overwrite = False
        if destination.exists():
            answer = QMessageBox.question(
                self,
                self._t("export.title"),
                self._t("export.overwrite_question", name=destination.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                raise RuntimeError(self._t("las_editor.save_cancelled"))
            overwrite = True
        plan = self.dataset_export_controller.default_las_plan()
        return self.dataset_export_controller.export_current_las(
            destination,
            overwrite=overwrite,
            plan=plan,
        )

    def _discard_current_derived_dataset(self, restore_dataset_id: str) -> None:
        current = self.session.current_dataset
        well = self.session.current_well
        if current is not None and well is not None and current.dataset_id != restore_dataset_id:
            well.datasets.pop(current.dataset_id, None)
            self.session.tablet_layouts.pop(current.dataset_id, None)
            self.session.source_documents.pop(current.dataset_id, None)
            self.session.import_reports.pop(current.dataset_id, None)
        self.session.current_dataset_id = restore_dataset_id

    def export_selected_csv(self) -> None:
        self._export_selected_table("csv")

    def export_selected_excel(self) -> None:
        self._export_selected_table("xlsx")

    def _export_selected_table(self, export_format: str) -> None:
        dataset = self.session.current_dataset
        selection = self.dataset_selection
        if dataset is None:
            QMessageBox.information(
                self, self._t("selection_export.title"), self._t("export.select_dataset")
            )
            return
        if selection.dataset_id != dataset.dataset_id or selection.interval is None:
            QMessageBox.information(
                self,
                self._t("selection_export.title"),
                self._t("selection_export.select_interval"),
            )
            return
        if not selection.curve_ids:
            QMessageBox.information(
                self,
                self._t("selection_export.title"),
                self._t("selection_export.select_curves"),
            )
            return
        is_excel = export_format == "xlsx"
        suffix = ".xlsx" if is_excel else ".csv"
        file_filter = "Excel (*.xlsx)" if is_excel else "CSV (*.csv)"
        initial = Path.cwd() / f"{dataset.name}_selection{suffix}"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("selection_export.save_title"),
            str(initial),
            file_filter,
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.casefold() != suffix:
            target = target.with_suffix(suffix)
        overwrite = self._confirm_export_overwrite(target)
        if overwrite is None:
            return
        depth_top, depth_bottom = selection.interval
        try:
            if is_excel:
                exported = self.dataset_export_controller.export_current_selection_excel(
                    target,
                    list(selection.curve_ids),
                    depth_top,
                    depth_bottom,
                    overwrite=overwrite,
                    language=self.language,
                )
            else:
                exported = self.dataset_export_controller.export_current_selection_text(
                    target,
                    list(selection.curve_ids),
                    depth_top,
                    depth_bottom,
                    delimiter=",",
                    overwrite=overwrite,
                )
        except (
            FileExistsError,
            KeyError,
            OSError,
            RuntimeError,
            ValueError,
            SelectionExportError,
        ) as exc:
            QMessageBox.critical(self, self._t("selection_export.title"), str(exc))
            self._log(self._t("selection_export.failed", error=str(exc)))
            return
        self._log(self._t("selection_export.success", name=exported.name))
        self.statusBar().showMessage(self._t("selection_export.success", name=exported.name))

    def _confirm_export_overwrite(self, target: Path) -> bool | None:
        if not target.exists():
            return False
        answer = QMessageBox.question(
            self,
            self._t("selection_export.title"),
            self._t("export.overwrite_question", name=target.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return True if answer == QMessageBox.StandardButton.Yes else None

    def open_print_center(
        self,
        _checked: bool = False,
        *,
        widget=None,
        source_name: str | None = None,
    ) -> None:
        current = widget or self.tabs.currentWidget()
        if current not in (self.curve_view, self.tablet_view):
            QMessageBox.information(
                self,
                self._t("print_center.title"),
                self._t("visual_export.select_view"),
            )
            return
        resolved_name = source_name or (
            self._t("print_center.tablet_source")
            if current is self.tablet_view
            else self._t("print_center.curves_source")
        )
        paged_tablet = current if isinstance(current, TabletView) else None
        dialog = PrintCenterDialog(
            self,
            initial_page=self.print_page_settings,
            initial_preferences=self.print_export_preferences,
            language=self.language,
            source_name=resolved_name,
            preview_callback=lambda job: self._preview_print_job(current, job, resolved_name),
            supports_pagination=paged_tablet is not None,
            current_vertical_range=(
                paged_tablet.visible_depth_range if paged_tablet is not None else None
            ),
            full_vertical_range=(
                paged_tablet.printable_vertical_range() if paged_tablet is not None else None
            ),
            vertical_unit=(
                paged_tablet.printable_vertical_unit if paged_tablet is not None else ""
            ),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        job = dialog.job_settings()
        self.print_page_settings = job.page
        self.print_export_preferences = dialog.preferences()
        self.user_profile_settings.save_print_page_settings(job.page)
        self.user_profile_settings.save_print_export_preferences(self.print_export_preferences)
        self._execute_print_job(current, job, resolved_name)

    def _configured_printer(self, widget, job: PrintJobSettings) -> QPrinter:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setResolution(job.dpi)
        printer.setPageSize(job.page.page_size_for_content(widget.width(), widget.height()))
        printer.setPageOrientation(job.page.qt_orientation)
        printer.setPageMargins(job.page.qt_margins, QPageLayout.Unit.Millimeter)
        return printer

    def _preview_print_job(self, widget, job: PrintJobSettings, source_name: str) -> None:
        printer = self._configured_printer(widget, job)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle(self._t("print.preview_title"))
        context = PrintDocumentContext(source_name, self.language)
        preview.paintRequested.connect(
            lambda requested: render_document_to_printer(widget, requested, job, context=context)
        )
        preview.exec()

    def _execute_print_job(self, widget, job: PrintJobSettings, source_name: str) -> None:
        context = PrintDocumentContext(source_name, self.language)
        try:
            if job.output_format is PrintOutputFormat.PRINTER:
                printer = self._configured_printer(widget, job)
                dialog = QPrintDialog(printer, self)
                dialog.setWindowTitle(self._t("print_center.physical_printer"))
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                page_count = render_document_to_printer(widget, printer, job, context=context)
                message = self._t("print_center.print_success_pages", count=page_count)
            else:
                target = job.normalized_target()
                if target is None:
                    raise ValueError(self._t("print_center.choose_file_error"))
                overwrite = self._confirm_print_overwrite(target)
                if overwrite is None:
                    return
                if job.output_format is PrintOutputFormat.PDF:
                    result = export_document_pdf(
                        widget,
                        target,
                        job,
                        context=context,
                        overwrite=overwrite,
                    )
                else:
                    result = export_document_pages(
                        widget,
                        target,
                        job,
                        context=context,
                        overwrite=overwrite,
                    )
                primary = result.primary_path
                name = primary.name if primary is not None else target.name
                message = self._t(
                    "print_center.export_success_pages",
                    name=name,
                    count=result.page_count,
                )
        except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, self._t("print_center.title"), str(exc))
            self._log(self._t("print_center.failed", error=str(exc)))
            return
        self._log(message)
        self.statusBar().showMessage(message)

    def _confirm_print_overwrite(self, target: Path) -> bool | None:
        if not target.exists():
            return False
        answer = QMessageBox.question(
            self,
            self._t("print_center.title"),
            self._t("export.overwrite_question", name=target.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return True if answer == QMessageBox.StandardButton.Yes else None

    def _print_form_from_manager(self, form) -> None:
        self.apply_form_to_tablet(form, mark_dirty=False, notify=False)
        self.open_print_center(widget=self.tablet_view, source_name=form.name)

    def export_active_visualization(self, export_format: str) -> None:
        current = self.tabs.currentWidget()
        if current not in (self.curve_view, self.tablet_view):
            QMessageBox.information(
                self,
                self._t("visual_export.title"),
                self._t("visual_export.select_view"),
            )
            return
        formats = {
            "png": (".png", "PNG (*.png)"),
            "svg": (".svg", "SVG (*.svg)"),
            "pdf": (".pdf", "PDF (*.pdf)"),
        }
        try:
            suffix, file_filter = formats[export_format]
        except KeyError as exc:
            raise ValueError(f"Неподдерживаемый формат визуализации: {export_format}") from exc
        view_name = "tablet" if current is self.tablet_view else "curves"
        target_name = f"{view_name}{suffix}"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("visual_export.save_title"),
            str(Path.cwd() / target_name),
            file_filter,
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.casefold() != suffix:
            target = target.with_suffix(suffix)
        overwrite = self._confirm_export_overwrite(target)
        if overwrite is None:
            return
        try:
            if export_format == "pdf":
                exported = export_widget_pdf(
                    current,
                    target,
                    overwrite=overwrite,
                    page_settings=self.print_page_settings,
                )
            else:
                exporters = {"png": export_widget_png, "svg": export_widget_svg}
                exported = exporters[export_format](current, target, overwrite=overwrite)
        except (FileExistsError, OSError, VisualizationExportError) as exc:
            QMessageBox.critical(self, self._t("visual_export.title"), str(exc))
            self._log(self._t("visual_export.failed", error=str(exc)))
            return
        message = self._t("visual_export.success", name=exported.name)
        self._log(message)
        self.statusBar().showMessage(message)

    def preview_active_visualization(self) -> None:
        current = self.tabs.currentWidget()
        if current not in (self.curve_view, self.tablet_view):
            QMessageBox.information(
                self,
                self._t("print.preview_title"),
                self._t("visual_export.select_view"),
            )
            return
        self._preview_print_job(
            current,
            PrintJobSettings(
                output_format=PrintOutputFormat.PRINTER,
                page=self.print_page_settings,
                dpi=self.print_export_preferences.dpi,
                image_quality=self.print_export_preferences.image_quality,
            ),
        )

    def configure_print_page(self) -> None:
        dialog = PrintPageDialog(
            self,
            initial=self.print_page_settings,
            language=self.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.print_page_settings = dialog.page_settings()
        self.user_profile_settings.save_print_page_settings(self.print_page_settings)
        self.statusBar().showMessage(
            self._t(
                "print.page_updated",
                format=self.print_page_settings.page_format.value.upper(),
                orientation=self._t(f"print.{self.print_page_settings.orientation.value}"),
            )
        )

    def show_masterlog_templates(self) -> None:
        MasterlogTemplatesDialog(
            self.masterlog_template_controller,
            self,
            language=self.language,
        ).exec()
        well = self.session.current_well
        self.tablet_view.set_lithology(
            well.lithology if well is not None else [],
            self.lithotype_catalog_controller.available(),
        )
        self.tablet_view.set_cuttings(well.cuttings if well is not None else [])
        self.tablet_view.set_stratigraphy(well.stratigraphy if well is not None else [])
        self._update_title()

    def save_export_profile(self) -> None:
        dataset = self.session.current_dataset
        selection = self.dataset_selection
        if dataset is None or selection.dataset_id != dataset.dataset_id:
            QMessageBox.information(
                self, self._t("export_profile.title"), self._t("export_profile.select_curves")
            )
            return
        if not selection.curve_ids:
            QMessageBox.information(
                self, self._t("export_profile.title"), self._t("export_profile.select_curves")
            )
            return
        name, accepted = QInputDialog.getText(
            self, self._t("export_profile.save"), self._t("export_profile.name")
        )
        if not accepted:
            return
        try:
            profile = self.dataset_export_controller.save_selection_profile(
                name, list(selection.curve_ids)
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("export_profile.title"), str(exc))
            return
        self._update_title()
        self._log(self._t("export_profile.saved", name=profile.name))

    def apply_export_profile(self) -> None:
        profile_id = self._select_export_profile(self._t("export_profile.apply"))
        if profile_id is None:
            return
        dataset = self.session.current_dataset
        if dataset is None:
            return
        try:
            curve_ids = self.dataset_export_controller.resolve_profile_curve_ids(profile_id)
            interval = (
                self.dataset_selection.interval
                if self.dataset_selection.dataset_id == dataset.dataset_id
                else None
            )
            if interval is None:
                finite_depth = dataset.depth[np.isfinite(dataset.depth)]
                if finite_depth.size == 0:
                    raise ValueError("В наборе нет конечных значений глубины")
                interval = (float(np.min(finite_depth)), float(np.max(finite_depth)))
            self.dataset_selection.select(dataset, *interval, curve_ids)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("export_profile.title"), str(exc))
            return
        profile = self.session.project.export_profiles[profile_id]
        self._log(self._t("export_profile.applied", name=profile.name))

    def delete_export_profile(self) -> None:
        profile_id = self._select_export_profile(self._t("export_profile.delete"))
        if profile_id is None:
            return
        profile = self.session.project.export_profiles[profile_id]
        try:
            self.dataset_export_controller.delete_selection_profile(profile_id)
        except KeyError as exc:
            QMessageBox.warning(self, self._t("export_profile.title"), str(exc))
            return
        self._update_title()
        self._log(self._t("export_profile.deleted", name=profile.name))

    def _select_export_profile(self, title: str) -> str | None:
        profiles = sorted(
            self.session.project.export_profiles.values(),
            key=lambda profile: profile.name.casefold(),
        )
        if not profiles:
            QMessageBox.information(
                self, self._t("export_profile.title"), self._t("export_profile.empty")
            )
            return None
        labels = [profile.name for profile in profiles]
        selected, accepted = QInputDialog.getItem(
            self, title, self._t("export_profile.name"), labels, 0, False
        )
        if not accepted:
            return None
        return next(profile.profile_id for profile in profiles if profile.name == selected)

    def export_current_json(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(
                self, self._t("json_export.title"), self._t("export.select_dataset")
            )
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("json_export.save_title"),
            str(Path.cwd() / f"{dataset.name}.json"),
            "JSON (*.json)",
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.casefold() != ".json":
            target = target.with_suffix(".json")
        overwrite = self._confirm_export_overwrite(target)
        if overwrite is None:
            return
        try:
            exported = self.dataset_export_controller.export_current_json(
                target, overwrite=overwrite
            )
        except (DatasetJsonExportError, FileExistsError, OSError, RuntimeError) as exc:
            QMessageBox.critical(self, self._t("json_export.title"), str(exc))
            self._log(self._t("json_export.failed", error=str(exc)))
            return
        message = self._t("json_export.success", name=exported.name)
        self._log(message)
        self.statusBar().showMessage(message)

    def export_current_parquet(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(
                self, self._t("parquet_export.title"), self._t("export.select_dataset")
            )
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("parquet_export.save_title"),
            str(Path.cwd() / f"{dataset.name}.parquet"),
            "Parquet (*.parquet)",
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.casefold() != ".parquet":
            target = target.with_suffix(".parquet")
        overwrite = self._confirm_export_overwrite(target)
        if overwrite is None:
            return
        try:
            exported = self.dataset_export_controller.export_current_parquet(
                target, overwrite=overwrite
            )
        except (DatasetParquetExportError, FileExistsError, OSError, RuntimeError) as exc:
            QMessageBox.critical(self, self._t("parquet_export.title"), str(exc))
            self._log(self._t("parquet_export.failed", error=str(exc)))
            return
        message = self._t("parquet_export.success", name=exported.name)
        self._log(message)
        self.statusBar().showMessage(message)

    def show_interpretation_report(self) -> None:
        if self.session.current_well is None:
            QMessageBox.information(
                self,
                self._t("interpretation_report.title"),
                self._t("interpretation_report.select_well"),
            )
            return
        InterpretationReportDialog(
            self.session,
            self,
            language=self.language,
        ).exec()

    def show_data_inspector(self) -> None:
        if self.session.current_dataset is None:
            QMessageBox.information(self, self._t("data.title"), self._t("data.select_dataset"))
            return
        DataInspectorDialog(
            self.data_inspector_controller,
            self.header_editing_controller,
            self.curve_metadata_controller,
            self,
            language=self.language,
        ).exec()
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()

    def _configure_edit_dependencies(self) -> None:
        graph = self.formula_registry.build_dependency_graph()
        basic_inputs = ("C1", "C2", "C3", "IC4", "NC4", "C4", "IC5", "NC5", "C5")
        basic_outputs = (
            "C1_C2",
            "C1_C3",
            "C2_C3",
            "C1_C2C3",
            "TG_CALC",
            "C1_REL",
            "C2_REL",
            "C3_REL",
            "IC4_REL",
            "NC4_REL",
            "C4_REL",
            "IC5_REL",
            "NC5_REL",
            "C5_REL",
        )
        for source in basic_inputs:
            for target in basic_outputs:
                try:
                    graph.add_dependency(source, target)
                except ValueError:
                    pass
        self.curve_editing_controller.dependency_graph = graph
        self.curve_editing_controller.formula_registry = self.formula_registry
        self.las_range_editing_controller.formula_registry = self.formula_registry

    def _editable_curve_choices(self) -> list[tuple[str, str]]:
        dataset = self.session.current_dataset
        if dataset is None:
            return []
        choices: list[tuple[str, str]] = []
        for curve in sorted(
            dataset.curves.values(),
            key=lambda item: item.metadata.original_mnemonic.casefold(),
        ):
            provenance = (curve.metadata.provenance or "").strip().casefold()
            if (
                provenance.startswith(("calculation:", "custom-formula:"))
                or provenance == "derived"
            ):
                continue
            mnemonic = curve.metadata.original_mnemonic
            unit = (curve.metadata.unit or "").strip()
            description = (curve.metadata.description or "").strip()
            label = mnemonic
            if unit:
                label += f" [{unit}]"
            if description and description.casefold() != mnemonic.casefold():
                label += f" — {description}"
            choices.append((label, mnemonic))
        return choices

    def _choose_curve_for_pencil(self, preferred: str = "") -> str | None:
        choices = self._editable_curve_choices()
        if not choices:
            QMessageBox.information(
                self,
                self._t("shell.curve_pencil"),
                self._t("shell.curve_pencil_no_curves"),
            )
            return None
        labels = [label for label, _ in choices]
        initial = 0
        for index, (_, mnemonic) in enumerate(choices):
            if mnemonic.casefold() == preferred.casefold():
                initial = index
                break
        selected, accepted = QInputDialog.getItem(
            self,
            self._t("shell.curve_pencil_choose_title"),
            self._t("shell.curve_pencil_choose_prompt"),
            labels,
            initial,
            False,
        )
        if not accepted:
            return None
        for label, mnemonic in choices:
            if label == selected:
                return mnemonic
        return None

    def _activate_curve_pencil(self, mnemonic: str) -> bool:
        dataset = self.session.current_dataset
        if dataset is None:
            return False
        self.tablet_view.set_curve_pencil_mode(False)
        self.curve_view.show_dataset(dataset, [mnemonic])
        self.tabs.setCurrentWidget(self.curve_view)
        if not self.curve_view.set_edit_mode(True):
            return False
        self.statusBar().showMessage(self._t("shell.curve_pencil_active_status", mnemonic=mnemonic))
        return True

    def _activate_tablet_curve_pencil(
        self, mnemonic: str = "", *, track_id: str | None = None
    ) -> bool:
        self.curve_view.set_edit_mode(False)
        activated = (
            self.tablet_view.set_curve_pencil_mode(True, track_id=track_id, mnemonic=mnemonic)
            if track_id and mnemonic
            else self.tablet_view.activate_curve_pencil_for_mnemonic(mnemonic)
            if mnemonic
            else self.tablet_view.set_curve_pencil_mode(True)
        )
        if not activated:
            return False
        target = self.tablet_view.curve_pencil_target
        active_mnemonic = target[1] if target is not None else mnemonic
        self.tabs.setCurrentWidget(self.tablet_view)
        self.statusBar().showMessage(
            self._t("shell.curve_pencil_active_status", mnemonic=active_mnemonic)
        )
        return True

    def _sync_pencil_action_from_tablet(self, enabled: bool, mnemonic: str) -> None:
        self.pencil_action.blockSignals(True)
        self.pencil_action.setChecked(enabled)
        self.pencil_action.blockSignals(False)
        if enabled:
            self.statusBar().showMessage(
                self._t("shell.curve_pencil_active_status", mnemonic=mnemonic)
            )
        else:
            self.statusBar().showMessage(self._t("shell.curve_pencil_inactive_status"), 3000)

    def _start_curve_pencil_from_tablet(self, track_id: str, mnemonic: str) -> None:
        editable = {item_mnemonic for _, item_mnemonic in self._editable_curve_choices()}
        target = mnemonic if mnemonic in editable else self._choose_curve_for_pencil(mnemonic)
        if not target:
            return
        if self._activate_tablet_curve_pencil(target, track_id=track_id):
            self.pencil_action.blockSignals(True)
            self.pencil_action.setChecked(True)
            self.pencil_action.blockSignals(False)

    def toggle_curve_edit_mode(self, enabled: bool) -> None:
        if enabled:
            if self.session.current_dataset is None:
                self.pencil_action.setChecked(False)
                QMessageBox.information(
                    self,
                    self._t("shell.curve_pencil"),
                    self._t("shell.curve_pencil_no_dataset"),
                )
                return
            if self.tabs.currentWidget() is self.tablet_view:
                selected_target = self.tablet_view.selected_curve_pencil_target()
                activated = (
                    self._activate_tablet_curve_pencil(
                        selected_target[1], track_id=selected_target[0]
                    )
                    if selected_target is not None
                    else self._activate_tablet_curve_pencil()
                )
                if not activated:
                    self.pencil_action.blockSignals(True)
                    self.pencil_action.setChecked(False)
                    self.pencil_action.blockSignals(False)
                    QMessageBox.information(
                        self,
                        self._t("shell.curve_pencil"),
                        self._t("tablet.curve_pencil_no_curves"),
                    )
                return
            if self.curve_view.can_edit:
                mnemonic = self.curve_view.editable_mnemonic
            else:
                mnemonic = self._choose_curve_for_pencil()
            if not mnemonic or not self._activate_curve_pencil(mnemonic):
                self.pencil_action.blockSignals(True)
                self.pencil_action.setChecked(False)
                self.pencil_action.blockSignals(False)
                return
        else:
            self.curve_view.set_edit_mode(False)
            self.tablet_view.set_curve_pencil_mode(False)
            self.statusBar().showMessage(self._t("shell.curve_pencil_inactive_status"), 3000)

    def _apply_curve_draw_edit(
        self,
        curve_id: str,
        indices: object,
        new_values: object,
    ) -> None:
        try:
            outcome = self.curve_editing_controller.edit_curve(
                curve_id,
                np.asarray(indices, dtype=np.int64),
                np.asarray(new_values, dtype=np.float64),
                description="Карандаш",
            )
        except (IndexError, KeyError, RuntimeError, ValueError) as exc:
            self.tablet_view.acknowledge_curve_pencil_commit(False, str(exc))
            QMessageBox.warning(self, "Редактор кривой", str(exc))
            return
        self.tablet_view.acknowledge_curve_pencil_commit(True)
        self._after_curve_edit(outcome)

    def undo_curve_edit(self) -> None:
        try:
            outcome = self.curve_editing_controller.undo()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Отмена редактирования", str(exc))
            return
        self._after_curve_edit(outcome)

    def redo_curve_edit(self) -> None:
        try:
            outcome = self.curve_editing_controller.redo()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Повтор редактирования", str(exc))
            return
        self._after_curve_edit(outcome)

    def _after_curve_edit(self, outcome: CurveEditOutcome) -> None:
        dataset = self.session.current_dataset
        if dataset is not None and dataset.dataset_id == outcome.dataset_id:
            tablet_pencil_active = self.tablet_view.curve_pencil_enabled
            self.curve_view.show_dataset(dataset, [outcome.mnemonic])
            self.curve_view.set_edit_mode(
                self.pencil_action.isChecked() and not tablet_pencil_active
            )
            self.tablet_view.set_dataset(dataset)
            self.las_table_editor.set_dataset(dataset)
        self._update_curve_edit_actions()
        self._update_title()
        self.tablet_view.mark_curve_pencil_unsaved()
        recalculated_status = ", ".join(outcome.recalculated_mnemonics) or "—"
        self.statusBar().showMessage(
            self._t(
                "curve_edit.unsaved_status",
                mnemonic=outcome.mnemonic,
                recalculated=recalculated_status,
            )
        )
        affected = ", ".join(outcome.affected_mnemonics) or "нет"
        recalculated = ", ".join(outcome.recalculated_mnemonics) or "нет"
        failed = ", ".join(outcome.failed_mnemonics) or "нет"
        self._log(
            f"{outcome.operation}: {outcome.mnemonic}; зависимые: {affected}; "
            f"пересчитано: {recalculated}; ошибки: {failed}"
        )

    def _after_table_edit(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            return
        self.curve_view.show_dataset(dataset)
        self.tablet_view.set_dataset(dataset)
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage("Значение изменено; газовые производные пересчитаны")

    def _update_curve_edit_actions(self) -> None:
        can_undo = self.curve_editing_controller.history.can_undo
        can_redo = self.curve_editing_controller.history.can_redo
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)
        self.tablet_view.set_curve_pencil_history_state(can_undo, can_redo)

    def _build_tablet_from_curve_selection(self, mnemonics: object) -> None:
        selected = [str(item) for item in mnemonics] if isinstance(mnemonics, list) else []
        if not selected:
            return
        try:
            layout = self.tablet_controller.build_layout_for_curves(selected)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("curve_browser.title"), str(exc))
            return
        self._selected_track_id = None
        self.curve_browser.set_replace_enabled(False)
        self.tablet_view.set_layout_model(layout)
        self.tablet_view.set_dataset(self.session.current_dataset)
        self.tabs.setCurrentWidget(self.tablet_view)
        self.curve_browser_dock.hide()
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage(self._t("curve_browser.built_status", count=len(selected)))

    def _add_curves_from_browser(self, mnemonics: object) -> None:
        selected = [str(item) for item in mnemonics] if isinstance(mnemonics, list) else []
        if not selected:
            return
        try:
            track = self.tablet_controller.add_track(TrackKind.CURVE, selected)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("curve_browser.title"), str(exc))
            return
        self.tablet_view.refresh_view()
        self._show_track_in_inspector(track.track_id)
        self.tabs.setCurrentWidget(self.tablet_view)
        self._refresh_tree()
        self._update_title()

    def _replace_selected_track_curves(self, mnemonics: object) -> None:
        selected = [str(item) for item in mnemonics] if isinstance(mnemonics, list) else []
        if not selected or self._selected_track_id is None:
            return
        try:
            track = self.tablet_controller.replace_track_curves(self._selected_track_id, selected)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("curve_browser.title"), str(exc))
            return
        self.tablet_view.refresh_view()
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))
        self._refresh_tree()
        self._update_title()

    def show_constructor(self) -> None:
        dialog = UniversalConstructorDialog(
            self.masterlog_template_controller,
            self,
            language=self.language,
            open_form_manager=self.show_form_manager,
            open_template_manager=self.show_masterlog_templates,
            import_skf=self._choose_and_import_skf,
        )
        dialog.exec()
        self._refresh_tree()
        self._update_title()

    def show_form_manager(self) -> None:
        dialog = FormManagerDialog(
            self.form_repository,
            self,
            language=self.language.value,
            dataset=self.session.current_dataset,
            preview_callback=lambda form: self.apply_form_to_tablet(
                form, mark_dirty=False, notify=False
            ),
            print_page_settings=self.print_page_settings,
            print_page_settings_changed=self._set_form_print_page_settings,
            print_form_callback=self._print_form_from_manager,
            skf_import_callback=self._import_skf_form_and_header,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_form is None:
            return
        self.apply_form_to_tablet(dialog.selected_form)

    def _choose_and_import_skf(self) -> bool:
        title = {
            AppLanguage.RU: "Импорт формы SKF",
            AppLanguage.KK: "SKF пішінін импорттау",
            AppLanguage.EN: "Import SKF form",
        }.get(self.language, "Импорт формы SKF")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            "Delphi SKF (*.skf);;All files (*)",
        )
        if not filename:
            return False
        try:
            _form, summary = self._import_skf_form_and_header(Path(filename))
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, title, str(exc))
            return False
        QMessageBox.information(self, title, summary)
        self._refresh_tree()
        self._update_title()
        return True

    def _import_skf_form_and_header(self, source: Path):
        result = import_skf_file(source)
        existing_template_names = {
            item.name.casefold() for item in self.session.project.masterlog_templates.values()
        }
        template_name = result.header_template.name
        suffix = 2
        while template_name.casefold() in existing_template_names:
            template_name = f"{result.header_template.name} ({suffix})"
            suffix += 1
        template = self.masterlog_template_controller.import_template(
            result.header_template, result.image_assets, template_name
        )
        form = result.form
        form.print_header_template_id = template.template_id
        existing_form_names = {item.name.casefold() for item in self.form_repository.list_forms()}
        original_name = form.name
        suffix = 2
        while form.name.casefold() in existing_form_names:
            form.name = f"{original_name} ({suffix})"
            suffix += 1
        self.form_repository.save(form)
        warning_text = ""
        if result.report.warnings:
            warning_text = "\n\nПредупреждения:\n- " + "\n- ".join(result.report.warnings)
        summary = (
            f"SKF импортирован: {result.report.source_name}\n"
            f"Компонентов Delphi: {result.report.component_count}\n"
            f"Колонок формы: {result.report.column_count}\n"
            f"Элементов шапки: {result.report.header_element_count}\n"
            f"Изображений: {result.report.image_asset_count}\n"
            f"Форма сохранена: {form.name}\n"
            f"Шапка Masterlog сохранена: {template.name}"
            f"{warning_text}"
        )
        self.session.dirty = True
        return form, summary

    def _set_form_print_page_settings(self, settings) -> None:
        self.print_page_settings = settings
        self.user_profile_settings.save_print_page_settings(settings)
        self.statusBar().showMessage(
            self._t(
                "print.page_updated",
                format=settings.page_format.value.upper(),
                orientation=self._t(f"print.{settings.orientation.value}"),
            )
        )

    def apply_form_to_tablet(self, form, *, mark_dirty: bool = True, notify: bool = True) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, self._t("forms.title"), self._t("forms.open_first"))
            return
        try:
            result = self.form_apply_engine.build_layout(form, dataset)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("forms.title"), str(exc))
            return
        self.session.set_current_tablet_layout(result.layout)
        if mark_dirty:
            self.session.dirty = True
        self.tablet_view.set_layout_model(result.layout)
        self.tablet_view.set_dataset(dataset)
        self.tabs.setCurrentWidget(self.tablet_view)
        self._selected_track_id = None
        self._refresh_tree()
        self._update_title()
        missing_names = ", ".join(item.canonical_parameter_id for item in result.missing)
        message = self._t(
            "forms.applied_status",
            name=form.name,
            resolved=result.resolved_count,
            total=len(result.resolutions),
        )
        if missing_names:
            message += " " + self._t("forms.missing_status", names=missing_names)
        if notify:
            self.statusBar().showMessage(message)
            self._log(message)

    def build_default_tablet(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, self._t("tablet.title"), self._t("tablet.open_first"))
            return

        layout = self.tablet_controller.build_default_layout()
        self.tablet_view.set_layout_model(layout)
        self.tablet_view.set_dataset(dataset)
        self._refresh_tree()
        self._update_title()
        self._log(self._t("tablet.default_built", count=len(layout.tracks)))

    def _set_tablet_edit_mode(self, enabled: bool) -> None:
        """Show or hide form-structure tools without affecting data navigation."""

        enabled = bool(enabled)
        self.form_edit_toolbar.setVisible(enabled)
        self.tablet_view.set_form_edit_mode(enabled)
        self.save_user_form_action.setEnabled(enabled)
        self.add_curve_track_action.setEnabled(enabled)
        self.edit_selected_track_action.setEnabled(enabled)
        self.move_left_action.setEnabled(enabled)
        self.move_right_action.setEnabled(enabled)
        self.remove_track_action.setEnabled(enabled)
        self.annotation_callout_action.setEnabled(enabled)
        self.annotation_comment_action.setEnabled(enabled)
        self.annotation_image_action.setEnabled(enabled)
        if not enabled:
            self.tablet_view.set_annotation_tool(None)
        selected_enabled = enabled and self._selected_annotation_id is not None
        self.annotation_edit_selected_action.setEnabled(selected_enabled)
        self.annotation_delete_selected_action.setEnabled(selected_enabled)
        if not enabled:
            self._selected_annotation_id = None
        self.statusBar().showMessage(
            self._t("ui.form_edit_enabled") if enabled else self._t("ui.form_edit_disabled")
        )

    def save_current_tablet_as_user_form(self) -> None:
        layout = self.session.current_tablet_layout
        dataset = self.session.current_dataset
        if layout is None or dataset is None:
            QMessageBox.information(self, self._t("forms.title"), self._t("tablet.build_first"))
            return
        index = (
            dataset.indexes.get(layout.vertical_index_id)
            if layout.vertical_index_id is not None
            else dataset.active_index
        )
        axis_word = self._t(
            "ui.axis_time"
            if index is not None and index.role is IndexRole.TIME
            else "ui.axis_depth"
        )
        suggested = f"{dataset.name} — {axis_word}"
        name, accepted = QInputDialog.getText(
            self,
            self._t("ui.save_user_form"),
            self._t("tablet.preset_name"),
            text=suggested,
        )
        if not accepted or not name.strip():
            return
        normalized = name.strip()
        existing = next(
            (
                form
                for form in self.form_repository.list_forms()
                if form.name.casefold() == normalized.casefold()
            ),
            None,
        )
        if existing is not None:
            answer = QMessageBox.question(
                self,
                self._t("ui.save_user_form"),
                self._t("ui.replace_user_form", name=existing.name),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            form = form_from_tablet_layout(
                layout,
                dataset,
                normalized,
                description=self._t("ui.saved_from_tablet_description"),
                language=self.language,
            )
            if existing is not None:
                form.form_id = existing.form_id
                form.style_id = existing.style_id
                form.print_header_template_id = existing.print_header_template_id
                form.validate()
            target = self.form_repository.save(form)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("ui.save_user_form"), str(exc))
            return
        self.session.dirty = True
        folder_name = self._t(
            "ui.user_time_forms" if form.axis_kind is FormAxisKind.TIME else "ui.user_depth_forms"
        )
        message = self._t(
            "ui.user_form_saved",
            name=form.name,
            folder=folder_name,
            path=str(target),
        )
        self.statusBar().showMessage(message)
        self._log(message)

    def save_tablet_preset(self) -> None:
        if self.session.current_tablet_layout is None:
            QMessageBox.information(self, self._t("tablet.title"), self._t("tablet.build_first"))
            return
        name, accepted = QInputDialog.getText(
            self, self._t("tablet.preset_save"), self._t("tablet.preset_name")
        )
        if not accepted:
            return
        try:
            self.tablet_controller.save_preset(name)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("tablet.title"), str(exc))
            return
        normalized = name.strip()
        self._update_title()
        self._log(self._t("tablet.preset_saved", name=normalized))

    def apply_tablet_preset(self) -> None:
        name = self._select_tablet_preset(self._t("tablet.preset_apply"))
        if name is None:
            return
        try:
            layout = self.tablet_controller.apply_preset(name)
        except (KeyError, RuntimeError) as exc:
            QMessageBox.warning(self, self._t("tablet.title"), str(exc))
            return
        self._selected_track_id = None
        self.tablet_view.set_layout_model(layout)
        self.tablet_view.set_dataset(self.session.current_dataset)
        self._refresh_tree()
        self._update_title()
        self._log(self._t("tablet.preset_applied", name=name))

    def delete_tablet_preset(self) -> None:
        name = self._select_tablet_preset(self._t("tablet.preset_delete"))
        if name is None:
            return
        try:
            self.tablet_controller.delete_preset(name)
        except KeyError as exc:
            QMessageBox.warning(self, self._t("tablet.title"), str(exc))
            return
        self._update_title()
        self._log(self._t("tablet.preset_deleted", name=name))

    def _select_tablet_preset(self, title: str) -> str | None:
        names = sorted(self.session.tablet_presets, key=str.casefold)
        if not names:
            QMessageBox.information(self, self._t("tablet.title"), self._t("tablet.preset_empty"))
            return None
        name, accepted = QInputDialog.getItem(
            self, title, self._t("tablet.preset_name"), names, 0, False
        )
        return name if accepted else None

    def add_track(self, kind: TrackKind) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, self._t("tablet.title"), self._t("tablet.open_first"))
            return

        mnemonics = self._select_curve_mnemonics() if kind is TrackKind.CURVE else []
        if kind is TrackKind.CURVE and not mnemonics:
            return

        try:
            track = self.tablet_controller.add_track(kind, mnemonics)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("tablet.title"), str(exc))
            return
        self.tablet_view.refresh_view()
        self._refresh_tree()
        self.tabs.setCurrentWidget(self.tablet_view)
        self._log(self._t("tablet.track_added", title=track.title))
        self._update_title()

    def change_selected_track_width(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        width, accepted = QInputDialog.getInt(
            self,
            self._t("tablet.width_title"),
            self._t("tablet.width_prompt"),
            track.width,
            80,
            2000,
            10,
        )
        if accepted:
            self.tablet_controller.set_track_width(track.track_id, width)
            self._layout_changed(self._t("tablet.width_changed", title=track.title, width=width))

    def _change_track_width_from_drag(self, track_id: str, width: int) -> None:
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
            self.tablet_controller.set_track_width(track_id, width)
            self.tablet_view.refresh_track(track_id, DirtyReason.STATIC)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("tablet.width_title"), str(exc))
            self.tablet_view.refresh_view()
            return
        self._refresh_tree()
        self._update_title()
        self._log(self._t("tablet.width_changed", title=track.title, width=width))

    def _track_order_changed_from_drag(self, track_id: str, target_index: int) -> None:
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except KeyError:
            return
        self.session.dirty = True
        self._refresh_tree()
        self._update_title()
        self._log(self._t("tablet.track_moved", title=track.title))

    def move_selected_track(self, offset: int) -> None:
        track = self._selected_track()
        if track is None:
            return
        if self.tablet_controller.move_track(track.track_id, offset):
            self._layout_changed(self._t("tablet.track_moved", title=track.title))

    def set_selected_track_x_scale(self, scale: XScale) -> None:
        track = self._selected_track()
        if track is None:
            return
        try:
            self.tablet_controller.set_track_x_scale(track.track_id, scale)
        except ValueError as exc:
            QMessageBox.warning(self, self._t("tablet.scale_title"), str(exc))
            return
        scale_name = (
            self._t("inspector.logarithmic")
            if scale is XScale.LOGARITHMIC
            else self._t("inspector.linear")
        )
        self._layout_changed(self._t("tablet.scale_changed", title=track.title, scale=scale_name))

    def change_selected_track_x_range(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        default_minimum = track.x_min if track.x_min is not None else 0.1
        default_maximum = track.x_max if track.x_max is not None else 100.0
        minimum, accepted = QInputDialog.getDouble(
            self,
            self._t("tablet.range_title"),
            self._t("tablet.minimum"),
            default_minimum,
            -1e300,
            1e300,
            6,
        )
        if not accepted:
            return
        maximum, accepted = QInputDialog.getDouble(
            self,
            self._t("tablet.range_title"),
            self._t("tablet.maximum"),
            default_maximum,
            -1e300,
            1e300,
            6,
        )
        if not accepted:
            return
        try:
            self.tablet_controller.set_track_x_range(track.track_id, minimum, maximum)
        except ValueError as exc:
            QMessageBox.warning(self, self._t("tablet.range_error_title"), str(exc))
            return
        self._layout_changed(
            self._t(
                "tablet.range_changed",
                title=track.title,
                minimum=f"{minimum:g}",
                maximum=f"{maximum:g}",
            )
        )

    def reset_selected_track_x_range(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        self.tablet_controller.set_track_x_range(track.track_id, None, None)
        self._layout_changed(self._t("tablet.auto_range_set", title=track.title))

    def change_visible_depth_range(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, self._t("tablet.title"), self._t("tablet.open_first"))
            return
        finite_depth = dataset.depth[np.isfinite(dataset.depth)]
        if finite_depth.size < 2:
            QMessageBox.information(self, self._t("tablet.title"), self._t("statistics.no_depth"))
            return
        current = self.tablet_view.visible_depth_range
        default_top = current[0] if current is not None else float(np.min(finite_depth))
        default_bottom = current[1] if current is not None else float(np.max(finite_depth))
        top, accepted = QInputDialog.getDouble(
            self,
            self._t("tablet.depth_range_title"),
            self._t("tablet.depth_top"),
            default_top,
            float(np.min(finite_depth)),
            float(np.max(finite_depth)),
            3,
        )
        if not accepted:
            return
        bottom, accepted = QInputDialog.getDouble(
            self,
            self._t("tablet.depth_range_title"),
            self._t("tablet.depth_bottom"),
            default_bottom,
            float(np.min(finite_depth)),
            float(np.max(finite_depth)),
            3,
        )
        if not accepted:
            return
        try:
            self.tablet_controller.set_visible_depth(top, bottom)
        except ValueError as exc:
            QMessageBox.warning(self, self._t("tablet.depth_range_title"), str(exc))
            return
        self.tablet_view.set_visible_depth(top, bottom)
        self._layout_changed(
            self._t("tablet.depth_range_changed", top=f"{top:g}", bottom=f"{bottom:g}")
        )

    def reset_visible_depth_range(self) -> None:
        if self.session.current_tablet_layout is None:
            QMessageBox.information(self, self._t("tablet.title"), self._t("tablet.build_first"))
            return
        self.tablet_controller.reset_visible_depth()
        self.tablet_view.refresh_view()
        self._layout_changed(self._t("tablet.full_depth_restored"))

    def hide_selected_track(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        self.tablet_controller.hide_track(track.track_id)
        self._selected_track_id = None
        self._layout_changed(self._t("tablet.track_hidden", title=track.title))

    def show_all_tracks(self) -> None:
        restored_count = self.tablet_controller.show_all_tracks()
        if restored_count == 0:
            self.statusBar().showMessage(self._t("tablet.no_hidden"))
            return
        self._layout_changed(self._t("tablet.hidden_shown", count=restored_count))

    def remove_selected_track(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        self.tablet_controller.remove_track(track.track_id)
        self._selected_track_id = None
        self._layout_changed(self._t("tablet.track_removed", title=track.title))

    def _selected_track(self) -> TrackDefinition | None:
        if self._selected_track_id is None:
            QMessageBox.information(self, self._t("tablet.title"), self._t("tablet.select_track"))
            return None
        try:
            return self.tablet_view.layout_model.track_by_id(self._selected_track_id)
        except KeyError:
            self._selected_track_id = None
            return None

    def _layout_changed(self, message: str) -> None:
        self.tablet_view.refresh_view()
        self._refresh_tree()
        self._update_title()
        self._log(message)

    def _select_curve_mnemonics(self, *, preselected: tuple[str, ...] = ()) -> list[str]:
        dataset = self.session.current_dataset
        if dataset is None:
            return []
        dialog = QDialog(self)
        dialog.setWindowTitle(self._t("tablet.select_curves_title"))
        dialog.resize(720, 640)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self._t("tablet.select_curves_prompt")))
        curve_list = QListWidget()
        # Check boxes are the source of truth. A normal click anywhere on a row
        # toggles it, so users do not need Ctrl and do not have to hit the tiny box.
        curve_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        curve_list.setAlternatingRowColors(True)
        selected_set = set(preselected)
        for curve in dataset.curves.values():
            mnemonic = clean_mnemonic(curve.metadata.original_mnemonic)
            unit = clean_display_text(curve.metadata.unit)
            description = clean_display_text(curve.metadata.description)
            readable = localized_curve_name(
                mnemonic,
                description=description,
                unit=unit,
                language=self.language,
            )
            details = f"{readable}  [{mnemonic}]"
            if unit:
                details += f"  ·  {unit}"
            item = QListWidgetItem(details)
            item.setData(Qt.ItemDataRole.UserRole, mnemonic)
            item.setToolTip(
                "\n".join(
                    value
                    for value in (
                        readable,
                        f"{mnemonic}{f' [{unit}]' if unit else ''}",
                        description,
                    )
                    if value
                )
            )
            item.setFlags(
                item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(
                Qt.CheckState.Checked if mnemonic in selected_set else Qt.CheckState.Unchecked
            )
            curve_list.addItem(item)

        pressed_state: dict[int, Qt.CheckState] = {}

        def remember_state(item: QListWidgetItem) -> None:
            pressed_state[id(item)] = item.checkState()

        def toggle_full_row(item: QListWidgetItem) -> None:
            before = pressed_state.pop(id(item), item.checkState())
            # Qt already toggles the checkbox when its indicator was clicked.
            # When the text area was clicked, toggle it here as well.
            if item.checkState() == before:
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if before is Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )

        curve_list.itemPressed.connect(remember_state)
        curve_list.itemClicked.connect(toggle_full_row)
        layout.addWidget(curve_list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("common.cancel"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []
        result: list[str] = []
        for index in range(curve_list.count()):
            item = curve_list.item(index)
            if item is not None and item.checkState() is Qt.CheckState.Checked:
                result.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return result

    def calculate_ratios(self) -> None:
        try:
            created = self.session.calculate_basic_gas_ratios()
        except ParameterResolutionError as exc:
            key = f"ratio.parameter_{exc.code}"
            error = self._t(key, **exc.values) if key in self.localizer.catalog else str(exc)
            QMessageBox.warning(self, self._t("ratio.title"), error)
            self._log(self._t("ratio.failed", error=error))
            return
        except (RuntimeError, KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("ratio.title"), str(exc))
            self._log(self._t("ratio.failed", error=str(exc)))
            return

        dataset = self.session.current_dataset
        assert dataset is not None
        self.curve_view.show_dataset(dataset, created)
        self.tablet_view.set_dataset(dataset)
        self._log(self._t("ratio.curves_updated", curves=", ".join(created)))
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage(self._t("ratio.completed"))

    def show_formula_profiles(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(
                self, self._t("formula.calculation"), self._t("formula.select_dataset")
            )
            return
        dialog = FormulaExecutionDialog(
            dataset,
            self.formula_registry,
            self.formula_execution_controller,
            self,
            language=self.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.execution_result is None:
            return
        result = dialog.execution_result
        passport = self.formula_registry.passport(result.profile_id)
        mapping = dialog.selected_mapping()
        gas_inputs = [
            mapping[name]
            for name in passport.required_inputs
            if passport.input_units[name] == "same concentration unit"
        ]
        visible_curves = list(dict.fromkeys([*gas_inputs, result.output_mnemonic]))
        self.curve_view.show_dataset(dataset, visible_curves)
        self.tablet_view.set_dataset(dataset)
        self._refresh_tree()
        self._update_title()
        self._log(f"Рассчитана кривая {result.output_mnemonic}: {result.profile_id}")
        self.statusBar().showMessage(f"Рассчитана кривая {result.output_mnemonic}")

    def show_time_depth_mapping(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(
                self, self._t("time_depth.action"), self._t("formula.select_dataset")
            )
            return
        TimeDepthMappingDialog(
            dataset,
            self.time_depth_mapping_controller,
            self,
            language=self.language,
        ).exec()
        self._update_title()

    def show_time_to_depth_conversion(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(
                self, self._t("time_to_depth.action"), self._t("formula.select_dataset")
            )
            return
        has_depth = any(index.role is IndexRole.DEPTH for index in dataset.indexes.values())
        has_time = any(index.role is IndexRole.TIME for index in dataset.indexes.values())
        if not has_depth or not has_time:
            QMessageBox.warning(
                self,
                self._t("time_to_depth.action"),
                self._t("time_to_depth.requires_indexes"),
            )
            return
        dialog = TimeToDepthDialog(dataset, self, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.plan is None:
            return
        try:
            result = self.time_to_depth_controller.create_copy(dialog.plan)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, self._t("time_to_depth.action"), str(exc))
            return
        self.undo_time_to_depth_action.setEnabled(True)
        self.redo_time_to_depth_action.setEnabled(False)
        self._refresh_tree()
        self._show_current_dataset()
        self._update_title()
        self._log(
            self._t(
                "time_to_depth.created_log",
                rows=len(result.dataset.depth),
                empty=result.empty_bin_count,
            )
        )
        self.statusBar().showMessage(
            self._t("time_to_depth.created", rows=len(result.dataset.depth))
        )

    def undo_time_to_depth_conversion(self) -> None:
        try:
            self.time_to_depth_controller.undo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("time_to_depth.action"), str(exc))
            return
        self.undo_time_to_depth_action.setEnabled(False)
        self.redo_time_to_depth_action.setEnabled(True)
        self._refresh_tree()
        self._show_current_dataset()
        self._update_title()

    def redo_time_to_depth_conversion(self) -> None:
        try:
            self.time_to_depth_controller.redo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("time_to_depth.action"), str(exc))
            return
        self.undo_time_to_depth_action.setEnabled(True)
        self.redo_time_to_depth_action.setEnabled(False)
        self._refresh_tree()
        self._show_current_dataset()
        self._update_title()

    def show_custom_formulas(self) -> None:
        dialog = CustomFormulaDialog(self.custom_formula_controller, self, language=self.language)
        dialog.exec()
        if not dialog.dataset_changed or self.session.current_dataset is None:
            return
        definition = next(
            (
                item
                for item in self.session.project.custom_formulas.values()
                if item.output_mnemonic == dialog.calculated_mnemonic
            ),
            None,
        )
        inputs = formula_inputs(definition.expression) if definition else ()
        self.curve_view.show_dataset(
            self.session.current_dataset,
            [*inputs, dialog.calculated_mnemonic]
            if dialog.calculated_mnemonic is not None
            else None,
        )
        self.tablet_view.set_dataset(self.session.current_dataset)
        self._refresh_tree()
        self._update_title()

    def show_interval_statistics(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(
                self, self._t("statistics.title"), self._t("statistics.select_dataset")
            )
            return
        visible_range = self.tablet_view.visible_depth_range
        if visible_range is None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size == 0:
                QMessageBox.warning(
                    self, self._t("statistics.title"), self._t("statistics.no_depth")
                )
                return
            depth_top, depth_bottom = float(np.min(finite_depth)), float(np.max(finite_depth))
        else:
            depth_top, depth_bottom = visible_range
        try:
            statistics = calculate_interval_statistics(dataset, depth_top, depth_bottom)
        except ValueError as exc:
            QMessageBox.warning(self, self._t("statistics.title"), str(exc))
            return
        if not statistics:
            QMessageBox.information(
                self, self._t("statistics.title"), self._t("statistics.no_curves")
            )
            return
        IntervalStatisticsDialog(
            depth_top, depth_bottom, statistics, self, language=self.language
        ).exec()

    def calculate_nct(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, self._t("nct.title"), self._t("formula.select_dataset"))
            return
        finite_depth = dataset.depth[np.isfinite(dataset.depth)]
        if finite_depth.size < 2:
            QMessageBox.information(self, self._t("nct.title"), self._t("statistics.no_depth"))
            return
        dialog = NctCalculationDialog(
            self.nct_calculation_controller,
            float(np.min(finite_depth)),
            float(np.max(finite_depth)),
            self,
            language=self.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.calculation_result is None:
            return
        self.curve_view.show_dataset(dataset, ["DEXPC", "NCT", "DEXPC_NCT"])
        self.tablet_view.set_dataset(dataset)
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage(
            self._t("nct.completed", points=dialog.calculation_result.calibration_points)
        )

    def show_depth_annotations(self) -> None:
        if self.session.current_well is None:
            QMessageBox.information(
                self, self._t("annotations.title"), self._t("annotations.select_well")
            )
            return
        self._open_annotation_dialog()

    def _open_annotation_dialog(
        self,
        *,
        initial_values: dict[str, object] | None = None,
        annotation_id: str | None = None,
    ) -> bool:
        """Open the annotation UI and never leave an F4 action silently dead.

        Qt signal callbacks can otherwise print a constructor exception only to
        the console.  The user then sees a toolbar button that appears to do
        nothing.  This UI boundary reports the failure visibly while preserving
        the project and source data.
        """

        try:
            dialog = DepthAnnotationsDialog(
                self.depth_annotation_controller,
                self,
                language=self.language,
                initial_values=initial_values,
                annotation_id=annotation_id,
            )
            dialog.exec()
        except Exception as exc:  # UI boundary: show unexpected plugin/Qt failures.
            QMessageBox.critical(
                self,
                self._t("annotations.title"),
                self._t("annotations.open_failed", error=str(exc)),
            )
            return False
        self._refresh_annotation_layer()
        return True

    def _refresh_annotation_layer(self) -> None:
        """Refresh annotations only, preserving the rendered tablet.

        Annotations intentionally do not live in the project/tree column. There
        is therefore no reason to rebuild the tree or every graph track after an
        annotation CRUD operation. The lightweight TabletView setters reuse the
        existing overlay helpers and selection.
        """

        well = self.session.current_well
        self.tablet_view.set_image_assets(self.session.image_assets)
        self.tablet_view.set_canvas_objects(well.canvas_objects if well is not None else [])
        self._update_title()

    def _toggle_annotation_tool(self, kind: AnnotationKind, checked: bool) -> None:
        if checked:
            actions = {
                AnnotationKind.CALLOUT: self.annotation_callout_action,
                AnnotationKind.COMMENT: self.annotation_comment_action,
                AnnotationKind.IMAGE: self.annotation_image_action,
            }
            for other_kind, action in actions.items():
                if other_kind is not kind and action.isChecked():
                    action.blockSignals(True)
                    action.setChecked(False)
                    action.blockSignals(False)
            self.tablet_view.set_annotation_tool(kind)
            self.statusBar().showMessage(self._t("annotations.tool_click_hint"))
        elif self.tablet_view.annotation_tool is kind:
            self.tablet_view.set_annotation_tool(None)

    def _sync_annotation_tool_actions(self, value: object) -> None:
        active = str(value) if value is not None else ""
        mapping = {
            AnnotationKind.CALLOUT.value: self.annotation_callout_action,
            AnnotationKind.COMMENT.value: self.annotation_comment_action,
            AnnotationKind.IMAGE.value: self.annotation_image_action,
        }
        for kind_value, action in mapping.items():
            should_check = kind_value == active
            if action.isChecked() != should_check:
                action.blockSignals(True)
                action.setChecked(should_check)
                action.blockSignals(False)

    def _create_annotation_at_view_center(self, kind: AnnotationKind) -> None:
        payload = self.tablet_view.annotation_request_at_view_center(
            kind,
            track_id=self._selected_track_id,
        )
        if payload is None:
            QMessageBox.information(
                self, self._t("annotations.title"), self._t("tablet.build_first")
            )
            return
        self._create_annotation_from_tablet(payload)

    def _create_annotation_from_tablet(self, payload: object) -> None:
        if self.session.current_well is None or not isinstance(payload, dict):
            return
        values = dict(payload)
        direct_create = bool(values.pop("direct_create", False))
        if not direct_create:
            self._open_annotation_dialog(initial_values=values)
            return
        try:
            record = self.depth_annotation_controller.add_annotation(**values)
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("annotations.title"), str(exc))
            return
        self._refresh_annotation_layer()
        self.tablet_view.select_annotation(record.annotation_id)
        self._annotation_selection_changed(record.annotation_id)
        self.statusBar().showMessage(self._t("annotations.direct_created_status"))

    def _edit_annotation_from_tablet(self, annotation_id: str) -> None:
        if self.session.current_well is None:
            return
        self._open_annotation_dialog(annotation_id=annotation_id)

    def _delete_annotation_from_tablet(self, annotation_id: str) -> None:
        answer = QMessageBox.question(
            self,
            self._t("annotations.title"),
            self._t("annotations.delete_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.depth_annotation_controller.remove(annotation_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("annotations.title"), str(exc))
            return
        self._refresh_annotation_layer()

    def _duplicate_annotation_from_tablet(self, annotation_id: str) -> None:
        try:
            self.depth_annotation_controller.duplicate(annotation_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("annotations.title"), str(exc))
            return
        self._refresh_annotation_layer()

    def _update_annotation_geometry_from_tablet(
        self,
        annotation_id: str,
        offset_x: float,
        offset_y: float,
        width: float,
        height: float,
    ) -> None:
        try:
            self.depth_annotation_controller.set_geometry(
                annotation_id,
                offset_x=offset_x,
                offset_y=offset_y,
                width=width,
                height=height,
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("annotations.title"), str(exc))
            self._refresh_annotation_layer()
            return
        # The overlay already contains the final drag/resize geometry. Commit
        # one history entry and dirty marker on release, but do not rebuild the
        # tablet or replace the overlay item. This removes the release flash and
        # keeps selection/focus stable.
        self._update_title()

    def _annotation_selection_changed(self, annotation_id: object) -> None:
        selected = annotation_id if isinstance(annotation_id, str) else None
        self._selected_annotation_id = selected
        enabled = selected is not None and self.tablet_view.form_edit_mode
        self.annotation_edit_selected_action.setEnabled(enabled)
        self.annotation_delete_selected_action.setEnabled(enabled)
        if selected is not None:
            self.statusBar().showMessage(self._t("annotations.selected_status"))

    def _edit_selected_annotation(self) -> None:
        annotation_id = self._selected_annotation_id
        if annotation_id is None:
            QMessageBox.information(
                self,
                self._t("annotations.title"),
                self._t("annotations.select_existing"),
            )
            return
        self._edit_annotation_from_tablet(annotation_id)

    def _delete_selected_annotation(self) -> None:
        annotation_id = self._selected_annotation_id
        if annotation_id is None:
            QMessageBox.information(
                self,
                self._t("annotations.title"),
                self._t("annotations.select_existing"),
            )
            return
        self._delete_annotation_from_tablet(annotation_id)

    def _save_curve_value_annotation(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        try:
            self.depth_annotation_controller.add_curve_value(
                track_id=str(payload["track_id"]),
                depth=float(payload["depth"]),
                axis_value=float(payload["axis_value"]),
                axis_id=str(payload["axis_id"]) if payload.get("axis_id") else None,
                mnemonic=str(payload["mnemonic"]),
                value=float(payload["value"]),
                unit=str(payload.get("unit", "")),
                x_fraction=float(payload.get("x_fraction", 0.5)),
                display_text=(
                    str(payload.get("display_value"))
                    if payload.get("display_value")
                    else None
                ),
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("annotations.title"), str(exc))
            return
        self._refresh_annotation_layer()
        self.statusBar().showMessage(self._t("annotations.value_saved"))

    def show_lithology_editor(self) -> None:
        if self.session.current_well is None:
            QMessageBox.information(
                self, self._t("lithology.title"), self._t("lithology.select_well")
            )
            return
        LithologyDialog(
            self.lithology_controller,
            self,
            catalog=self.lithotype_catalog_controller.available(),
            description_templates=self.description_template_controller.available(),
            language=self.language,
        ).exec()
        well = self.session.current_well
        self.tablet_view.set_lithology(
            well.lithology if well is not None else [],
            self.lithotype_catalog_controller.available(),
        )
        self._refresh_tree()
        self._update_title()

    def _create_lithology_interval_from_tablet(self, top_depth: float, bottom_depth: float) -> None:
        if self.session.current_well is None or self.session.current_dataset is None:
            QMessageBox.information(
                self, self._t("lithology.title"), self._t("lithology.select_well")
            )
            return
        catalog = self.lithotype_catalog_controller.available()
        if not catalog:
            QMessageBox.warning(
                self, self._t("lithology.title"), self._t("lithology.quick_no_catalog")
            )
            return
        dialog = LithologyIntervalDialog(
            top_depth,
            bottom_depth,
            catalog,
            language=self.language,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                interval = self.lithology_controller.add(
                    dialog.top_depth,
                    dialog.bottom_depth,
                    dialog.lithotype_id,
                )
            except (RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, self._t("lithology.title"), str(exc))
                continue
            well = self.session.current_well
            self.tablet_view.set_lithology(
                well.lithology if well is not None else [],
                catalog,
            )
            self._refresh_tree()
            self._update_title()
            self.statusBar().showMessage(
                self._t(
                    "lithology.quick_created",
                    top=f"{interval.top_depth:g}",
                    bottom=f"{interval.bottom_depth:g}",
                )
            )
            break

    def _edit_lithology_interval_from_tablet(self, interval_id: str) -> None:
        if self.session.current_well is None:
            return
        try:
            interval = self.lithology_controller.get(interval_id)
        except (KeyError, RuntimeError) as exc:
            QMessageBox.warning(self, self._t("lithology.title"), str(exc))
            return
        catalog = self.lithotype_catalog_controller.available()
        if not catalog:
            QMessageBox.warning(
                self, self._t("lithology.title"), self._t("lithology.quick_no_catalog")
            )
            return
        dialog = LithologyIntervalDialog(
            interval.top_depth,
            interval.bottom_depth,
            catalog,
            language=self.language,
            lithotype_id=interval.lithotype_id,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.delete_requested:
                try:
                    deleted = self.lithology_controller.remove(interval_id)
                except (KeyError, RuntimeError, ValueError) as exc:
                    QMessageBox.warning(self, self._t("lithology.title"), str(exc))
                    continue
                well = self.session.current_well
                self.tablet_view.set_lithology(
                    well.lithology if well is not None else [],
                    catalog,
                )
                self._refresh_tree()
                self._update_title()
                self.statusBar().showMessage(
                    self._t(
                        "lithology.quick_deleted",
                        top=f"{deleted.top_depth:g}",
                        bottom=f"{deleted.bottom_depth:g}",
                    )
                )
                break
            try:
                updated = self.lithology_controller.update(
                    interval_id,
                    top_depth=dialog.top_depth,
                    bottom_depth=dialog.bottom_depth,
                    lithotype_id=dialog.lithotype_id,
                    description=interval.description,
                )
            except (KeyError, RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, self._t("lithology.title"), str(exc))
                continue
            well = self.session.current_well
            self.tablet_view.set_lithology(
                well.lithology if well is not None else [],
                catalog,
            )
            self._refresh_tree()
            self._update_title()
            self.statusBar().showMessage(
                self._t(
                    "lithology.quick_updated",
                    top=f"{updated.top_depth:g}",
                    bottom=f"{updated.bottom_depth:g}",
                )
            )
            break

    def _create_cuttings_sample_from_tablet(self, top_depth: float, bottom_depth: float) -> None:
        """Create one shared sample from a Shift+drag interval.

        The same object feeds cuttings, LBA, calcimetry and rich description
        tracks.  This prevents the four columns from drifting into unrelated
        intervals.
        """
        if self.session.current_well is None:
            return
        catalog = self.lithotype_catalog_controller.available()
        if not catalog:
            QMessageBox.warning(
                self, self._t("cuttings.create_title"), self._t("lithology.quick_no_catalog")
            )
            return
        dialog = UnifiedCuttingsSampleDialog(
            top_depth,
            bottom_depth,
            catalog,
            language=self.language,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                created = self.cuttings_controller.create_full_sample(
                    dialog.top_depth,
                    dialog.bottom_depth,
                    dialog.components(),
                    **dialog.values(),
                )
            except (RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, self._t("cuttings.create_title"), str(exc))
                continue
            self._refresh_cuttings_after_edit()
            self.statusBar().showMessage(
                self._t(
                    "cuttings.created",
                    top=f"{created.top_depth:g}",
                    bottom=f"{created.bottom_depth:g}",
                )
            )
            break

    def _edit_cuttings_sample_from_tablet(self, sample_id: str) -> None:
        """Reopen and atomically edit one existing geological sample."""
        if self.session.current_well is None:
            return
        try:
            sample = self.cuttings_controller.get(sample_id)
        except (KeyError, RuntimeError) as exc:
            QMessageBox.warning(self, self._t("cuttings.edit_title"), str(exc))
            return
        catalog = self.lithotype_catalog_controller.available()
        if not catalog:
            QMessageBox.warning(
                self, self._t("cuttings.edit_title"), self._t("lithology.quick_no_catalog")
            )
            return
        dialog = UnifiedCuttingsSampleDialog(
            sample.top_depth,
            sample.bottom_depth,
            catalog,
            language=self.language,
            sample=sample,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                if dialog.delete_requested:
                    deleted = self.cuttings_controller.remove(sample_id)
                    self._refresh_cuttings_after_edit()
                    self.statusBar().showMessage(
                        self._t(
                            "cuttings.deleted",
                            top=f"{deleted.top_depth:g}",
                            bottom=f"{deleted.bottom_depth:g}",
                        )
                    )
                    break
                updated = self.cuttings_controller.update_full_sample(
                    sample_id,
                    top_depth=dialog.top_depth,
                    bottom_depth=dialog.bottom_depth,
                    components=dialog.components(),
                    **dialog.values(),
                )
            except (KeyError, RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, self._t("cuttings.edit_title"), str(exc))
                continue
            self._refresh_cuttings_after_edit()
            self.statusBar().showMessage(
                self._t(
                    "cuttings.edit_updated",
                    top=f"{updated.top_depth:g}",
                    bottom=f"{updated.bottom_depth:g}",
                )
            )
            break

    def _refresh_cuttings_after_edit(self) -> None:
        well = self.session.current_well
        self.tablet_view.set_cuttings(well.cuttings if well is not None else [])
        self._refresh_tree()
        self._update_title()

    def show_lithotype_catalog(self) -> None:
        LithotypeCatalogDialog(
            self.lithotype_catalog_controller, self, language=self.language
        ).exec()
        well = self.session.current_well
        self.tablet_view.set_lithology(
            well.lithology if well is not None else [],
            self.lithotype_catalog_controller.available(),
        )
        self._update_title()

    def show_stratigraphy_editor(self) -> None:
        if self.session.current_well is None:
            QMessageBox.information(
                self, self._t("stratigraphy.title"), self._t("stratigraphy.select_well")
            )
            return
        StratigraphyDialog(
            self.stratigraphy_controller,
            self,
            language=self.language,
            catalog_controller=self.stratigraphy_catalog_controller,
        ).exec()
        well = self.session.current_well
        self.tablet_view.set_stratigraphy(well.stratigraphy if well is not None else [])
        self._refresh_tree()
        self._update_title()

    def show_stratigraphy_catalog(self) -> None:
        StratigraphyCatalogDialog(
            self.stratigraphy_catalog_controller, self, language=self.language
        ).exec()
        self._update_title()

    def toggle_stratigraphy_input_mode(self, enabled: bool) -> None:
        mode = GeologicalInputMode.STRATIGRAPHY if enabled else GeologicalInputMode.SELECT
        self.tablet_view.set_geological_input_mode(mode)
        if enabled:
            self.tabs.setCurrentWidget(self.tablet_view)
            self.statusBar().showMessage(self._t("stratigraphy.mode_hint"))

    def _create_stratigraphy_interval_from_tablet(self, top: float, bottom: float) -> None:
        if self.session.current_well is None:
            return
        while True:
            dialog = StratigraphyIntervalDialog(
                top,
                bottom,
                self,
                language=self.language,
                catalog_controller=self.stratigraphy_catalog_controller,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                self.stratigraphy_controller.add(**dialog.values())
            except (RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, self._t("stratigraphy.title"), str(exc))
                top, bottom = dialog.top_depth, dialog.bottom_depth
                continue
            self._refresh_stratigraphy_after_edit()
            return

    def _edit_stratigraphy_interval_from_tablet(self, interval_id: str) -> None:
        try:
            interval = self.stratigraphy_controller.get(interval_id)
        except (KeyError, RuntimeError) as exc:
            QMessageBox.warning(self, self._t("stratigraphy.title"), str(exc))
            return
        edit_top = interval.top_depth
        edit_bottom = interval.bottom_depth
        while True:
            dialog = StratigraphyIntervalDialog(
                edit_top,
                edit_bottom,
                self,
                language=self.language,
                catalog_controller=self.stratigraphy_catalog_controller,
            )
            dialog.rank_input.setCurrentText(interval.rank or "")
            dialog.code_input.setText(interval.code)
            dialog.name_input.setText(interval.name or "")
            dialog.color_input.setText(interval.color)
            dialog.description_input.setText(interval.description or "")
            dialog.set_text_presentation(interval.text_orientation, interval.text_position)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                self.stratigraphy_controller.update(interval_id, **dialog.values())
            except (KeyError, RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, self._t("stratigraphy.title"), str(exc))
                edit_top = dialog.top_depth
                edit_bottom = dialog.bottom_depth
                continue
            self._refresh_stratigraphy_after_edit()
            return

    def _refresh_stratigraphy_after_edit(self) -> None:
        well = self.session.current_well
        self.tablet_view.set_stratigraphy(well.stratigraphy if well is not None else [])
        self._refresh_tree()
        self._update_title()

    def set_interval_interaction_mode(self, mode: IntervalEditMode) -> None:
        if mode is not IntervalEditMode.SELECT and not self._ensure_interpretation_for_drawing():
            self.interval_select_action.setChecked(True)
            self.tablet_view.set_interval_edit_mode(IntervalEditMode.SELECT)
            return
        selected = self.interpretation_controller.selected_interval()
        if selected is not None:
            self.tablet_view.set_interval_creation_type(selected.interval_type)
        self.tablet_view.set_interval_edit_mode(mode)
        self.tabs.setCurrentWidget(self.tablet_view)
        action_by_mode = {
            IntervalEditMode.SELECT: self.interval_select_action,
            IntervalEditMode.CREATE: self.interval_create_action,
            IntervalEditMode.RESIZE: self.interval_resize_action,
        }
        action_by_mode[mode].setChecked(True)
        self.statusBar().showMessage(self._t(f"interpretations.mode_{mode.value}_hint"))

    def _ensure_interpretation_for_drawing(self) -> bool:
        if self.session.current_well is None or self.session.current_dataset is None:
            QMessageBox.information(
                self,
                self._t("interpretations.title"),
                self._t("interpretations.drawing_requires_data"),
            )
            return False
        well = self.session.current_well
        if not well.interpretations:
            try:
                self.interpretation_controller.add_interpretation(
                    self._t("interpretations.default_name")
                )
            except (RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
                return False
            self._after_interpretation_change()
        else:
            self.interpretation_controller.normalize_selection()
            self._after_interpretation_change()
        return True

    def _create_interval_from_tablet(
        self, interpretation_id: str, top_depth: float, bottom_depth: float, interval_type: str
    ) -> None:
        try:
            interpretation = self.interpretation_controller.select_interpretation(interpretation_id)
            interval_number = len(interpretation.intervals) + 1
            interval = self.interpretation_controller.add_interval(
                top_depth,
                bottom_depth,
                interval_type or self._t("interpretations.default_type"),
                self._t("interpretations.default_label", number=interval_number),
                color=self._interval_default_color(interval_number),
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
            self._after_interpretation_change()
            return
        self._after_interpretation_change()
        self._select_interpretation_interval(interpretation_id, interval.interval_id)
        self._update_interpretation_history_actions()
        self.statusBar().showMessage(
            self._t(
                "interpretations.created_from_tablet",
                top=f"{interval.top_depth:g}",
                bottom=f"{interval.bottom_depth:g}",
            )
        )

    def _resize_interval_from_tablet(
        self,
        interpretation_id: str,
        interval_id: str,
        top_depth: float,
        bottom_depth: float,
    ) -> None:
        try:
            interval = self.interpretation_controller.select_interval(
                interpretation_id, interval_id
            )
            updated = self.interpretation_controller.update_interval(
                interval_id,
                top_depth=top_depth,
                bottom_depth=bottom_depth,
                interval_type=interval.interval_type,
                label=interval.label,
                color=interval.color,
                comment=interval.comment,
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
            self._after_interpretation_change()
            return
        self._after_interpretation_change()
        self._select_interpretation_interval(interpretation_id, updated.interval_id)
        self._update_interpretation_history_actions()
        self.statusBar().showMessage(
            self._t(
                "interpretations.resized_from_tablet",
                top=f"{updated.top_depth:g}",
                bottom=f"{updated.bottom_depth:g}",
            )
        )

    @staticmethod
    def _interval_default_color(index: int) -> str:
        palette = ("#fde68a", "#bfdbfe", "#bbf7d0", "#fecaca", "#ddd6fe", "#fed7aa")
        return palette[(max(1, index) - 1) % len(palette)]

    def undo_interpretation_edit(self) -> None:
        if not self.interpretation_controller.can_undo:
            return
        try:
            description = self.interpretation_controller.undo()
        except (IndexError, RuntimeError) as exc:
            QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
            return
        self._after_interpretation_change()
        self._update_interpretation_history_actions()
        self.statusBar().showMessage(self._t("interpretations.undo_done", description=description))

    def redo_interpretation_edit(self) -> None:
        if not self.interpretation_controller.can_redo:
            return
        try:
            description = self.interpretation_controller.redo()
        except (IndexError, RuntimeError) as exc:
            QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
            return
        self._after_interpretation_change()
        self._update_interpretation_history_actions()
        self.statusBar().showMessage(self._t("interpretations.redo_done", description=description))

    def _update_interpretation_history_actions(self) -> None:
        if not hasattr(self, "undo_interpretation_action"):
            return
        self.undo_interpretation_action.setEnabled(self.interpretation_controller.can_undo)
        self.redo_interpretation_action.setEnabled(self.interpretation_controller.can_redo)

    def show_interpretation_intervals(self) -> None:
        if self.session.current_well is None:
            QMessageBox.information(
                self,
                self._t("interpretations.title"),
                self._t("interpretations.select_well"),
            )
            return
        dialog = InterpretationIntervalsDialog(
            self.interpretation_controller,
            self,
            language=self.language,
        )
        self._interpretation_dialog = dialog
        dialog.interpretation_selected.connect(self._select_interpretation_from_manager)
        dialog.interval_selected.connect(self._select_interpretation_interval)
        dialog.intervals_changed.connect(self._after_interpretation_change)
        selected_interpretation_id = self.interpretation_controller.selected_interpretation_id
        selected_interval_id = self.interpretation_controller.selected_interval_id
        if selected_interpretation_id and selected_interval_id:
            dialog.select_interval(selected_interpretation_id, selected_interval_id)
        elif selected_interpretation_id:
            dialog.select_interpretation(selected_interpretation_id)
        try:
            dialog.exec()
        finally:
            self._interpretation_dialog = None
        self._after_interpretation_change()

    def _select_interpretation_from_manager(self, interpretation_id: str) -> None:
        try:
            self.interpretation_controller.select_interpretation(interpretation_id)
        except (KeyError, RuntimeError):
            return
        self.tablet_view.set_selected_interpretation(interpretation_id)
        self.interpretation_properties.clear()
        self.interpretation_properties_dock.hide()

    def _select_interpretation_from_tablet(self, interpretation_id: str) -> None:
        self._select_interpretation_from_manager(interpretation_id)
        if self._interpretation_dialog is not None:
            self._interpretation_dialog.select_interpretation(interpretation_id)

    def _select_interpretation_interval(self, interpretation_id: str, interval_id: str) -> None:
        try:
            interval = self.interpretation_controller.select_interval(
                interpretation_id, interval_id
            )
            interpretation = self.interpretation_controller.current_interpretation()
        except (KeyError, RuntimeError):
            self._clear_interpretation_interval_selection()
            return
        self.tablet_view.set_selected_interval(interpretation_id, interval_id)
        self.interpretation_properties.show_interval(interpretation, interval)
        self.interpretation_properties_dock.show()
        self.interpretation_properties_dock.raise_()
        if self._interpretation_dialog is not None:
            self._interpretation_dialog.select_interval(interpretation_id, interval_id)

    def _clear_interpretation_interval_selection(self) -> None:
        self.interpretation_controller.selected_interval_id = None
        self.tablet_view.clear_interval_selection()
        self.interpretation_properties.clear()
        self.interpretation_properties_dock.hide()

    def _update_interval_from_properties(
        self, interpretation_id: str, interval_id: str, values: object
    ) -> None:
        if not isinstance(values, dict):
            return
        try:
            self.interpretation_controller.select_interpretation(interpretation_id)
            interval = self.interpretation_controller.update_interval(
                interval_id,
                top_depth=float(values["top_depth"]),
                bottom_depth=float(values["bottom_depth"]),
                interval_type=str(values["interval_type"]),
                label=str(values["label"]),
                color=str(values["color"]),
                comment=str(values["comment"]),
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
            return
        self._after_interpretation_change()
        self._select_interpretation_interval(interpretation_id, interval.interval_id)
        self.statusBar().showMessage(self._t("interpretations.properties_updated"))

    def _after_interpretation_change(self) -> None:
        well = self.session.current_well
        self.interpretation_controller.normalize_selection()
        layout = self.session.current_tablet_layout
        if (
            well is not None
            and well.interpretations
            and layout is not None
            and not any(track.kind is TrackKind.INTERPRETATION for track in layout.tracks)
        ):
            try:
                self.tablet_controller.add_track(TrackKind.INTERPRETATION)
            except (RuntimeError, ValueError):
                pass
        self.tablet_view.set_interpretations(
            list(well.interpretations.values()) if well is not None else [],
            self.interpretation_controller.selected_interpretation_id,
        )
        selected_interpretation_id = self.interpretation_controller.selected_interpretation_id
        selected_interval_id = self.interpretation_controller.selected_interval_id
        if selected_interpretation_id and selected_interval_id:
            self._select_interpretation_interval(selected_interpretation_id, selected_interval_id)
        else:
            self._clear_interpretation_interval_selection()
        self._refresh_tree()
        self._update_title()
        self._update_interpretation_history_actions()

    def show_sensor_catalog(self) -> None:
        dialog = SensorCatalogDialog(
            self.curve_browser.sensor_catalog,
            self,
            language=self.language,
            registry=self.mnemonic_registry,
        )
        dialog.catalog_changed.connect(self._apply_sensor_catalog)
        dialog.exec()

    def _apply_sensor_catalog(self, catalog: object) -> None:
        if not isinstance(catalog, SensorCatalog):
            return
        set_active_sensor_catalog(catalog)
        self.curve_browser.set_sensor_catalog(catalog)
        self.statusBar().showMessage(self._t("sensors.applied", count=len(catalog.sensors)))

    def show_description_templates(self) -> None:
        DescriptionTemplatesDialog(
            self.description_template_controller, self, language=self.language
        ).exec()
        self._refresh_tree()
        self._update_title()

    def create_ascending_depth_copy(self, *, save_as_las: bool = False) -> None:
        try:
            report = self.depth_axis_controller.analyze_current()
        except RuntimeError as exc:
            QMessageBox.information(self, self._t("depth.title"), str(exc))
            return
        if report.direction is not DepthDirection.DESCENDING:
            QMessageBox.information(
                self,
                self._t("depth.title"),
                self._t(
                    "depth.no_reversal",
                    direction=self._t(f"depth.direction.{report.direction.value}"),
                ),
            )
            return
        answer = QMessageBox.question(
            self,
            self._t("depth.confirm_title"),
            self._t("depth.confirm_message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.depth_axis_controller.create_ascending_copy()
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("depth.title"), str(exc))
            return
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._update_depth_axis_actions()
        self._log(self._t("depth.copy_created", name=result.name))
        if save_as_las:
            self._save_derived_dataset_copy(result, suffix="_ascending")

    def undo_ascending_depth_copy(self) -> None:
        answer = QMessageBox.question(
            self,
            self._t("depth.undo_title"),
            self._t("depth.undo_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.depth_axis_controller.undo_ascending_copy()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("depth.title"), str(exc))
            return
        self._after_depth_axis_history(self._t("depth.undone"))

    def redo_ascending_depth_copy(self) -> None:
        try:
            result = self.depth_axis_controller.redo_ascending_copy()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("depth.title"), str(exc))
            return
        self._after_depth_axis_history(self._t("depth.redone", name=result.name))

    def create_resampled_depth_copy(self, *, save_as_las: bool = False) -> None:
        try:
            dialog = DepthResampleDialog(self.depth_axis_controller, self, language=self.language)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("resample.title"), str(exc))
            return
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.plan is None:
            return
        try:
            result = self.depth_axis_controller.create_resampled_copy(dialog.plan)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("resample.title"), str(exc))
            return
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._update_depth_axis_actions()
        self._log(self._t("resample.created", name=result.name))
        if save_as_las:
            self._save_derived_dataset_copy(result, suffix=f"_step_{dialog.plan.step:g}")

    def _save_derived_dataset_copy(self, dataset: object, *, suffix: str) -> None:
        current = self.session.current_dataset
        if current is None or current is not dataset:
            return
        initial = Path.cwd() / f"{current.name}{suffix}.las"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("las_editor.choose_output_title"),
            str(initial),
            "LAS (*.las)",
        )
        if not filename:
            return
        try:
            exported = self._export_current_dataset_to_path(Path(filename))
        except (OSError, RuntimeError, LasExportError) as exc:
            QMessageBox.warning(self, self._t("las_editor.title"), str(exc))
            return
        self.statusBar().showMessage(self._t("las_editor.saved_copy", name=exported.name))

    def show_curve_transfer(self) -> None:
        if self.session.current_dataset is None:
            QMessageBox.information(self, self._t("transfer.title"), self._t("data.select_dataset"))
            return
        dialog = CurveTransferDialog(self.curve_transfer_controller, self, language=self.language)
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or dialog.analysis is None
            or dialog.source_dataset_id is None
        ):
            return
        try:
            curves = self.curve_transfer_controller.apply(
                dialog.source_dataset_id,
                dialog.selected_curve_ids,
                dialog.analysis,
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("transfer.title"), str(exc))
            return
        self._after_curve_transfer(self._t("transfer.completed", count=len(curves)))

    def show_external_las_insert(self) -> None:
        target = self.session.current_dataset
        if target is None:
            QMessageBox.information(
                self, self._t("external_las.title"), self._t("data.select_dataset")
            )
            return
        dialog = ExternalLasInsertDialog(
            self.external_las_insert_controller,
            self,
            language=self.language,
        )
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or dialog.analysis is None
            or dialog.output_path is None
        ):
            return
        previous_dataset_id = target.dataset_id
        try:
            outcome = self.external_las_insert_controller.create_copy(
                dialog.analysis,
                dialog.selections,
                name=dialog.output_path.stem,
            )
            exported = self._export_current_dataset_to_path(dialog.output_path)
        except (KeyError, OSError, RuntimeError, ValueError, LasExportError) as exc:
            self._discard_current_derived_dataset(previous_dataset_id)
            QMessageBox.warning(self, self._t("external_las.title"), str(exc))
            return
        self._after_external_las_insert(
            self._t(
                "external_las.copy_completed",
                count=len(outcome.inserted_mnemonics),
                name=exported.name,
            ),
            outcome.inserted_mnemonics,
        )

    def undo_external_las_insert(self) -> None:
        try:
            outcome = self.external_las_insert_controller.undo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("external_las.title"), str(exc))
            return
        self._after_external_las_insert(self._t("external_las.undone"), outcome.inserted_mnemonics)

    def redo_external_las_insert(self) -> None:
        try:
            outcome = self.external_las_insert_controller.redo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("external_las.title"), str(exc))
            return
        self._after_external_las_insert(self._t("external_las.redone"), outcome.inserted_mnemonics)

    def _after_external_las_insert(self, message: str, mnemonics: tuple[str, ...]) -> None:
        dataset = self.session.current_dataset
        if dataset is not None:
            existing = [
                mnemonic
                for mnemonic in mnemonics
                if dataset.curve_by_mnemonic(mnemonic) is not None
            ]
            self.curve_view.show_dataset(dataset, existing or None)
            self.tablet_view.set_dataset(dataset)
            self.las_table_editor.set_dataset(dataset)
        self._refresh_tree()
        self._update_title()
        self._update_external_las_insert_actions()
        self._log(message)
        self.statusBar().showMessage(message)

    def _update_external_las_insert_actions(self) -> None:
        if hasattr(self, "undo_external_las_insert_action"):
            self.undo_external_las_insert_action.setEnabled(
                self.external_las_insert_controller.can_undo
            )
            self.redo_external_las_insert_action.setEnabled(
                self.external_las_insert_controller.can_redo
            )

    def show_dataset_merge(self) -> None:
        target = self.session.current_dataset
        if target is None:
            QMessageBox.information(self, self._t("merge.title"), self._t("data.select_dataset"))
            return
        dialog = DatasetMergeDialog(self.dataset_merge_controller, self, language=self.language)
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or dialog.analysis is None
            or dialog.source_dataset_id is None
            or dialog.output_path is None
        ):
            return
        previous_dataset_id = target.dataset_id
        try:
            result = self.dataset_merge_controller.create(
                dialog.source_dataset_id,
                dialog.analysis,
                overlap_policy=dialog.overlap_policy,
            )
            result.name = dialog.output_path.stem
            exported = self._export_current_dataset_to_path(dialog.output_path)
        except (KeyError, RuntimeError, ValueError, OSError, LasExportError) as exc:
            self._discard_current_derived_dataset(previous_dataset_id)
            QMessageBox.warning(self, self._t("merge.title"), str(exc))
            return
        self._after_dataset_merge(self._t("merge.copy_completed", name=exported.name))

    def undo_dataset_merge(self) -> None:
        try:
            self.dataset_merge_controller.undo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("merge.title"), str(exc))
            return
        self._after_dataset_merge(self._t("merge.undone"))

    def redo_dataset_merge(self) -> None:
        try:
            result = self.dataset_merge_controller.redo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("merge.title"), str(exc))
            return
        self._after_dataset_merge(self._t("merge.redone", name=result.name))

    def _after_dataset_merge(self, message: str) -> None:
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._update_merge_actions()
        self._log(message)

    def _update_merge_actions(self) -> None:
        if hasattr(self, "undo_merge_action"):
            self.undo_merge_action.setEnabled(self.dataset_merge_controller.can_undo)
            self.redo_merge_action.setEnabled(self.dataset_merge_controller.can_redo)

    def undo_curve_transfer(self) -> None:
        try:
            self.curve_transfer_controller.undo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("transfer.title"), str(exc))
            return
        self._after_curve_transfer(self._t("transfer.undone"))

    def redo_curve_transfer(self) -> None:
        try:
            self.curve_transfer_controller.redo()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("transfer.title"), str(exc))
            return
        self._after_curve_transfer(self._t("transfer.redone"))

    def _after_curve_transfer(self, message: str) -> None:
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._update_transfer_actions()
        self._log(message)

    def _update_transfer_actions(self) -> None:
        if hasattr(self, "undo_transfer_action"):
            self.undo_transfer_action.setEnabled(self.curve_transfer_controller.can_undo)
            self.redo_transfer_action.setEnabled(self.curve_transfer_controller.can_redo)

    def undo_depth_resample(self) -> None:
        answer = QMessageBox.question(
            self,
            self._t("resample.undo_title"),
            self._t("resample.undo_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.depth_axis_controller.undo_resample()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("resample.title"), str(exc))
            return
        self._after_resample_history(self._t("resample.undone"))

    def redo_depth_resample(self) -> None:
        try:
            result = self.depth_axis_controller.redo_resample()
        except RuntimeError as exc:
            QMessageBox.warning(self, self._t("resample.title"), str(exc))
            return
        self._after_resample_history(self._t("resample.redone", name=result.name))

    def _after_resample_history(self, message: str) -> None:
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._update_depth_axis_actions()
        self._log(message)

    def _after_depth_axis_history(self, message: str) -> None:
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._update_depth_axis_actions()
        self._log(message)

    def _update_depth_axis_actions(self) -> None:
        if hasattr(self, "undo_normalize_depth_action"):
            self.undo_normalize_depth_action.setEnabled(
                self.depth_axis_controller.can_undo_ascending_copy
            )
            self.redo_normalize_depth_action.setEnabled(
                self.depth_axis_controller.can_redo_ascending_copy
            )
        if hasattr(self, "undo_resample_action"):
            self.undo_resample_action.setEnabled(self.depth_axis_controller.can_undo_resample)
            self.redo_resample_action.setEnabled(self.depth_axis_controller.can_redo_resample)

    def show_lithology_legend(self) -> None:
        well = self.session.current_well
        intervals = well.lithology if well is not None else []
        entries = build_lithology_legend(
            intervals,
            self.lithotype_catalog_controller.available(),
            name_resolver=lambda item: item.localized_name(self.language.value),
            unknown_name=self._t("legend.unknown"),
        )
        LithologyLegendDialog(entries, self, language=self.language).exec()

    def save_project(self) -> None:
        if self.project_path is None:
            self.save_project_as()
            return
        try:
            saved_path = self.project_controller.save_project()
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, self._t("shell.save_project"), str(exc))
            return
        self.tablet_view.clear_curve_pencil_unsaved()
        self._update_title()
        self._log(f"Проект сохранён: {saved_path}")

    def save_project_as(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект",
            str(self.project_path or Path("project.geolog.json")),
            "GeoLog Project (*.geolog.json);;JSON (*.json)",
        )
        if not filename:
            return
        try:
            saved_path = self.project_controller.save_project(Path(filename))
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, "Сохранение", str(exc))
            return
        self.tablet_view.clear_curve_pencil_unsaved()
        self._update_title()
        self._log(f"Проект сохранён: {saved_path}")

    def _refresh_tree(self) -> None:
        self.tree.clear()
        root = QTreeWidgetItem([self.session.project.name])
        root.setData(0, Qt.ItemDataRole.UserRole, ("project", self.session.project.project_id))
        self.tree.addTopLevelItem(root)
        if self.session.project.description_templates:
            templates_item = QTreeWidgetItem(
                [
                    self._t(
                        "templates.tree",
                        count=len(self.session.project.description_templates),
                    )
                ]
            )
            templates_item.setData(0, Qt.ItemDataRole.UserRole, ("description_templates",))
            root.addChild(templates_item)
            for name in sorted(self.session.project.description_templates, key=str.casefold):
                templates_item.addChild(QTreeWidgetItem([name]))
        for well in self.session.project.wells.values():
            well_item = QTreeWidgetItem([well.name])
            well_item.setData(0, Qt.ItemDataRole.UserRole, ("well", well.well_id))
            root.addChild(well_item)
            for dataset in well.datasets.values():
                dataset_item = QTreeWidgetItem([f"{dataset.name} ({dataset.kind.value})"])
                dataset_item.setData(
                    0, Qt.ItemDataRole.UserRole, ("dataset", well.well_id, dataset.dataset_id)
                )
                well_item.addChild(dataset_item)
                for curve in dataset.curves.values():
                    curve_item = QTreeWidgetItem([curve.metadata.original_mnemonic])
                    curve_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        ("curve", well.well_id, dataset.dataset_id, curve.metadata.curve_id),
                    )
                    dataset_item.addChild(curve_item)
                layout = self.session.tablet_layouts.get(dataset.dataset_id)
                if layout is not None and layout.tracks:
                    tracks_item = QTreeWidgetItem([f"Слои планшета ({len(layout.tracks)})"])
                    dataset_item.addChild(tracks_item)
                    for position, track in enumerate(layout.tracks, start=1):
                        state = "" if track.visible else " [скрыт]"
                        track_item = QTreeWidgetItem([f"{position}. {track.title}{state}"])
                        track_item.setData(
                            0,
                            Qt.ItemDataRole.UserRole,
                            ("track", well.well_id, dataset.dataset_id, track.track_id),
                        )
                        tracks_item.addChild(track_item)
            if well.lithology:
                lithology_item = QTreeWidgetItem(
                    [self._t("lithology.tree", count=len(well.lithology))]
                )
                lithology_item.setData(0, Qt.ItemDataRole.UserRole, ("lithology", well.well_id))
                well_item.addChild(lithology_item)
                for interval in well.lithology:
                    child = QTreeWidgetItem(
                        [
                            f"{interval.top_depth:g}–{interval.bottom_depth:g} м: "
                            f"{interval.lithotype_id}"
                        ]
                    )
                    child.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        ("lithology_interval", well.well_id, interval.interval_id),
                    )
                    lithology_item.addChild(child)
            if well.interpretations:
                interpretations_item = QTreeWidgetItem(
                    [self._t("interpretations.tree", count=len(well.interpretations))]
                )
                interpretations_item.setData(
                    0, Qt.ItemDataRole.UserRole, ("interpretations", well.well_id)
                )
                well_item.addChild(interpretations_item)
                for interpretation in sorted(
                    well.interpretations.values(), key=lambda item: item.name.casefold()
                ):
                    child = QTreeWidgetItem(
                        [
                            self._t(
                                "interpretations.tree_item",
                                name=interpretation.name,
                                count=len(interpretation.intervals),
                            )
                        ]
                    )
                    child.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        (
                            "interpretation",
                            well.well_id,
                            interpretation.interpretation_id,
                        ),
                    )
                    interpretations_item.addChild(child)
                    for interpretation_interval in sorted(
                        interpretation.intervals,
                        key=lambda item: (
                            item.top_depth,
                            item.bottom_depth,
                            item.label.casefold(),
                        ),
                    ):
                        interval_child = QTreeWidgetItem(
                            [
                                self._t(
                                    "interpretations.tree_interval",
                                    top=f"{interpretation_interval.top_depth:g}",
                                    bottom=f"{interpretation_interval.bottom_depth:g}",
                                    type=interpretation_interval.interval_type,
                                    label=interpretation_interval.label,
                                )
                            ]
                        )
                        interval_child.setData(
                            0,
                            Qt.ItemDataRole.UserRole,
                            (
                                "interpretation_interval",
                                well.well_id,
                                interpretation.interpretation_id,
                                interpretation_interval.interval_id,
                            ),
                        )
                        child.addChild(interval_child)
            if well.stratigraphy:
                stratigraphy_item = QTreeWidgetItem(
                    [self._t("stratigraphy.tree", count=len(well.stratigraphy))]
                )
                stratigraphy_item.setData(
                    0, Qt.ItemDataRole.UserRole, ("stratigraphy", well.well_id)
                )
                well_item.addChild(stratigraphy_item)
                for stratigraphy_interval in sorted(
                    well.stratigraphy,
                    key=lambda item: ((item.rank or "").casefold(), item.top_depth),
                ):
                    child = QTreeWidgetItem(
                        [
                            f"{stratigraphy_interval.top_depth:g}–"
                            f"{stratigraphy_interval.bottom_depth:g} м: "
                            f"{stratigraphy_interval.code}"
                        ]
                    )
                    child.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        (
                            "stratigraphy_interval",
                            well.well_id,
                            stratigraphy_interval.interval_id,
                        ),
                    )
                    stratigraphy_item.addChild(child)
            # Annotations are managed by the dedicated F4 layer and the
            # “All…” manager. They are deliberately omitted from the project
            # navigation tree so dozens of comments do not clutter the settings
            # column.
        root.setExpanded(True)

    def _activate_tree_item(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "dataset":
            _, well_id, dataset_id = data
            self.session.current_well_id = well_id
            self.session.current_dataset_id = dataset_id
            dataset = self.session.current_dataset
            if dataset is not None:
                self._selected_track_id = None
                self._show_current_dataset()
        elif data[0] == "curve":
            _, well_id, dataset_id, curve_id = data
            self.session.current_well_id = well_id
            self.session.current_dataset_id = dataset_id
            dataset = self.session.current_dataset
            if dataset is None:
                return
            curve = dataset.curves.get(curve_id)
            if curve is not None:
                mnemonic = curve.metadata.original_mnemonic
                self.curve_view.show_dataset(dataset, [mnemonic])
                self.tabs.setCurrentWidget(self.curve_view)
                if self.pencil_action.isChecked():
                    self.curve_view.set_edit_mode(True)
                    self.statusBar().showMessage(
                        self._t("shell.curve_pencil_active_status", mnemonic=mnemonic)
                    )
                self.inspector.setPlainText(
                    f"{self._t('inspector.curve')}: {mnemonic}\n"
                    f"{self._t('inspector.unit')}: "
                    f"{curve.metadata.unit or self._t('common.unset')}\n"
                    f"{self._t('inspector.description')}: "
                    f"{curve.metadata.description or self._t('common.none')}\n"
                    f"{self._t('inspector.version')}: {curve.version}\n"
                    f"{self._t('inspector.provenance')}: {curve.metadata.provenance}"
                )
        elif data[0] == "track":
            _, well_id, dataset_id, track_id = data
            self.session.current_well_id = well_id
            self.session.current_dataset_id = dataset_id
            self._show_current_dataset()
            self._show_track_in_inspector(track_id)
            self.tabs.setCurrentWidget(self.tablet_view)
        elif data[0] in ("lithology", "lithology_interval"):
            self.session.current_well_id = data[1]
            self.show_lithology_editor()
        elif data[0] in ("stratigraphy", "stratigraphy_interval"):
            self.session.current_well_id = data[1]
            self.show_stratigraphy_editor()
        elif data[0] in ("interpretations", "interpretation"):
            self.session.current_well_id = data[1]
            if data[0] == "interpretation":
                self.interpretation_controller.select_interpretation(data[2])
                self.tablet_view.set_selected_interpretation(data[2])
            self.show_interpretation_intervals()
        elif data[0] == "interpretation_interval":
            _, well_id, interpretation_id, interval_id = data
            self.session.current_well_id = well_id
            self._show_current_dataset()
            self._select_interpretation_interval(interpretation_id, interval_id)
            self.tabs.setCurrentWidget(self.tablet_view)
        elif data[0] in ("annotations", "annotation"):
            self.session.current_well_id = data[1]
            self.show_depth_annotations()
        elif data[0] == "description_templates":
            self.show_description_templates()

    def _show_tablet_curve_in_inspector(self, track_id: str, mnemonic: str) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            return
        curve = dataset.curves.get(mnemonic)
        if curve is None:
            curve = next(
                (
                    item
                    for item in dataset.curves.values()
                    if item.metadata.original_mnemonic == mnemonic
                ),
                None,
            )
        if curve is None:
            self._show_track_in_inspector(track_id)
            return
        self._selected_track_id = track_id
        try:
            definition = self.tablet_view.layout_model.track_by_id(track_id)
            configured = definition.curve_display_settings(mnemonic).display_name
        except KeyError:
            configured = ""
        readable_name = localized_curve_name(
            curve.metadata.original_mnemonic,
            description=curve.metadata.description or "",
            unit=curve.metadata.unit or "",
            language=self.language,
            configured=configured,
        )
        self.inspector.setPlainText(
            f"{self._t('inspector.curve')}: {readable_name} [{curve.metadata.original_mnemonic}]\n"
            f"{self._t('inspector.unit')}: {curve.metadata.unit or self._t('common.unset')}\n"
            f"{self._t('inspector.description')}: "
            f"{curve.metadata.description or self._t('common.none')}\n"
            f"{self._t('inspector.version')}: {curve.version}\n"
            f"{self._t('inspector.provenance')}: {curve.metadata.provenance}"
        )

    def _graphical_track(self, track_id: str) -> TrackDefinition | None:
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except KeyError:
            return None
        if track.kind not in {TrackKind.CURVE, TrackKind.GAS, TrackKind.DEXP}:
            return None
        return track

    def _apply_context_curve_selection(self, track_id: str, mnemonics: list[str]) -> None:
        if not mnemonics:
            return
        self._selected_track_id = track_id
        try:
            track = self.tablet_controller.replace_track_curves(track_id, mnemonics)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("curve_browser.title"), str(exc))
            return
        self.tablet_view.refresh_view()
        self.tablet_view.select_track(track_id, emit_signal=False)
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))
        self._refresh_tree()
        self._update_title()

    def _add_curves_to_track_from_context(self, track_id: str) -> None:
        track = self._graphical_track(track_id)
        if track is None:
            return
        selected = self._select_curve_mnemonics()
        if not selected:
            return
        combined = list(dict.fromkeys([*track.curve_mnemonics, *selected]))
        self._apply_context_curve_selection(track_id, combined)

    def _replace_track_curves_from_context(self, track_id: str) -> None:
        track = self._graphical_track(track_id)
        if track is None:
            return
        selected = self._select_curve_mnemonics(preselected=tuple(track.curve_mnemonics))
        self._apply_context_curve_selection(track_id, selected)

    def _show_curve_settings_from_context(self, track_id: str, mnemonic: str) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            return
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except KeyError:
            return
        dialog = CurveSettingsDialog(track, dataset, self, language=self.language)
        if mnemonic:
            for row in range(dialog.curves.count()):
                item = dialog.curves.item(row)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == mnemonic:
                    dialog.curves.setCurrentRow(row)
                    break
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            for curve_mnemonic, style in dialog.curve_styles.items():
                self.tablet_controller.set_curve_style(track_id, curve_mnemonic, style)
            for curve_mnemonic, settings in dialog.curve_display.items():
                self.tablet_controller.set_curve_display_settings(
                    track_id, curve_mnemonic, settings
                )
        except (KeyError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("curve_settings.title"), str(exc))
            return
        self.tablet_view.refresh_track(
            track_id, DirtyReason.STYLE | DirtyReason.DATA | DirtyReason.STATIC
        )
        self._refresh_tree()
        self._update_title()

    def edit_selected_track(self) -> None:
        if not self._selected_track_id:
            QMessageBox.information(
                self, self._t("tablet.edit_current_track"), self._t("tablet.select_track_first")
            )
            return
        self._edit_live_track(self._selected_track_id)

    def _edit_live_track(self, track_id: str) -> None:
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except KeyError:
            return
        dialog = TabletTrackEditorDialog(track, self, language=self.language.value)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = self.tablet_controller.update_track_definition(track_id, dialog.track)
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self._t("tablet.edit_current_track"), str(exc))
            return
        self.tablet_view.refresh_view()
        self.tablet_view.select_track(track_id, emit_signal=False)
        self.inspector.show_track(updated, suggested_range=self._track_data_range(updated))
        self._refresh_tree()
        self._update_title()

    def _rename_live_track(self, track_id: str) -> None:
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except KeyError:
            return
        title, accepted = QInputDialog.getText(
            self,
            self._t("tablet.rename_track"),
            self._t("tablet.track_title_prompt"),
            text=track.title,
        )
        if not accepted:
            return
        try:
            self.tablet_controller.rename_track(track_id, title)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("tablet.rename_track"), str(exc))
            return
        self.tablet_view.refresh_view()
        self._refresh_tree()
        self._update_title()

    def _rename_live_track_group(self, track_id: str) -> None:
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except KeyError:
            return
        title, accepted = QInputDialog.getText(
            self,
            self._t("tablet.rename_group"),
            self._t("tablet.group_title_prompt"),
            text=track.group_title,
        )
        if not accepted:
            return
        try:
            self.tablet_controller.rename_track_group(track_id, title)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("tablet.rename_group"), str(exc))
            return
        self.tablet_view.refresh_view()
        self._refresh_tree()
        self._update_title()

    def _show_track_properties_from_context(self, track_id: str) -> None:
        self._show_track_in_inspector(track_id)
        self.inspector_dock.show()
        self.inspector_dock.raise_()

    def _hide_track_from_context(self, track_id: str) -> None:
        self._selected_track_id = track_id
        self.hide_selected_track()

    def _remove_track_from_context(self, track_id: str) -> None:
        self._selected_track_id = track_id
        self.remove_selected_track()

    def _show_track_in_inspector(self, track_id: str) -> None:
        self._selected_track_id = track_id
        track = next(
            (item for item in self.tablet_view.layout_model.tracks if item.track_id == track_id),
            None,
        )
        if track is None:
            self.curve_browser.set_replace_enabled(False)
            return
        self.curve_browser.set_replace_enabled(
            track.kind in {TrackKind.CURVE, TrackKind.GAS, TrackKind.DEXP}
        )
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))

    def _track_data_range(self, track: TrackDefinition) -> tuple[float, float] | None:
        dataset = self.session.current_dataset
        if dataset is None:
            return None
        finite_parts = []
        for mnemonic in track.curve_mnemonics:
            curve = dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                continue
            values = curve.values[np.isfinite(curve.values)]
            if track.x_scale is XScale.LOGARITHMIC:
                values = values[values > 0.0]
            if values.size:
                finite_parts.append(values)
        if not finite_parts:
            return None
        values = np.concatenate(finite_parts)
        minimum, maximum = float(np.min(values)), float(np.max(values))
        if minimum == maximum:
            if track.x_scale is XScale.LOGARITHMIC:
                return minimum / 1.05, maximum * 1.05
            padding = max(abs(minimum) * 0.05, 1.0)
            return minimum - padding, maximum + padding
        return minimum, maximum

    def _apply_inspector_track_settings(
        self,
        track_id: str,
        width: int,
        scale: str,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        try:
            self.tablet_controller.update_track_view_settings(
                track_id,
                width=width,
                x_scale=XScale(scale),
                x_min=minimum,
                x_max=maximum,
            )
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except (KeyError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("inspector.title"), str(exc))
            return
        self._layout_changed(f"Обновлены свойства трека: {track.title}")
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))

    def _change_vertical_index_from_tablet(self, index_id: str) -> None:
        try:
            changed = self.tablet_controller.set_vertical_index(index_id)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("tablet.title"), str(exc))
            return
        if changed:
            layout = self.session.current_tablet_layout
            if layout is not None:
                self.tablet_view.set_layout_model(layout)
            self._update_title()

    def _show_visible_depth(self, top: float, bottom: float) -> None:
        if self.tablet_controller.set_visible_depth(top, bottom):
            self._update_title()
        top_text = self.tablet_view.format_vertical_value(top)
        bottom_text = self.tablet_view.format_vertical_value(bottom)
        self.statusBar().showMessage(
            self._t("tablet.visible_interval_status", top=top_text, bottom=bottom_text)
        )

    def _apply_inspector_curve_style(
        self,
        track_id: str,
        mnemonic: str,
        color: str,
        width: float,
        line_style: str,
    ) -> None:
        try:
            style = CurveStyle(
                color=color,
                width=width,
                line_style=CurveLineStyle(line_style),
            )
            self.tablet_controller.set_curve_style(track_id, mnemonic, style)
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except (KeyError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("inspector.title"), str(exc))
            return
        self.tablet_view.refresh_track(
            track_id, DirtyReason.STYLE | DirtyReason.DATA | DirtyReason.STATIC
        )
        self._refresh_tree()
        self._update_title()
        self._log(self._t("inspector.style_updated", mnemonic=mnemonic))
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))

    def _apply_inspector_grid(
        self, track_id: str, show_x: bool, show_y: bool, alpha: float
    ) -> None:
        try:
            self.tablet_controller.set_track_grid(track_id, show_x, show_y, alpha)
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except (KeyError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("inspector.title"), str(exc))
            return
        self.tablet_view.refresh_track(track_id, DirtyReason.STATIC)
        self._refresh_tree()
        self._update_title()
        self._log(self._t("inspector.grid_updated"))
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))

    def _apply_inspector_x_axis_label(self, track_id: str, label: str) -> None:
        try:
            self.tablet_controller.set_track_x_axis_label(track_id, label)
            track = self.tablet_view.layout_model.track_by_id(track_id)
        except (KeyError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("inspector.title"), str(exc))
            return
        self.tablet_view.refresh_track(track_id, DirtyReason.STATIC)
        self._refresh_tree()
        self._update_title()
        self._log(self._t("inspector.axis_label_updated"))
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))

    def _update_title(self) -> None:
        marker = " *" if self.session.dirty else ""
        self.setWindowTitle(
            f"GEOLOG GASRATIO@Pixler {__version__} — {self.session.project.name}{marker}"
        )

    def _log(self, text: str) -> None:
        self.issues.append(text)
        normalized = text.casefold()
        if "ошибка" in normalized or "error" in normalized or "failed" in normalized:
            self.issues_dock.show()

    def show_about(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("GEOLOG GASRATIO@Pixler")
        dialog.setIconPixmap(logo_pixmap(280))
        dialog.setText(
            f"Версия {__version__}\n\n"
            "Автор: Rinat Sarmuldin (Сармулдин Ринат)\n"
            "E-mail: ura07srr@gmail.com\n\n"
            "Реализовано: загрузка и безопасный экспорт LAS, базовые Gas Ratio, "
            "версионированные проекты, многотрековый планшет и редактор кривых с Undo/Redo."
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()
