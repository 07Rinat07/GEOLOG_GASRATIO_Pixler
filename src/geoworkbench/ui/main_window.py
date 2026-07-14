from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
)

from geoworkbench import __version__
from geoworkbench.data.las_adapter import LasImportError, import_las
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage import ProjectFormatError, load_project, save_project
from geoworkbench.visualization.curve_view import CurveView


ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_WELL_ID = Qt.ItemDataRole.UserRole + 1
ROLE_DATASET_ID = Qt.ItemDataRole.UserRole + 2
ROLE_CURVE_ID = Qt.ItemDataRole.UserRole + 3


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.session = ProjectSession()
        self.project_path: Path | None = None
        self.resize(1500, 920)

        self.tabs = QTabWidget()
        self.curve_view = CurveView()
        self.tabs.addTab(self.curve_view, "LAS / Газовые кривые")
        self.tabs.addTab(QLabel("Многотрековый планшет реализуется следующим инкрементом"), "Планшет")
        self.setCentralWidget(self.tabs)

        self._create_project_explorer()
        self._create_inspector()
        self._create_issues_panel()
        self._create_actions()
        self._create_toolbar()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готово: создайте проект или откройте LAS-файл")
        self._refresh_tree()
        self._update_title()

    def _create_project_explorer(self) -> None:
        dock = QDockWidget("Проект", self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project Explorer")
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _create_inspector(self) -> None:
        dock = QDockWidget("Инспектор", self)
        self.inspector = QTextEdit()
        self.inspector.setReadOnly(True)
        self.inspector.setPlainText("Выберите проект, скважину, набор данных или кривую")
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
        calc_menu = self.menuBar().addMenu("Расчёты")
        help_menu = self.menuBar().addMenu("Справка")

        self.new_action = QAction("Новый проект", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_project)
        file_menu.addAction(self.new_action)

        self.open_project_action = QAction("Открыть проект...", self)
        self.open_project_action.setShortcut("Ctrl+Shift+O")
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)

        self.open_las_action = QAction("Добавить LAS...", self)
        self.open_las_action.setShortcut("Ctrl+O")
        self.open_las_action.triggered.connect(self.open_las)
        file_menu.addAction(self.open_las_action)

        file_menu.addSeparator()

        self.save_action = QAction("Сохранить", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_project)
        file_menu.addAction(self.save_action)

        self.save_as_action = QAction("Сохранить проект как...", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(self.save_as_action)

        self.ratio_action = QAction("Рассчитать базовые Gas Ratio", self)
        self.ratio_action.triggered.connect(self.calculate_ratios)
        calc_menu.addAction(self.ratio_action)

        pixler_action = QAction("Pixler: профили формул", self)
        pixler_action.triggered.connect(self.show_pixler_status)
        calc_menu.addAction(pixler_action)

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Основная")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.open_las_action)
        toolbar.addSeparator()
        toolbar.addAction(self.ratio_action)
        toolbar.addSeparator()
        toolbar.addAction(self.save_action)
        self.addToolBar(toolbar)

    def _confirm_discard_changes(self) -> bool:
        if not self.session.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Несохранённые изменения",
            "В проекте есть несохранённые изменения. Продолжить без сохранения?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def new_project(self) -> None:
        if not self._confirm_discard_changes():
            return
        self.session.new_project()
        self.project_path = None
        self.curve_view.clear_view()
        self.inspector.setPlainText("Новый пустой проект")
        self._refresh_tree()
        self._update_title()
        self._log("Создан новый проект")

    def open_project(self) -> None:
        if not self._confirm_discard_changes():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект",
            "",
            "GeoLog Project (*.geolog.json);;JSON (*.json)",
        )
        if not filename:
            return
        try:
            project = load_project(filename)
        except (OSError, ProjectFormatError) as exc:
            QMessageBox.critical(self, "Ошибка проекта", str(exc))
            self._log(f"ОШИБКА открытия проекта: {exc}")
            return

        self.session.replace_project(project)
        self.project_path = Path(filename)
        self._refresh_tree()
        dataset = self.session.current_dataset
        if dataset is not None:
            self.curve_view.show_dataset(dataset)
            self._show_dataset_inspector(dataset)
        else:
            self.curve_view.clear_view()
        self._update_title()
        self._log(f"Открыт проект: {filename}")
        self.statusBar().showMessage(f"Открыт проект {Path(filename).name}")

    def open_las(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(self, "Добавить LAS", "", "LAS (*.las)")
        if not filenames:
            return
        loaded = 0
        last_dataset = None
        last_well = None
        for filename in filenames:
            try:
                dataset = import_las(filename)
                well = self.session.add_dataset(dataset)
            except (OSError, LasImportError) as exc:
                self._log(f"ОШИБКА LAS {filename}: {exc}")
                continue
            loaded += 1
            last_dataset = dataset
            last_well = well
            self._log(f"Загружен LAS: {filename}")

        if loaded == 0 or last_dataset is None or last_well is None:
            QMessageBox.warning(self, "LAS", "Ни один LAS-файл не был загружен")
            return

        self.curve_view.show_dataset(last_dataset)
        self._show_dataset_inspector(last_dataset, last_well.name)
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage(f"Загружено LAS-файлов: {loaded}")

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
        self._log(f"Созданы/обновлены кривые: {', '.join(created)}")
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage("Базовые Gas Ratio пересчитаны")

    def show_pixler_status(self) -> None:
        QMessageBox.information(
            self,
            "Pixler",
            "Движок профилей Pixler создан. Формулы добавляются только вместе с "
            "подтверждённой методикой, источником, единицами и контрольным примером.",
        )

    def save_project(self) -> None:
        if self.project_path is None:
            self.save_project_as()
            return
        self._write_project(self.project_path)

    def save_project_as(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект",
            str(self.project_path or Path("project.geolog.json")),
            "GeoLog Project (*.geolog.json);;JSON (*.json)",
        )
        if not filename:
            return
        self.project_path = Path(filename)
        self._write_project(self.project_path)

    def _write_project(self, path: Path) -> None:
        try:
            save_project(self.session.project, path)
        except OSError as exc:
            QMessageBox.critical(self, "Сохранение", str(exc))
            return
        self.session.dirty = False
        self._update_title()
        self._log(f"Проект сохранён: {path}")
        self.statusBar().showMessage(f"Проект сохранён: {path.name}")

    def _refresh_tree(self) -> None:
        self.tree.clear()
        root = QTreeWidgetItem([self.session.project.name])
        root.setData(0, ROLE_KIND, "project")
        self.tree.addTopLevelItem(root)
        for well in self.session.project.wells.values():
            well_item = QTreeWidgetItem([well.name])
            well_item.setData(0, ROLE_KIND, "well")
            well_item.setData(0, ROLE_WELL_ID, well.well_id)
            root.addChild(well_item)
            for dataset in well.datasets.values():
                dataset_item = QTreeWidgetItem([f"{dataset.name} ({dataset.kind.value})"])
                dataset_item.setData(0, ROLE_KIND, "dataset")
                dataset_item.setData(0, ROLE_WELL_ID, well.well_id)
                dataset_item.setData(0, ROLE_DATASET_ID, dataset.dataset_id)
                well_item.addChild(dataset_item)
                for curve in dataset.curves.values():
                    curve_item = QTreeWidgetItem([curve.metadata.original_mnemonic])
                    curve_item.setData(0, ROLE_KIND, "curve")
                    curve_item.setData(0, ROLE_WELL_ID, well.well_id)
                    curve_item.setData(0, ROLE_DATASET_ID, dataset.dataset_id)
                    curve_item.setData(0, ROLE_CURVE_ID, curve.metadata.curve_id)
                    dataset_item.addChild(curve_item)
        root.setExpanded(True)

    def _on_tree_selection(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            return
        item = selected[0]
        kind = item.data(0, ROLE_KIND)
        if kind == "project":
            self.inspector.setPlainText(
                f"Проект: {self.session.project.name}\nСкважин: {len(self.session.project.wells)}"
            )
            return
        if kind == "well":
            well = self.session.project.wells[item.data(0, ROLE_WELL_ID)]
            self.inspector.setPlainText(f"Скважина: {well.name}\nНаборов данных: {len(well.datasets)}")
            return

        well_id = item.data(0, ROLE_WELL_ID)
        dataset_id = item.data(0, ROLE_DATASET_ID)
        dataset = self.session.select_dataset(well_id, dataset_id)
        if kind == "dataset":
            self.curve_view.show_dataset(dataset)
            self._show_dataset_inspector(dataset)
            return
        if kind == "curve":
            curve_id = item.data(0, ROLE_CURVE_ID)
            curve = dataset.curves[curve_id]
            self.curve_view.show_dataset(dataset, [curve.metadata.original_mnemonic])
            finite = int((~__import__("numpy").isnan(curve.values)).sum())
            self.inspector.setPlainText(
                f"Кривая: {curve.metadata.original_mnemonic}\n"
                f"Каноническая мнемоника: {curve.metadata.canonical_mnemonic or '—'}\n"
                f"Единица: {curve.metadata.unit or '—'}\n"
                f"Описание: {curve.metadata.description or '—'}\n"
                f"Версия: {curve.version}\n"
                f"Происхождение: {curve.metadata.provenance}\n"
                f"Конечных значений: {finite}/{len(curve.values)}"
            )

    def _show_dataset_inspector(self, dataset, well_name: str | None = None) -> None:
        depth_range = "нет данных"
        if len(dataset.depth):
            depth_range = f"{dataset.depth[0]:.2f}–{dataset.depth[-1]:.2f}"
        self.inspector.setPlainText(
            (f"Скважина: {well_name}\n" if well_name else "")
            + f"Набор: {dataset.name}\n"
            + f"Тип: {dataset.kind.value}\n"
            + f"Кривых: {len(dataset.curves)}\n"
            + f"Отсчётов: {len(dataset.depth)}\n"
            + f"Диапазон: {depth_range}\n"
            + f"Источник: {dataset.source_path or '—'}"
        )

    def _update_title(self) -> None:
        marker = " *" if self.session.dirty else ""
        filename = f" — {self.project_path.name}" if self.project_path else ""
        self.setWindowTitle(
            f"GEOLOG GASRATIO@Pixler {__version__} — {self.session.project.name}{filename}{marker}"
        )

    def _log(self, text: str) -> None:
        self.issues.append(text)

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "GEOLOG GASRATIO@Pixler",
            f"Версия {__version__}\n\n"
            "Автор: Сармулдин Ринат\n"
            "E-mail: ura07srr@gmail.com\n\n"
            "LAS/ГИС, ГТИ, газовый каротаж, литология, шламограмма, "
            "стратиграфия, корреляция и мастерлоги.",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()
