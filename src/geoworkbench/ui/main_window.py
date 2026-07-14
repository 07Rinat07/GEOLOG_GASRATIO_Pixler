from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
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

from geoworkbench.data.las_adapter import LasImportError, import_las
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.visualization.curve_view import CurveView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.session = ProjectSession()
        self.project_path: Path | None = None
        self.setWindowTitle("GEOLOG GASRATIO@Pixler 0.2")
        self.resize(1500, 920)

        self.tabs = QTabWidget()
        self.curve_view = CurveView()
        self.tabs.addTab(self.curve_view, "LAS / Газовые кривые")
        self.tabs.addTab(QLabel("Планшет и мастерлог будут добавлены следующим инкрементом"), "Планшет")
        self.setCentralWidget(self.tabs)

        self._create_project_explorer()
        self._create_inspector()
        self._create_issues_panel()
        self._create_actions()
        self._create_toolbar()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готово: откройте LAS-файл")
        self._update_title()

    def _create_project_explorer(self) -> None:
        dock = QDockWidget("Проект", self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project Explorer")
        dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self._refresh_tree()

    def _create_inspector(self) -> None:
        dock = QDockWidget("Инспектор", self)
        self.inspector = QTextEdit()
        self.inspector.setReadOnly(True)
        self.inspector.setPlainText("Свойства выбранного LAS-набора и расчётов")
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

        self.open_action = QAction("Открыть LAS...", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_las)
        file_menu.addAction(self.open_action)

        self.save_action = QAction("Сохранить проект как...", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_project_as)
        file_menu.addAction(self.save_action)

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
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.ratio_action)
        toolbar.addAction(self.save_action)
        self.addToolBar(toolbar)

    def open_las(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Открыть LAS", "", "LAS (*.las)")
        if not filename:
            return
        try:
            dataset = import_las(filename)
            well = self.session.add_dataset(dataset)
        except (OSError, LasImportError) as exc:
            QMessageBox.critical(self, "Ошибка LAS", str(exc))
            self._log(f"ОШИБКА: {exc}")
            return

        self.curve_view.show_dataset(dataset)
        self.inspector.setPlainText(
            f"Скважина: {well.name}\n"
            f"Набор: {dataset.name}\n"
            f"Кривых: {len(dataset.curves)}\n"
            f"Отсчётов: {len(dataset.depth)}\n"
            f"Диапазон: {dataset.depth[0]:.2f}–{dataset.depth[-1]:.2f}"
        )
        self._log(f"Загружен LAS: {filename}")
        self._refresh_tree()
        self._update_title()
        self.statusBar().showMessage(f"Загружен {Path(filename).name}")

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
            "Движок профилей Pixler создан. Конкретные формулы не зашиты без "
            "подтверждённой методики и источника. Следующий шаг — добавить рабочий "
            "профиль формул с контрольным примером.",
        )

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
        try:
            save_project(self.session.project, self.project_path)
        except OSError as exc:
            QMessageBox.critical(self, "Сохранение", str(exc))
            return
        self.session.dirty = False
        self._update_title()
        self._log(f"Проект сохранён: {self.project_path}")

    def _refresh_tree(self) -> None:
        self.tree.clear()
        root = QTreeWidgetItem([self.session.project.name])
        self.tree.addTopLevelItem(root)
        for well in self.session.project.wells.values():
            well_item = QTreeWidgetItem([well.name])
            root.addChild(well_item)
            for dataset in well.datasets.values():
                dataset_item = QTreeWidgetItem([f"{dataset.name} ({dataset.kind.value})"])
                well_item.addChild(dataset_item)
                for curve in dataset.curves.values():
                    dataset_item.addChild(QTreeWidgetItem([curve.metadata.original_mnemonic]))
        root.setExpanded(True)

    def _update_title(self) -> None:
        marker = " *" if self.session.dirty else ""
        self.setWindowTitle(f"GEOLOG GASRATIO@Pixler 0.2 — {self.session.project.name}{marker}")

    def _log(self, text: str) -> None:
        self.issues.append(text)

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "GEOLOG GASRATIO@Pixler",
            "Версия 0.2\n\n"
            "Реализовано: загрузка LAS, просмотр кривых, базовые газовые отношения, "
            "расчётная сумма компонентов, проектная сессия и атомарное сохранение.",
        )
