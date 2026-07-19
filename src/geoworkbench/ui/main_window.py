from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPainter, QPen, QPixmap
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QColorDialog,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from geoworkbench import __version__
from geoworkbench.calculations.controller import FormulaExecutionController
from geoworkbench.catalogs.sensors import SensorCatalog, set_active_sensor_catalog
from geoworkbench.calculations.custom_formula import formula_inputs
from geoworkbench.calculations.interval_statistics import calculate_interval_statistics
from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
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
from geoworkbench.forms import FormApplyEngine, FormRepository
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.data_inspector_controller import DataInspectorController
from geoworkbench.project.curve_metadata_controller import CurveMetadataController
from geoworkbench.project.curve_transfer_controller import CurveTransferController
from geoworkbench.project.custom_formula_controller import CustomFormulaController
from geoworkbench.project.header_editing_controller import HeaderEditingController
from geoworkbench.project.description_template_controller import DescriptionTemplateController
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.curve_editing_controller import (
    CurveEditingController,
    CurveEditOutcome,
)
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.project.nct_controller import NctCalculationController
from geoworkbench.project.new_las_controller import NewLasController
from geoworkbench.project.las_range_editor import LasRangeEditingController
from geoworkbench.project.dataset_export_controller import DatasetExportController
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.time_depth_mapping_controller import TimeDepthMappingController
from geoworkbench.printing.widget_print import render_widget_to_printer
from geoworkbench.storage.project_codec import ProjectFormatError
from geoworkbench.tablet import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.render_invalidation import DirtyReason
from geoworkbench.tablet.models import CurveLineStyle, CurveStyle
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.interval_interaction import IntervalEditMode
from geoworkbench.tablet.lithology_legend import build_lithology_legend
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.track_inspector import TrackInspector
from geoworkbench.ui.time_depth_mapping_dialog import TimeDepthMappingDialog
from geoworkbench.ui.branding import application_icon, logo_pixmap
from geoworkbench.ui.csv_import_dialog import CsvImportDialog
from geoworkbench.ui.curve_transfer_dialog import CurveTransferDialog
from geoworkbench.ui.excel_import_dialog import ExcelImportDialog
from geoworkbench.ui.form_manager_dialog import FormManagerDialog
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
from geoworkbench.ui.lithology_legend_dialog import LithologyLegendDialog
from geoworkbench.ui.lithotype_catalog_dialog import LithotypeCatalogDialog
from geoworkbench.ui.sensor_catalog_dialog import SensorCatalogDialog
from geoworkbench.ui.stratigraphy_dialog import StratigraphyDialog
from geoworkbench.ui.nct_dialog import NctCalculationDialog
from geoworkbench.ui.new_las_dialog import NewLasDialog
from geoworkbench.ui.las_table_editor import LasTableEditor
from geoworkbench.ui.las_export_dialog import LasExportPlanDialog
from geoworkbench.ui.las_curve_browser import LasCurveBrowser
from geoworkbench.ui.print_page_dialog import PrintPageDialog
from geoworkbench.ui.masterlog_templates_dialog import MasterlogTemplatesDialog
from geoworkbench.visualization.curve_view import CurveView
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis
from geoworkbench.services.localization import (
    LANGUAGE_NAMES,
    AppLanguage,
    LanguageSettings,
    Localizer,
)
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
        forms_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / "forms"
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
        self.formula_registry = build_all_sourced_formula_registry()
        self.formula_execution_controller = FormulaExecutionController(
            self.session, self.formula_registry
        )
        self.custom_formula_controller = CustomFormulaController(self.session)
        self.time_depth_mapping_controller = TimeDepthMappingController(self.session)
        self.depth_annotation_controller = DepthAnnotationController(self.session)
        self.lithology_controller = LithologyController(self.session)
        self.interpretation_controller = InterpretationController(self.session)
        self.stratigraphy_controller = StratigraphyController(self.session)
        self.lithotype_catalog_controller = LithotypeCatalogController(self.session)
        self.description_template_controller = DescriptionTemplateController(self.session)
        self.depth_axis_controller = DepthAxisController(self.session)
        self.nct_calculation_controller = NctCalculationController(self.session)
        self.new_las_controller = NewLasController(self.session)
        self.las_range_editing_controller = LasRangeEditingController(self.session)
        self.masterlog_template_controller = MasterlogTemplateController(self.session)
        self.dataset_selection = DatasetIntervalSelection()
        self._selected_track_id: str | None = None
        self._interpretation_dialog: InterpretationIntervalsDialog | None = None
        self.print_page_settings = self.user_profile_settings.print_page_settings()
        self.cursor_line_settings = self.user_profile_settings.cursor_line_settings()
        self.setWindowIcon(application_icon())
        self.setWindowTitle(f"GEOLOG GASRATIO@Pixler {__version__}")
        self.resize(1580, 960)

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
        self.tablet_view.track_width_change_requested.connect(self._change_track_width_from_drag)
        self.tablet_view.track_order_change_requested.connect(self._track_order_changed_from_drag)
        self.tablet_view.visible_depth_changed.connect(self._show_visible_depth)
        self.tablet_view.vertical_index_changed.connect(self._change_vertical_index_from_tablet)
        self.tablet_view.cursor_changed.connect(self._show_cursor_values)
        self.tablet_view.interpretation_selected.connect(
            self._select_interpretation_from_tablet
        )
        self.tablet_view.interval_selected.connect(self._select_interpretation_interval)
        self.tablet_view.interval_selection_cleared.connect(
            self._clear_interpretation_interval_selection
        )
        self.tablet_view.interval_create_requested.connect(
            self._create_interval_from_tablet
        )
        self.tablet_view.interval_resize_requested.connect(
            self._resize_interval_from_tablet
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
        self._create_actions()
        self._create_toolbar()
        self.setStatusBar(QStatusBar())
        self.cursor_line_action.setChecked(self.cursor_line_settings.enabled)
        self.statusBar().showMessage(self._t("app.ready"))
        self._update_title()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

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
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(self._t("explorer.title"))
        self.tree.itemDoubleClicked.connect(self._activate_tree_item)
        self.project_dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)
        self._refresh_tree()

    def _create_curve_browser(self) -> None:
        self.curve_browser_dock = QDockWidget(self._t("curve_browser.title"), self)
        self.curve_browser = LasCurveBrowser(language=self.language)
        self.curve_browser.set_sensor_catalog(self.mnemonic_registry.catalog())
        self.curve_browser.setMinimumWidth(440)
        self.curve_browser.build_requested.connect(self._build_tablet_from_curve_selection)
        self.curve_browser.add_requested.connect(self._add_curves_from_browser)
        self.curve_browser.replace_requested.connect(self._replace_selected_track_curves)
        self.curve_browser_dock.setWidget(self.curve_browser)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.curve_browser_dock)
        self.tabifyDockWidget(self.project_dock, self.curve_browser_dock)
        self.curve_browser_dock.hide()

    def _create_inspector(self) -> None:
        dock = QDockWidget(self._t("dock.inspector"), self)
        self.inspector = TrackInspector(language=self.language)
        self.inspector.settings_requested.connect(self._apply_inspector_track_settings)
        self.inspector.curve_style_requested.connect(self._apply_inspector_curve_style)
        self.inspector.grid_requested.connect(self._apply_inspector_grid)
        self.inspector.x_axis_label_requested.connect(self._apply_inspector_x_axis_label)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)


    def _create_interpretation_properties_panel(self) -> None:
        self.interpretation_properties_dock = QDockWidget(
            self._t("interpretations.properties_title"), self
        )
        self.interpretation_properties = InterpretationPropertiesPanel(
            language=self.language
        )
        self.interpretation_properties.update_requested.connect(
            self._update_interval_from_properties
        )
        self.interpretation_properties.manager_requested.connect(
            self.show_interpretation_intervals
        )
        self.interpretation_properties_dock.setWidget(self.interpretation_properties)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.interpretation_properties_dock
        )
        self.interpretation_properties_dock.hide()

    def _create_issues_panel(self) -> None:
        self.issues_dock = QDockWidget(self._t("dock.log"), self)
        self.issues = QTextEdit()
        self.issues.setReadOnly(True)
        self.issues_dock.setWidget(self.issues)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.issues_dock)
        self.issues_dock.hide()

    def _create_cursor_panel(self) -> None:
        self.cursor_dock = QDockWidget("Параметры по визиру", self)
        self.cursor_values = QTextEdit()
        self.cursor_values.setReadOnly(True)
        self.cursor_dock.setWidget(self.cursor_values)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.cursor_dock)
        self.cursor_dock.hide()

    def _create_actions(self) -> None:
        file_menu = self.menuBar().addMenu(self._t("menu.file"))
        edit_menu = self.menuBar().addMenu(self._t("menu.edit"))
        calc_menu = self.menuBar().addMenu(self._t("menu.calculations"))
        tablet_menu = self.menuBar().addMenu(self._t("menu.tablet"))
        forms_menu = self.menuBar().addMenu(self._t("forms.menu"))
        print_menu = self.menuBar().addMenu(self._t("menu.print"))
        language_menu = self.menuBar().addMenu(self._t("menu.language"))
        help_menu = self.menuBar().addMenu(self._t("menu.help"))

        self.open_project_action = QAction("Открыть проект...", self)
        self.open_project_action.setShortcut("Ctrl+O")
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)

        self.new_las_action = QAction(self._t("new_las.action"), self)
        self.new_las_action.setShortcut("Ctrl+N")
        self.new_las_action.triggered.connect(self.create_new_las)
        file_menu.addAction(self.new_las_action)

        self.open_data_action = QAction(self._t("import.universal"), self)
        self.open_data_action.setShortcut("Ctrl+I")
        self.open_data_action.triggered.connect(self.open_data)
        file_menu.addAction(self.open_data_action)
        file_menu.addSeparator()

        self.open_action = QAction("Импортировать LAS...", self)
        self.open_action.setShortcut("Ctrl+L")
        self.open_action.triggered.connect(self.open_las)
        file_menu.addAction(self.open_action)

        self.open_csv_action = QAction("Импортировать CSV/TXT...", self)
        self.open_csv_action.triggered.connect(self.open_csv)
        file_menu.addAction(self.open_csv_action)

        self.open_excel_action = QAction("Импортировать Excel...", self)
        self.open_excel_action.triggered.connect(self.open_excel)
        file_menu.addAction(self.open_excel_action)

        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        for language, name in LANGUAGE_NAMES.items():
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(language is self.language)
            action.triggered.connect(
                lambda checked=False, value=language: self.change_language(value)
            )
            language_group.addAction(action)
            language_menu.addAction(action)
        language_menu.addSeparator()
        self.user_profile_action = QAction(self._t("profile.action"), self)
        self.user_profile_action.triggered.connect(self.select_user_profile)
        language_menu.addAction(self.user_profile_action)

        self.save_action = QAction("Сохранить проект как...", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_project_as)
        file_menu.addAction(self.save_action)

        self.export_las_action = QAction("Экспортировать текущий dataset в LAS...", self)
        self.export_las_action.triggered.connect(self.export_current_las)
        file_menu.addAction(self.export_las_action)

        export_csv_action = QAction(self._t("selection_export.csv_action"), self)
        export_csv_action.triggered.connect(self.export_selected_csv)
        file_menu.addAction(export_csv_action)
        export_excel_action = QAction(self._t("selection_export.excel_action"), self)
        export_excel_action.triggered.connect(self.export_selected_excel)
        file_menu.addAction(export_excel_action)
        export_png_action = QAction(self._t("visual_export.png_action"), self)
        export_png_action.triggered.connect(lambda: self.export_active_visualization("png"))
        file_menu.addAction(export_png_action)
        export_svg_action = QAction(self._t("visual_export.svg_action"), self)
        export_svg_action.triggered.connect(lambda: self.export_active_visualization("svg"))
        file_menu.addAction(export_svg_action)
        export_pdf_action = QAction(self._t("visual_export.pdf_action"), self)
        export_pdf_action.triggered.connect(lambda: self.export_active_visualization("pdf"))
        file_menu.addAction(export_pdf_action)
        print_preview_action = QAction(self._t("print.preview_action"), self)
        print_preview_action.triggered.connect(self.preview_active_visualization)
        file_menu.addAction(print_preview_action)
        page_setup_action = QAction(self._t("print.page_setup_action"), self)
        page_setup_action.triggered.connect(self.configure_print_page)
        file_menu.addAction(page_setup_action)
        templates_action = QAction(self._t("masterlog_templates.action"), self)
        templates_action.triggered.connect(self.show_masterlog_templates)
        print_menu.addAction(templates_action)
        self.interpretation_report_action = QAction(
            self._t("interpretation_report.action"), self
        )
        self.interpretation_report_action.triggered.connect(self.show_interpretation_report)
        print_menu.addAction(self.interpretation_report_action)
        file_menu.addSeparator()
        save_export_profile_action = QAction(self._t("export_profile.save"), self)
        save_export_profile_action.triggered.connect(self.save_export_profile)
        file_menu.addAction(save_export_profile_action)
        apply_export_profile_action = QAction(self._t("export_profile.apply"), self)
        apply_export_profile_action.triggered.connect(self.apply_export_profile)
        file_menu.addAction(apply_export_profile_action)
        delete_export_profile_action = QAction(self._t("export_profile.delete"), self)
        delete_export_profile_action.triggered.connect(self.delete_export_profile)
        file_menu.addAction(delete_export_profile_action)
        export_json_action = QAction(self._t("json_export.action"), self)
        export_json_action.triggered.connect(self.export_current_json)
        file_menu.addAction(export_json_action)
        export_parquet_action = QAction(self._t("parquet_export.action"), self)
        export_parquet_action.triggered.connect(self.export_current_parquet)
        file_menu.addAction(export_parquet_action)

        self.data_inspector_action = QAction(self._t("data.action"), self)
        self.data_inspector_action.triggered.connect(self.show_data_inspector)
        file_menu.addAction(self.data_inspector_action)

        self.pencil_action = QAction("Карандаш кривой", self)
        self.pencil_action.setCheckable(True)
        self.pencil_action.setShortcut("E")
        self.pencil_action.toggled.connect(self.toggle_curve_edit_mode)
        edit_menu.addAction(self.pencil_action)

        self.cursor_line_action = QAction("Визирная линия", self)
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
        self.cursor_style_action = QAction("Настроить визирную линию...", self)
        self.cursor_style_action.triggered.connect(self.configure_cursor_line)
        edit_menu.addAction(self.cursor_style_action)

        self.undo_action = QAction("Отменить редактирование", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_curve_edit)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Повторить редактирование", self)
        self.redo_action.setShortcut("Ctrl+Shift+Z")
        self.redo_action.triggered.connect(self.redo_curve_edit)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)

        self.annotations_action = QAction(self._t("annotations.action"), self)
        self.annotations_action.triggered.connect(self.show_depth_annotations)
        edit_menu.addAction(self.annotations_action)

        self.lithology_action = QAction(self._t("lithology.action"), self)
        self.lithology_action.triggered.connect(self.show_lithology_editor)
        edit_menu.addAction(self.lithology_action)

        self.stratigraphy_action = QAction(self._t("stratigraphy.action"), self)
        self.stratigraphy_action.triggered.connect(self.show_stratigraphy_editor)
        edit_menu.addAction(self.stratigraphy_action)

        self.interpretation_intervals_action = QAction(
            self._t("interpretations.action"), self
        )
        self.interpretation_intervals_action.triggered.connect(
            self.show_interpretation_intervals
        )
        edit_menu.addAction(self.interpretation_intervals_action)

        self.lithotype_catalog_action = QAction(self._t("catalog.action"), self)
        self.lithotype_catalog_action.triggered.connect(self.show_lithotype_catalog)
        edit_menu.addAction(self.lithotype_catalog_action)

        self.sensor_catalog_action = QAction(self._t("sensors.action"), self)
        self.sensor_catalog_action.triggered.connect(self.show_sensor_catalog)
        edit_menu.addAction(self.sensor_catalog_action)

        self.description_templates_action = QAction(self._t("templates.action"), self)
        self.description_templates_action.triggered.connect(self.show_description_templates)
        edit_menu.addAction(self.description_templates_action)

        self.normalize_depth_action = QAction(self._t("depth.create_copy_action"), self)
        self.normalize_depth_action.triggered.connect(self.create_ascending_depth_copy)
        edit_menu.addAction(self.normalize_depth_action)
        self.undo_normalize_depth_action = QAction(self._t("depth.undo"), self)
        self.undo_normalize_depth_action.triggered.connect(self.undo_ascending_depth_copy)
        self.undo_normalize_depth_action.setEnabled(False)
        edit_menu.addAction(self.undo_normalize_depth_action)
        self.redo_normalize_depth_action = QAction(self._t("depth.redo"), self)
        self.redo_normalize_depth_action.triggered.connect(self.redo_ascending_depth_copy)
        self.redo_normalize_depth_action.setEnabled(False)
        edit_menu.addAction(self.redo_normalize_depth_action)

        self.resample_depth_action = QAction(self._t("resample.action"), self)
        self.resample_depth_action.triggered.connect(self.create_resampled_depth_copy)
        edit_menu.addAction(self.resample_depth_action)
        self.undo_resample_action = QAction(self._t("resample.undo"), self)
        self.undo_resample_action.triggered.connect(self.undo_depth_resample)
        self.undo_resample_action.setEnabled(False)
        edit_menu.addAction(self.undo_resample_action)
        self.redo_resample_action = QAction(self._t("resample.redo"), self)
        self.redo_resample_action.triggered.connect(self.redo_depth_resample)
        self.redo_resample_action.setEnabled(False)
        edit_menu.addAction(self.redo_resample_action)

        self.transfer_curves_action = QAction(self._t("transfer.action"), self)
        self.transfer_curves_action.triggered.connect(self.show_curve_transfer)
        edit_menu.addAction(self.transfer_curves_action)
        self.undo_transfer_action = QAction(self._t("transfer.undo"), self)
        self.undo_transfer_action.triggered.connect(self.undo_curve_transfer)
        self.undo_transfer_action.setEnabled(False)
        edit_menu.addAction(self.undo_transfer_action)
        self.redo_transfer_action = QAction(self._t("transfer.redo"), self)
        self.redo_transfer_action.triggered.connect(self.redo_curve_transfer)
        self.redo_transfer_action.setEnabled(False)
        edit_menu.addAction(self.redo_transfer_action)

        self.merge_datasets_action = QAction(self._t("merge.action"), self)
        self.merge_datasets_action.triggered.connect(self.show_dataset_merge)
        edit_menu.addAction(self.merge_datasets_action)
        self.undo_merge_action = QAction(self._t("merge.undo"), self)
        self.undo_merge_action.triggered.connect(self.undo_dataset_merge)
        self.undo_merge_action.setEnabled(False)
        edit_menu.addAction(self.undo_merge_action)
        self.redo_merge_action = QAction(self._t("merge.redo"), self)
        self.redo_merge_action.triggered.connect(self.redo_dataset_merge)
        self.redo_merge_action.setEnabled(False)
        edit_menu.addAction(self.redo_merge_action)

        self.ratio_action = QAction(self._t("ratio.action"), self)
        self.ratio_action.triggered.connect(self.calculate_ratios)
        calc_menu.addAction(self.ratio_action)

        self.formula_action = QAction(self._t("formula.action"), self)
        self.formula_action.triggered.connect(self.show_formula_profiles)
        calc_menu.addAction(self.formula_action)

        self.custom_formula_action = QAction("Пользовательские формулы...", self)
        self.custom_formula_action.triggered.connect(self.show_custom_formulas)
        calc_menu.addAction(self.custom_formula_action)

        self.time_depth_mapping_action = QAction(self._t("time_depth.action"), self)
        self.time_depth_mapping_action.triggered.connect(self.show_time_depth_mapping)
        calc_menu.addAction(self.time_depth_mapping_action)

        self.nct_action = QAction(self._t("nct.action"), self)
        self.nct_action.triggered.connect(self.calculate_nct)
        calc_menu.addAction(self.nct_action)

        self.interval_statistics_action = QAction(self._t("statistics.action"), self)
        self.interval_statistics_action.triggered.connect(self.show_interval_statistics)
        calc_menu.addAction(self.interval_statistics_action)

        self.default_tablet_action = QAction(self._t("tablet.build_default"), self)
        self.default_tablet_action.triggered.connect(self.build_default_tablet)
        tablet_menu.addAction(self.default_tablet_action)

        self.curve_browser_action = self.curve_browser_dock.toggleViewAction()
        self.curve_browser_action.setText(self._t("curve_browser.title"))
        tablet_menu.addAction(self.curve_browser_action)

        tablet_menu.addSeparator()
        self.interval_mode_group = QActionGroup(self)
        self.interval_mode_group.setExclusive(True)
        self.interval_select_action = QAction(
            self._t("interpretations.mode_select"), self, checkable=True
        )
        self.interval_select_action.setChecked(True)
        self.interval_select_action.setShortcut("Alt+1")
        self.interval_select_action.triggered.connect(
            lambda: self.set_interval_interaction_mode(IntervalEditMode.SELECT)
        )
        self.interval_mode_group.addAction(self.interval_select_action)
        tablet_menu.addAction(self.interval_select_action)

        self.interval_create_action = QAction(
            self._t("interpretations.mode_create"), self, checkable=True
        )
        self.interval_create_action.setShortcut("Alt+2")
        self.interval_create_action.triggered.connect(
            lambda: self.set_interval_interaction_mode(IntervalEditMode.CREATE)
        )
        self.interval_mode_group.addAction(self.interval_create_action)
        tablet_menu.addAction(self.interval_create_action)

        self.interval_resize_action = QAction(
            self._t("interpretations.mode_resize"), self, checkable=True
        )
        self.interval_resize_action.setShortcut("Alt+3")
        self.interval_resize_action.triggered.connect(
            lambda: self.set_interval_interaction_mode(IntervalEditMode.RESIZE)
        )
        self.interval_mode_group.addAction(self.interval_resize_action)
        tablet_menu.addAction(self.interval_resize_action)

        self.undo_interpretation_action = QAction(
            self._t("interpretations.undo"), self
        )
        self.undo_interpretation_action.setShortcut("Ctrl+Alt+Z")
        self.undo_interpretation_action.triggered.connect(self.undo_interpretation_edit)
        tablet_menu.addAction(self.undo_interpretation_action)
        self.redo_interpretation_action = QAction(
            self._t("interpretations.redo"), self
        )
        self.redo_interpretation_action.setShortcut("Ctrl+Alt+Shift+Z")
        self.redo_interpretation_action.triggered.connect(self.redo_interpretation_edit)
        tablet_menu.addAction(self.redo_interpretation_action)
        self._update_interpretation_history_actions()

        save_preset_action = QAction(self._t("tablet.preset_save"), self)
        save_preset_action.triggered.connect(self.save_tablet_preset)
        tablet_menu.addAction(save_preset_action)
        apply_preset_action = QAction(self._t("tablet.preset_apply"), self)
        apply_preset_action.triggered.connect(self.apply_tablet_preset)
        tablet_menu.addAction(apply_preset_action)
        delete_preset_action = QAction(self._t("tablet.preset_delete"), self)
        delete_preset_action.triggered.connect(self.delete_tablet_preset)
        tablet_menu.addAction(delete_preset_action)

        self.form_manager_action = QAction(self._t("forms.manager_action"), self)
        self.form_manager_action.triggered.connect(self.show_form_manager)
        forms_menu.addAction(self.form_manager_action)

        self.lithology_legend_action = QAction(self._t("legend.action"), self)
        self.lithology_legend_action.triggered.connect(self.show_lithology_legend)
        tablet_menu.addAction(self.lithology_legend_action)

        add_track_menu = QMenu(self._t("tablet.add_track"), self)
        tablet_menu.addMenu(add_track_menu)
        for title, kind in (
            (self._t("tablet.track.depth"), TrackKind.DEPTH),
            (self._t("tablet.track.gas"), TrackKind.GAS),
            ("DEXP / NCT", TrackKind.DEXP),
            (self._t("tablet.track.lithology"), TrackKind.LITHOLOGY),
            (self._t("tablet.track.stratigraphy"), TrackKind.STRATIGRAPHY),
            (self._t("tablet.track.interpretation"), TrackKind.INTERPRETATION),
            (self._t("tablet.track.cuttings"), TrackKind.CUTTINGS),
            (self._t("tablet.track.calcimetry"), TrackKind.CALCIMETRY),
            (self._t("tablet.track.lba"), TrackKind.LBA),
            (self._t("tablet.track.description"), TrackKind.TEXT),
            (self._t("tablet.track.curve"), TrackKind.CURVE),
        ):
            action = QAction(title, self)
            action.triggered.connect(lambda _checked=False, value=kind: self.add_track(value))
            add_track_menu.addAction(action)

        tablet_menu.addSeparator()
        width_action = QAction(self._t("tablet.change_width"), self)
        width_action.triggered.connect(self.change_selected_track_width)
        tablet_menu.addAction(width_action)

        linear_scale_action = QAction(self._t("tablet.linear_scale"), self)
        linear_scale_action.triggered.connect(
            lambda: self.set_selected_track_x_scale(XScale.LINEAR)
        )
        tablet_menu.addAction(linear_scale_action)

        log_scale_action = QAction(self._t("tablet.log_scale"), self)
        log_scale_action.triggered.connect(
            lambda: self.set_selected_track_x_scale(XScale.LOGARITHMIC)
        )
        tablet_menu.addAction(log_scale_action)

        range_action = QAction(self._t("tablet.set_range"), self)
        range_action.triggered.connect(self.change_selected_track_x_range)
        tablet_menu.addAction(range_action)

        auto_range_action = QAction(self._t("tablet.auto_range"), self)
        auto_range_action.triggered.connect(self.reset_selected_track_x_range)
        tablet_menu.addAction(auto_range_action)

        depth_range_action = QAction(self._t("tablet.set_depth_range"), self)
        depth_range_action.triggered.connect(self.change_visible_depth_range)
        tablet_menu.addAction(depth_range_action)

        full_depth_action = QAction(self._t("tablet.full_depth_range"), self)
        full_depth_action.triggered.connect(self.reset_visible_depth_range)
        tablet_menu.addAction(full_depth_action)

        move_left_action = QAction(self._t("tablet.move_left"), self)
        move_left_action.triggered.connect(lambda: self.move_selected_track(-1))
        tablet_menu.addAction(move_left_action)

        move_right_action = QAction(self._t("tablet.move_right"), self)
        move_right_action.triggered.connect(lambda: self.move_selected_track(1))
        tablet_menu.addAction(move_right_action)

        hide_action = QAction(self._t("tablet.hide"), self)
        hide_action.triggered.connect(self.hide_selected_track)
        tablet_menu.addAction(hide_action)

        show_all_action = QAction(self._t("tablet.show_all"), self)
        show_all_action.triggered.connect(self.show_all_tracks)
        tablet_menu.addAction(show_all_action)

        remove_action = QAction(self._t("tablet.remove"), self)
        remove_action.triggered.connect(self.remove_selected_track)
        tablet_menu.addAction(remove_action)

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Основная")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.open_data_action)
        toolbar.addAction(self.default_tablet_action)
        toolbar.addSeparator()
        toolbar.addAction(self.interval_select_action)
        toolbar.addAction(self.interval_create_action)
        toolbar.addAction(self.interval_resize_action)
        toolbar.addSeparator()
        toolbar.addAction(self.ratio_action)
        toolbar.addAction(self.cursor_line_action)
        toolbar.addAction(self.save_action)
        self.addToolBar(toolbar)

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
        color = QColorDialog.getColor(parent=self, title="Цвет визирной линии")
        if not color.isValid():
            return
        width, accepted = QInputDialog.getDouble(
            self,
            "Визирная линия",
            "Толщина, px",
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
            return
        self.language_settings.save(language)
        QMessageBox.information(
            self,
            self._t("language.changed.title"),
            self._t("language.changed.message", language=LANGUAGE_NAMES[language]),
        )

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
        self.las_table_editor.set_number_formats(
            self.user_profile_settings.table_number_formats()
        )

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

        last_dataset = None
        last_well = None
        errors: list[str] = []
        descending_files: list[str] = []
        import_warnings: list[str] = []
        for filename in filenames:
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
                        f"Ручная проверка: {Path(filename).name}",
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
                )
                last_dataset = dataset
                last_well = well
                if (
                    import_mode is LasImportMode.COMPATIBLE
                    and analyze_depth_axis(dataset.depth).direction is DepthDirection.DESCENDING
                ):
                    descending_files.append(Path(filename).name)
                report_messages = tuple(
                    issue.message
                    for issue in import_result.report.issues
                    if issue.code != "index-descending"
                    and issue.severity is not LasIssueSeverity.INFO
                )
                if report_messages and import_mode is LasImportMode.COMPATIBLE:
                    import_warnings.append(
                        f"{Path(filename).name}:\n  " + "\n  ".join(report_messages)
                    )
                self._log(f"Загружен LAS: {filename}")
            except (OSError, LasImportError) as exc:
                errors.append(f"{Path(filename).name}: {exc}")
                self._log(f"ОШИБКА: {filename}: {exc}")

        if last_dataset is None or last_well is None:
            QMessageBox.critical(self, "Ошибка LAS", "\n".join(errors) or "Файлы не загружены")
            return

        self.curve_view.show_dataset(last_dataset)
        self.las_table_editor.set_dataset(last_dataset)
        self.tablet_view.set_dataset(last_dataset)
        self.tablet_view.set_canvas_objects(last_well.canvas_objects)
        self.tablet_view.set_lithology(
            last_well.lithology,
            self.lithotype_catalog_controller.available(),
        )
        self.tablet_view.set_cuttings(last_well.cuttings)
        self.tablet_view.set_stratigraphy(last_well.stratigraphy)
        self.curve_browser.set_dataset(last_dataset)
        self.curve_browser.select_recommended()
        self.curve_browser_dock.show()
        self.curve_browser_dock.raise_()
        self.build_default_tablet()
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
        self.formula_execution_controller.session = self.session
        self.custom_formula_controller.session = self.session
        self.custom_formula_controller.clear_history()
        self.depth_annotation_controller.session = self.session
        self.depth_annotation_controller.history.clear()
        self.lithology_controller.session = self.session
        self.stratigraphy_controller.session = self.session
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
        if dataset is None:
            self.curve_view.clear()
            self.las_table_editor.set_dataset(None)
            self.tablet_view.set_layout_model(TabletLayout())
            self.tablet_view.set_dataset(None)
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
        self.curve_browser.set_dataset(dataset)
        self.curve_browser.select_recommended()
        self.curve_browser_dock.show()
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
            self._select_interpretation_interval(
                selected_interpretation_id, selected_interval_id
            )
        else:
            self._clear_interpretation_interval_selection()
        saved_layout = self.session.current_tablet_layout
        if saved_layout is None:
            self.build_default_tablet()
        else:
            self.tablet_view.set_layout_model(saved_layout)
        self.tabs.setCurrentWidget(self.tablet_view)

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
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(
            self.print_page_settings.page_size_for_content(current.width(), current.height())
        )
        printer.setPageOrientation(self.print_page_settings.qt_orientation)
        dialog = QPrintPreviewDialog(printer, self)
        dialog.setWindowTitle(self._t("print.preview_title"))
        dialog.paintRequested.connect(
            lambda requested_printer: render_widget_to_printer(current, requested_printer)
        )
        dialog.exec()

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

    def toggle_curve_edit_mode(self, enabled: bool) -> None:
        if enabled and not self.curve_view.set_edit_mode(True):
            self.pencil_action.setChecked(False)
            QMessageBox.information(
                self,
                "Редактор кривой",
                "Выберите одну кривую двойным щелчком в дереве проекта",
            )
            return
        if not enabled:
            self.curve_view.set_edit_mode(False)

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
            QMessageBox.warning(self, "Редактор кривой", str(exc))
            return
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
            self.curve_view.show_dataset(dataset, [outcome.mnemonic])
            self.curve_view.set_edit_mode(self.pencil_action.isChecked())
            self.tablet_view.set_dataset(dataset)
            self.las_table_editor.set_dataset(dataset)
        self._update_curve_edit_actions()
        self._update_title()
        affected = ", ".join(outcome.affected_mnemonics) or "нет"
        self._log(f"{outcome.operation}: {outcome.mnemonic}; зависимые STALE: {affected}")

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
        self.undo_action.setEnabled(self.curve_editing_controller.history.can_undo)
        self.redo_action.setEnabled(self.curve_editing_controller.history.can_redo)

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
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage(
            self._t("curve_browser.built_status", count=len(selected))
        )

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
            track = self.tablet_controller.replace_track_curves(
                self._selected_track_id, selected
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("curve_browser.title"), str(exc))
            return
        self.tablet_view.refresh_view()
        self.inspector.show_track(track, suggested_range=self._track_data_range(track))
        self._refresh_tree()
        self._update_title()

    def show_form_manager(self) -> None:
        dialog = FormManagerDialog(
            self.form_repository,
            self,
            language=self.language.value,
            dataset=self.session.current_dataset,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_form is None:
            return
        self.apply_form_to_tablet(dialog.selected_form)

    def apply_form_to_tablet(self, form) -> None:
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

    def _select_curve_mnemonics(self) -> list[str]:
        dataset = self.session.current_dataset
        if dataset is None:
            return []
        dialog = QDialog(self)
        dialog.setWindowTitle(self._t("tablet.select_curves_title"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self._t("tablet.select_curves_prompt")))
        curve_list = QListWidget()
        curve_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for curve in dataset.curves.values():
            curve_list.addItem(curve.metadata.original_mnemonic)
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
        return [item.text() for item in curve_list.selectedItems()]

    def calculate_ratios(self) -> None:
        try:
            created = self.session.calculate_basic_gas_ratios()
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
        DepthAnnotationsDialog(
            self.depth_annotation_controller, self, language=self.language
        ).exec()
        well = self.session.current_well
        self.tablet_view.set_canvas_objects(well.canvas_objects if well is not None else [])
        self._refresh_tree()
        self._update_title()

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
        ).exec()
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
        self.statusBar().showMessage(
            self._t(f"interpretations.mode_{mode.value}_hint")
        )

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
            interpretation = self.interpretation_controller.select_interpretation(
                interpretation_id
            )
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
        self.statusBar().showMessage(
            self._t("interpretations.undo_done", description=description)
        )

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
        self.statusBar().showMessage(
            self._t("interpretations.redo_done", description=description)
        )

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

    def _select_interpretation_interval(
        self, interpretation_id: str, interval_id: str
    ) -> None:
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
            self._select_interpretation_interval(
                selected_interpretation_id, selected_interval_id
            )
        else:
            self._clear_interpretation_interval_selection()
        self._refresh_tree()
        self._update_title()
        self._update_interpretation_history_actions()

    def show_sensor_catalog(self) -> None:
        dialog = SensorCatalogDialog(
            self.curve_browser.sensor_catalog, self, language=self.language, registry=self.mnemonic_registry
        )
        dialog.catalog_changed.connect(self._apply_sensor_catalog)
        dialog.exec()

    def _apply_sensor_catalog(self, catalog: object) -> None:
        if not isinstance(catalog, SensorCatalog):
            return
        set_active_sensor_catalog(catalog)
        self.curve_browser.set_sensor_catalog(catalog)
        self.statusBar().showMessage(
            self._t("sensors.applied", count=len(catalog.sensors))
        )

    def show_description_templates(self) -> None:
        DescriptionTemplatesDialog(
            self.description_template_controller, self, language=self.language
        ).exec()
        self._refresh_tree()
        self._update_title()

    def create_ascending_depth_copy(self) -> None:
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

    def create_resampled_depth_copy(self) -> None:
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

    def show_dataset_merge(self) -> None:
        if self.session.current_dataset is None:
            QMessageBox.information(self, self._t("merge.title"), self._t("data.select_dataset"))
            return
        dialog = DatasetMergeDialog(self.dataset_merge_controller, self, language=self.language)
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or dialog.analysis is None
            or dialog.source_dataset_id is None
        ):
            return
        try:
            result = self.dataset_merge_controller.create(dialog.source_dataset_id, dialog.analysis)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("merge.title"), str(exc))
            return
        self._after_dataset_merge(self._t("merge.completed", name=result.name))

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
            annotations = [
                item for item in well.canvas_objects if item.object_type == "depth_annotation"
            ]
            if annotations:
                annotations_item = QTreeWidgetItem(
                    [self._t("annotations.tree", count=len(annotations))]
                )
                annotations_item.setData(0, Qt.ItemDataRole.UserRole, ("annotations", well.well_id))
                well_item.addChild(annotations_item)
                for annotation in annotations:
                    text = str(annotation.properties.get("text", self._t("annotations.default")))
                    depth = (
                        annotation.top_depth if annotation.top_depth is not None else annotation.y
                    )
                    child = QTreeWidgetItem([f"{depth:g} м: {text}"])
                    child.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        ("annotation", well.well_id, annotation.object_id),
                    )
                    annotations_item.addChild(child)
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
                (item for item in dataset.curves.values() if item.metadata.original_mnemonic == mnemonic),
                None,
            )
        if curve is None:
            self._show_track_in_inspector(track_id)
            return
        self._selected_track_id = track_id
        self.inspector.setPlainText(
            f"{self._t('inspector.curve')}: {curve.metadata.original_mnemonic}\n"
            f"{self._t('inspector.unit')}: {curve.metadata.unit or self._t('common.unset')}\n"
            f"{self._t('inspector.description')}: "
            f"{curve.metadata.description or self._t('common.none')}\n"
            f"{self._t('inspector.version')}: {curve.version}\n"
            f"{self._t('inspector.provenance')}: {curve.metadata.provenance}"
        )

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
        self.statusBar().showMessage(f"Видимый интервал: {top_text}–{bottom_text}")

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
