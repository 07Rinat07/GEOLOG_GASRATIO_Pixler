from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
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
from geoworkbench.data.las_export_plan import ExportIssueSeverity
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.data_inspector_controller import DataInspectorController
from geoworkbench.project.curve_metadata_controller import CurveMetadataController
from geoworkbench.project.header_editing_controller import HeaderEditingController
from geoworkbench.project.description_template_controller import DescriptionTemplateController
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.curve_editing_controller import (
    CurveEditingController,
    CurveEditOutcome,
)
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.las_range_editor import LasRangeEditingController
from geoworkbench.project.dataset_export_controller import DatasetExportController
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_codec import ProjectFormatError
from geoworkbench.tablet import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.lithology_legend import build_lithology_legend
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.track_inspector import TrackInspector
from geoworkbench.ui.branding import application_icon, logo_pixmap
from geoworkbench.ui.csv_import_dialog import CsvImportDialog
from geoworkbench.ui.formula_dialog import FormulaExecutionDialog
from geoworkbench.ui.depth_annotations_dialog import DepthAnnotationsDialog
from geoworkbench.ui.description_templates_dialog import DescriptionTemplatesDialog
from geoworkbench.ui.data_inspector_dialog import DataInspectorDialog
from geoworkbench.ui.interval_statistics_dialog import IntervalStatisticsDialog
from geoworkbench.ui.lithology_dialog import LithologyDialog
from geoworkbench.ui.lithology_legend_dialog import LithologyLegendDialog
from geoworkbench.ui.lithotype_catalog_dialog import LithotypeCatalogDialog
from geoworkbench.ui.las_table_editor import LasTableEditor
from geoworkbench.ui.las_export_dialog import LasExportPlanDialog
from geoworkbench.visualization.curve_view import CurveView
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project_controller = ProjectController()
        self.tablet_controller = TabletController(self.session)
        self.curve_editing_controller = CurveEditingController(self.session)
        self.dataset_export_controller = DatasetExportController(self.session)
        self.data_inspector_controller = DataInspectorController(self.session)
        self.header_editing_controller = HeaderEditingController(self.session)
        self.curve_metadata_controller = CurveMetadataController(self.session)
        self.formula_registry = build_all_sourced_formula_registry()
        self.formula_execution_controller = FormulaExecutionController(
            self.session, self.formula_registry
        )
        self.depth_annotation_controller = DepthAnnotationController(self.session)
        self.lithology_controller = LithologyController(self.session)
        self.lithotype_catalog_controller = LithotypeCatalogController(self.session)
        self.description_template_controller = DescriptionTemplateController(self.session)
        self.depth_axis_controller = DepthAxisController(self.session)
        self.las_range_editing_controller = LasRangeEditingController(self.session)
        self._selected_track_id: str | None = None
        self.setWindowIcon(application_icon())
        self.setWindowTitle(f"GEOLOG GASRATIO@Pixler {__version__}")
        self.resize(1580, 960)

        self.tabs = QTabWidget()
        self.curve_view = CurveView()
        self.curve_view.edit_requested.connect(self._apply_curve_draw_edit)
        self.tablet_view = TabletView()
        self.tablet_view.track_selected.connect(self._show_track_in_inspector)
        self.tablet_view.track_width_change_requested.connect(self._change_track_width_from_drag)
        self.tablet_view.visible_depth_changed.connect(self._show_visible_depth)
        self.las_table_editor = LasTableEditor(self.las_range_editing_controller)
        self.las_table_editor.dataset_edited.connect(self._after_table_edit)
        self.las_table_editor.edit_failed.connect(
            lambda message: QMessageBox.warning(self, "LAS Editor", message)
        )
        self.tabs.addTab(self.curve_view, "LAS / Газовые кривые")
        self.tabs.addTab(self.las_table_editor, "LAS таблица")
        self.tabs.addTab(self.tablet_view, "Планшет")
        self.setCentralWidget(self.tabs)

        self._create_project_explorer()
        self._create_inspector()
        self._create_issues_panel()
        self._create_actions()
        self._create_toolbar()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готово: откройте LAS-файл")
        self._update_title()

    @property
    def session(self) -> ProjectSession:
        return self.project_controller.session

    @property
    def project_path(self) -> Path | None:
        return self.project_controller.project_path

    def _create_project_explorer(self) -> None:
        dock = QDockWidget("Проект", self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project Explorer")
        self.tree.itemDoubleClicked.connect(self._activate_tree_item)
        dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self._refresh_tree()

    def _create_inspector(self) -> None:
        dock = QDockWidget("Инспектор", self)
        self.inspector = TrackInspector()
        self.inspector.settings_requested.connect(self._apply_inspector_track_settings)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _create_issues_panel(self) -> None:
        dock = QDockWidget("Ошибки и журнал", self)
        self.issues = QTextEdit()
        self.issues.setReadOnly(True)
        dock.setWidget(self.issues)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def _create_actions(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        edit_menu = self.menuBar().addMenu("Правка")
        calc_menu = self.menuBar().addMenu("Расчёты")
        tablet_menu = self.menuBar().addMenu("Планшет")
        help_menu = self.menuBar().addMenu("Справка")

        self.open_project_action = QAction("Открыть проект...", self)
        self.open_project_action.setShortcut("Ctrl+O")
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)

        self.open_action = QAction("Импортировать LAS...", self)
        self.open_action.setShortcut("Ctrl+L")
        self.open_action.triggered.connect(self.open_las)
        file_menu.addAction(self.open_action)

        self.open_csv_action = QAction("Импортировать CSV/TXT...", self)
        self.open_csv_action.triggered.connect(self.open_csv)
        file_menu.addAction(self.open_csv_action)

        self.save_action = QAction("Сохранить проект как...", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_project_as)
        file_menu.addAction(self.save_action)

        self.export_las_action = QAction("Экспортировать текущий dataset в LAS...", self)
        self.export_las_action.triggered.connect(self.export_current_las)
        file_menu.addAction(self.export_las_action)

        self.data_inspector_action = QAction("Сведения о данных и индексах...", self)
        self.data_inspector_action.triggered.connect(self.show_data_inspector)
        file_menu.addAction(self.data_inspector_action)

        self.pencil_action = QAction("Карандаш кривой", self)
        self.pencil_action.setCheckable(True)
        self.pencil_action.setShortcut("E")
        self.pencil_action.toggled.connect(self.toggle_curve_edit_mode)
        edit_menu.addAction(self.pencil_action)

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

        self.annotations_action = QAction("Глубинные заметки...", self)
        self.annotations_action.triggered.connect(self.show_depth_annotations)
        edit_menu.addAction(self.annotations_action)

        self.lithology_action = QAction("Литологические интервалы...", self)
        self.lithology_action.triggered.connect(self.show_lithology_editor)
        edit_menu.addAction(self.lithology_action)

        self.lithotype_catalog_action = QAction("Справочник пород и литотипов...", self)
        self.lithotype_catalog_action.triggered.connect(self.show_lithotype_catalog)
        edit_menu.addAction(self.lithotype_catalog_action)

        self.description_templates_action = QAction("Шаблоны описаний пород...", self)
        self.description_templates_action.triggered.connect(self.show_description_templates)
        edit_menu.addAction(self.description_templates_action)

        self.normalize_depth_action = QAction(
            "Создать копию с глубиной по возрастанию...", self
        )
        self.normalize_depth_action.triggered.connect(self.create_ascending_depth_copy)
        edit_menu.addAction(self.normalize_depth_action)

        self.ratio_action = QAction("Рассчитать базовые Gas Ratio", self)
        self.ratio_action.triggered.connect(self.calculate_ratios)
        calc_menu.addAction(self.ratio_action)

        self.formula_action = QAction("Профили формул и расчёт...", self)
        self.formula_action.triggered.connect(self.show_formula_profiles)
        calc_menu.addAction(self.formula_action)

        self.interval_statistics_action = QAction("Статистика видимого интервала...", self)
        self.interval_statistics_action.triggered.connect(self.show_interval_statistics)
        calc_menu.addAction(self.interval_statistics_action)

        self.default_tablet_action = QAction("Построить базовый планшет", self)
        self.default_tablet_action.triggered.connect(self.build_default_tablet)
        tablet_menu.addAction(self.default_tablet_action)

        self.lithology_legend_action = QAction("Легенда пород...", self)
        self.lithology_legend_action.triggered.connect(self.show_lithology_legend)
        tablet_menu.addAction(self.lithology_legend_action)

        add_track_menu = QMenu("Добавить трек", self)
        tablet_menu.addMenu(add_track_menu)
        for title, kind in (
            ("Глубина", TrackKind.DEPTH),
            ("Газовые компоненты", TrackKind.GAS),
            ("DEXP / NCT", TrackKind.DEXP),
            ("Литология", TrackKind.LITHOLOGY),
            ("Описание пород", TrackKind.TEXT),
            ("Кривая", TrackKind.CURVE),
        ):
            action = QAction(title, self)
            action.triggered.connect(lambda _checked=False, value=kind: self.add_track(value))
            add_track_menu.addAction(action)

        tablet_menu.addSeparator()
        width_action = QAction("Изменить ширину выбранного трека...", self)
        width_action.triggered.connect(self.change_selected_track_width)
        tablet_menu.addAction(width_action)

        linear_scale_action = QAction("Линейная шкала выбранного трека", self)
        linear_scale_action.triggered.connect(
            lambda: self.set_selected_track_x_scale(XScale.LINEAR)
        )
        tablet_menu.addAction(linear_scale_action)

        log_scale_action = QAction("Логарифмическая шкала выбранного трека", self)
        log_scale_action.triggered.connect(
            lambda: self.set_selected_track_x_scale(XScale.LOGARITHMIC)
        )
        tablet_menu.addAction(log_scale_action)

        range_action = QAction("Задать диапазон X выбранного трека...", self)
        range_action.triggered.connect(self.change_selected_track_x_range)
        tablet_menu.addAction(range_action)

        auto_range_action = QAction("Автоматический диапазон X выбранного трека", self)
        auto_range_action.triggered.connect(self.reset_selected_track_x_range)
        tablet_menu.addAction(auto_range_action)

        move_left_action = QAction("Переместить выбранный трек влево", self)
        move_left_action.triggered.connect(lambda: self.move_selected_track(-1))
        tablet_menu.addAction(move_left_action)

        move_right_action = QAction("Переместить выбранный трек вправо", self)
        move_right_action.triggered.connect(lambda: self.move_selected_track(1))
        tablet_menu.addAction(move_right_action)

        hide_action = QAction("Скрыть выбранный трек", self)
        hide_action.triggered.connect(self.hide_selected_track)
        tablet_menu.addAction(hide_action)

        show_all_action = QAction("Показать все скрытые треки", self)
        show_all_action.triggered.connect(self.show_all_tracks)
        tablet_menu.addAction(show_all_action)

        remove_action = QAction("Удалить выбранный трек", self)
        remove_action.triggered.connect(self.remove_selected_track)
        tablet_menu.addAction(remove_action)

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Основная")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.default_tablet_action)
        toolbar.addAction(self.ratio_action)
        toolbar.addAction(self.save_action)
        self.addToolBar(toolbar)

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
                    raise LasImportError(
                        f"режим {import_mode.value} отклонил файл:\n  {messages}"
                    )
                if decision.requires_confirmation:
                    messages = "\n".join(
                        f"• {issue.message}" for issue in decision.review_issues
                    )
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
        self.build_default_tablet()
        self.inspector.setPlainText(
            f"Скважина: {last_well.name}\n"
            f"Набор: {last_dataset.name}\n"
            f"Кривых: {len(last_dataset.curves)}\n"
            f"Отсчётов: {len(last_dataset.depth)}\n"
            f"Диапазон: {last_dataset.depth[0]:.2f}–{last_dataset.depth[-1]:.2f}"
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
        dialog = CsvImportDialog(Path(filename), self)
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
        self.curve_editing_controller = CurveEditingController(self.session)
        self.dataset_export_controller.session = self.session
        self.data_inspector_controller.session = self.session
        self.header_editing_controller.session = self.session
        self.header_editing_controller.clear_history()
        self.curve_metadata_controller.session = self.session
        self.curve_metadata_controller.clear_history()
        self.formula_execution_controller.session = self.session
        self.depth_annotation_controller.session = self.session
        self.depth_annotation_controller.history.clear()
        self.lithology_controller.session = self.session
        self.lithotype_catalog_controller.session = self.session
        self.description_template_controller.session = self.session
        self.depth_axis_controller.session = self.session
        self.las_range_editing_controller.session = self.session
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
            return
        self.curve_view.show_dataset(dataset)
        self.las_table_editor.set_dataset(dataset)
        self.tablet_view.set_dataset(dataset)
        well = self.session.current_well
        self.tablet_view.set_canvas_objects(well.canvas_objects if well is not None else [])
        self.tablet_view.set_lithology(
            well.lithology if well is not None else [],
            self.lithotype_catalog_controller.available(),
        )
        saved_layout = self.session.current_tablet_layout
        if saved_layout is None:
            self.build_default_tablet()
        else:
            self.tablet_view.set_layout_model(saved_layout)
        self.tabs.setCurrentWidget(self.tablet_view)

    def export_current_las(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Экспорт LAS", "Сначала выберите набор данных")
            return
        plan_dialog = LasExportPlanDialog(
            self,
            initial=self.dataset_export_controller.default_las_plan(),
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
            QMessageBox.critical(self, "Экспорт LAS невозможен", "\n".join(errors))
            return
        warnings = [
            issue.message
            for issue in analysis.issues
            if issue.severity is ExportIssueSeverity.WARNING
        ]
        if warnings:
            answer = QMessageBox.question(
                self,
                "Предупреждения экспорта LAS",
                "\n".join(warnings) + "\n\nПродолжить экспорт?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
        initial = Path.cwd() / f"{dataset.name}_edited.las"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Экспортировать LAS",
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
                "Экспорт LAS",
                f"Файл уже существует:\n{target.name}\n\nЗаменить его?",
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
            QMessageBox.critical(self, "Экспорт LAS", str(exc))
            self._log(f"LAS не экспортирован: {exc}")
            return
        self._log(f"LAS экспортирован: {exported}")
        self.statusBar().showMessage(f"LAS экспортирован: {exported.name}")

    def show_data_inspector(self) -> None:
        if self.session.current_dataset is None:
            QMessageBox.information(self, "Сведения о данных", "Сначала выберите dataset")
            return
        DataInspectorDialog(
            self.data_inspector_controller,
            self.header_editing_controller,
            self.curve_metadata_controller,
            self,
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

    def build_default_tablet(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Планшет", "Сначала откройте LAS-файл")
            return

        layout = self.tablet_controller.build_default_layout()
        self.tablet_view.set_layout_model(layout)
        self.tablet_view.set_dataset(dataset)
        self._refresh_tree()
        self._update_title()
        self._log(f"Построен базовый планшет: треков {len(layout.tracks)}")

    def add_track(self, kind: TrackKind) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Планшет", "Сначала откройте LAS-файл")
            return

        mnemonics = self._select_curve_mnemonics() if kind is TrackKind.CURVE else []
        if kind is TrackKind.CURVE and not mnemonics:
            return

        try:
            track = self.tablet_controller.add_track(kind, mnemonics)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Планшет", str(exc))
            return
        self.tablet_view.refresh_view()
        self._refresh_tree()
        self.tabs.setCurrentWidget(self.tablet_view)
        self._log(f"Добавлен трек: {track.title}")
        self._update_title()

    def change_selected_track_width(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        width, accepted = QInputDialog.getInt(
            self, "Ширина трека", "Ширина, px:", track.width, 80, 2000, 10
        )
        if accepted:
            self.tablet_controller.set_track_width(track.track_id, width)
            self._layout_changed(f"Изменена ширина трека {track.title}: {width}px")

    def _change_track_width_from_drag(self, track_id: str, width: int) -> None:
        try:
            track = self.tablet_view.layout_model.track_by_id(track_id)
            self.tablet_controller.set_track_width(track_id, width)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Ширина трека", str(exc))
            self.tablet_view.refresh_view()
            return
        self._layout_changed(f"Изменена ширина трека {track.title}: {width}px")

    def move_selected_track(self, offset: int) -> None:
        track = self._selected_track()
        if track is None:
            return
        if self.tablet_controller.move_track(track.track_id, offset):
            self._layout_changed(f"Перемещён трек: {track.title}")

    def set_selected_track_x_scale(self, scale: XScale) -> None:
        track = self._selected_track()
        if track is None:
            return
        try:
            self.tablet_controller.set_track_x_scale(track.track_id, scale)
        except ValueError as exc:
            QMessageBox.warning(self, "Шкала трека", str(exc))
            return
        scale_name = "логарифмическая" if scale is XScale.LOGARITHMIC else "линейная"
        self._layout_changed(f"Шкала трека {track.title}: {scale_name}")

    def change_selected_track_x_range(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        default_minimum = track.x_min if track.x_min is not None else 0.1
        default_maximum = track.x_max if track.x_max is not None else 100.0
        minimum, accepted = QInputDialog.getDouble(
            self, "Диапазон X", "Минимум:", default_minimum, -1e300, 1e300, 6
        )
        if not accepted:
            return
        maximum, accepted = QInputDialog.getDouble(
            self, "Диапазон X", "Максимум:", default_maximum, -1e300, 1e300, 6
        )
        if not accepted:
            return
        try:
            self.tablet_controller.set_track_x_range(track.track_id, minimum, maximum)
        except ValueError as exc:
            QMessageBox.warning(self, "Диапазон трека", str(exc))
            return
        self._layout_changed(f"Диапазон трека {track.title}: {minimum:g}–{maximum:g}")

    def reset_selected_track_x_range(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        self.tablet_controller.set_track_x_range(track.track_id, None, None)
        self._layout_changed(f"Автоматический диапазон трека: {track.title}")

    def hide_selected_track(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        self.tablet_controller.hide_track(track.track_id)
        self._selected_track_id = None
        self._layout_changed(f"Скрыт трек: {track.title}")

    def show_all_tracks(self) -> None:
        restored_count = self.tablet_controller.show_all_tracks()
        if restored_count == 0:
            self.statusBar().showMessage("Скрытых треков нет")
            return
        self._layout_changed(f"Показано скрытых треков: {restored_count}")

    def remove_selected_track(self) -> None:
        track = self._selected_track()
        if track is None:
            return
        self.tablet_controller.remove_track(track.track_id)
        self._selected_track_id = None
        self._layout_changed(f"Удалён трек: {track.title}")

    def _selected_track(self) -> TrackDefinition | None:
        if self._selected_track_id is None:
            QMessageBox.information(self, "Планшет", "Сначала выберите трек на планшете")
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
        dialog.setWindowTitle("Выбор кривых трека")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Выберите одну или несколько кривых:"))
        curve_list = QListWidget()
        curve_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for curve in dataset.curves.values():
            curve_list.addItem(curve.metadata.original_mnemonic)
        layout.addWidget(curve_list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
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
            QMessageBox.warning(self, "Gas Ratio", str(exc))
            self._log(f"Расчёт не выполнен: {exc}")
            return

        dataset = self.session.current_dataset
        assert dataset is not None
        self.curve_view.show_dataset(dataset, created)
        self.tablet_view.set_dataset(dataset)
        self._log(f"Созданы/обновлены кривые: {', '.join(created)}")
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage("Базовые Gas Ratio пересчитаны")

    def show_formula_profiles(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Расчёт формулы", "Сначала выберите набор данных")
            return
        dialog = FormulaExecutionDialog(
            dataset,
            self.formula_registry,
            self.formula_execution_controller,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.execution_result is None:
            return
        result = dialog.execution_result
        self.curve_view.show_dataset(dataset, [result.output_mnemonic])
        self.tablet_view.set_dataset(dataset)
        self._refresh_tree()
        self._update_title()
        self._log(f"Рассчитана кривая {result.output_mnemonic}: {result.profile_id}")
        self.statusBar().showMessage(f"Рассчитана кривая {result.output_mnemonic}")

    def show_interval_statistics(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Статистика", "Сначала выберите набор данных")
            return
        visible_range = self.tablet_view.visible_depth_range
        if visible_range is None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size == 0:
                QMessageBox.warning(self, "Статистика", "В наборе нет корректной глубины")
                return
            depth_top, depth_bottom = float(np.min(finite_depth)), float(np.max(finite_depth))
        else:
            depth_top, depth_bottom = visible_range
        try:
            statistics = calculate_interval_statistics(dataset, depth_top, depth_bottom)
        except ValueError as exc:
            QMessageBox.warning(self, "Статистика", str(exc))
            return
        if not statistics:
            QMessageBox.information(self, "Статистика", "В интервале нет числовых кривых")
            return
        IntervalStatisticsDialog(depth_top, depth_bottom, statistics, self).exec()

    def show_depth_annotations(self) -> None:
        if self.session.current_well is None:
            QMessageBox.information(self, "Заметки", "Сначала выберите скважину")
            return
        DepthAnnotationsDialog(self.depth_annotation_controller, self).exec()
        well = self.session.current_well
        self.tablet_view.set_canvas_objects(well.canvas_objects if well is not None else [])
        self._refresh_tree()
        self._update_title()

    def show_lithology_editor(self) -> None:
        if self.session.current_well is None:
            QMessageBox.information(self, "Литология", "Сначала выберите скважину")
            return
        LithologyDialog(
            self.lithology_controller,
            self,
            catalog=self.lithotype_catalog_controller.available(),
            description_templates=self.description_template_controller.available(),
        ).exec()
        well = self.session.current_well
        self.tablet_view.set_lithology(
            well.lithology if well is not None else [],
            self.lithotype_catalog_controller.available(),
        )
        self._refresh_tree()
        self._update_title()

    def show_lithotype_catalog(self) -> None:
        LithotypeCatalogDialog(self.lithotype_catalog_controller, self).exec()
        well = self.session.current_well
        self.tablet_view.set_lithology(
            well.lithology if well is not None else [],
            self.lithotype_catalog_controller.available(),
        )
        self._update_title()

    def show_description_templates(self) -> None:
        DescriptionTemplatesDialog(self.description_template_controller, self).exec()
        self._refresh_tree()
        self._update_title()

    def create_ascending_depth_copy(self) -> None:
        try:
            report = self.depth_axis_controller.analyze_current()
        except RuntimeError as exc:
            QMessageBox.information(self, "Порядок глубины", str(exc))
            return
        if report.direction is not DepthDirection.DESCENDING:
            QMessageBox.information(
                self,
                "Порядок глубины",
                f"Автоматический разворот не требуется: {report.direction.value}",
            )
            return
        answer = QMessageBox.question(
            self,
            "Создать исправленную копию",
            "Будет создан новый dataset с возрастающей глубиной и развёрнутыми кривыми. "
            "Исходный LAS и исходный dataset останутся без изменений. Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.depth_axis_controller.create_ascending_copy()
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Порядок глубины", str(exc))
            return
        self._show_current_dataset()
        self._refresh_tree()
        self._update_title()
        self._log(f"Создана копия с возрастающей глубиной: {result.name}")

    def show_lithology_legend(self) -> None:
        well = self.session.current_well
        intervals = well.lithology if well is not None else []
        entries = build_lithology_legend(
            intervals, self.lithotype_catalog_controller.available()
        )
        LithologyLegendDialog(entries, self).exec()

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
                [f"Шаблоны описаний ({len(self.session.project.description_templates)})"]
            )
            templates_item.setData(0, Qt.ItemDataRole.UserRole, ("description_templates",))
            root.addChild(templates_item)
            for name in sorted(
                self.session.project.description_templates, key=str.casefold
            ):
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
                        track_item = QTreeWidgetItem(
                            [f"{position}. {track.title}{state}"]
                        )
                        track_item.setData(
                            0,
                            Qt.ItemDataRole.UserRole,
                            ("track", well.well_id, dataset.dataset_id, track.track_id),
                        )
                        tracks_item.addChild(track_item)
            if well.lithology:
                lithology_item = QTreeWidgetItem(
                    [f"Литология ({len(well.lithology)})"]
                )
                lithology_item.setData(
                    0, Qt.ItemDataRole.UserRole, ("lithology", well.well_id)
                )
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
            annotations = [
                item for item in well.canvas_objects if item.object_type == "depth_annotation"
            ]
            if annotations:
                annotations_item = QTreeWidgetItem(
                    [f"Глубинные заметки ({len(annotations)})"]
                )
                annotations_item.setData(
                    0, Qt.ItemDataRole.UserRole, ("annotations", well.well_id)
                )
                well_item.addChild(annotations_item)
                for annotation in annotations:
                    text = str(annotation.properties.get("text", "Заметка"))
                    depth = annotation.top_depth if annotation.top_depth is not None else annotation.y
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
                    f"Кривая: {mnemonic}\n"
                    f"Единица: {curve.metadata.unit or 'не задана'}\n"
                    f"Описание: {curve.metadata.description or 'нет'}\n"
                    f"Версия: {curve.version}\n"
                    f"Происхождение: {curve.metadata.provenance}"
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
        elif data[0] in ("annotations", "annotation"):
            self.session.current_well_id = data[1]
            self.show_depth_annotations()
        elif data[0] == "description_templates":
            self.show_description_templates()

    def _show_track_in_inspector(self, track_id: str) -> None:
        self._selected_track_id = track_id
        track = next(
            (item for item in self.tablet_view.layout_model.tracks if item.track_id == track_id),
            None,
        )
        if track is None:
            return
        self.inspector.show_track(track)

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
            QMessageBox.warning(self, "Инспектор трека", str(exc))
            return
        self._layout_changed(f"Обновлены свойства трека: {track.title}")
        self.inspector.show_track(track)

    def _show_visible_depth(self, top: float, bottom: float) -> None:
        if self.tablet_controller.set_visible_depth(top, bottom):
            self._update_title()
        self.statusBar().showMessage(f"Видимый интервал: {top:.2f}–{bottom:.2f} м")

    def _update_title(self) -> None:
        marker = " *" if self.session.dirty else ""
        self.setWindowTitle(
            f"GEOLOG GASRATIO@Pixler {__version__} — {self.session.project.name}{marker}"
        )

    def _log(self, text: str) -> None:
        self.issues.append(text)

    def show_about(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("GEOLOG GASRATIO@Pixler")
        dialog.setIconPixmap(logo_pixmap(280))
        dialog.setText(
            f"Версия {__version__}\n\n"
            "Автор: Сармулдин Ринат\n"
            "E-mail: ura07srr@gmail.com\n\n"
            "Реализовано: загрузка и безопасный экспорт LAS, базовые Gas Ratio, "
            "версионированные проекты, многотрековый планшет и редактор кривых с Undo/Redo."
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()
