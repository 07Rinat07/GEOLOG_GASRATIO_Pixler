from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
)

from geoworkbench.data.las_adapter import LasImportError, import_las
from geoworkbench.domain.models import new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.tablet import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.visualization.curve_view import CurveView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.session = ProjectSession()
        self.project_path: Path | None = None
        self.setWindowTitle("GEOLOG GASRATIO@Pixler 0.4")
        self.resize(1580, 960)

        self.tabs = QTabWidget()
        self.curve_view = CurveView()
        self.tablet_view = TabletView()
        self.tablet_view.track_selected.connect(self._show_track_in_inspector)
        self.tablet_view.visible_depth_changed.connect(self._show_visible_depth)
        self.tabs.addTab(self.curve_view, "LAS / Газовые кривые")
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
        self.inspector = QTextEdit()
        self.inspector.setReadOnly(True)
        self.inspector.setPlainText("Свойства выбранного набора, кривой или трека")
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
        tablet_menu = self.menuBar().addMenu("Планшет")
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

        self.default_tablet_action = QAction("Построить базовый планшет", self)
        self.default_tablet_action.triggered.connect(self.build_default_tablet)
        tablet_menu.addAction(self.default_tablet_action)

        add_track_menu = QMenu("Добавить трек", self)
        tablet_menu.addMenu(add_track_menu)
        for title, kind in (
            ("Глубина", TrackKind.DEPTH),
            ("Газовые компоненты", TrackKind.GAS),
            ("Кривая", TrackKind.CURVE),
        ):
            action = QAction(title, self)
            action.triggered.connect(lambda _checked=False, value=kind: self.add_track(value))
            add_track_menu.addAction(action)

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Основная")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.default_tablet_action)
        toolbar.addAction(self.ratio_action)
        toolbar.addAction(self.save_action)
        self.addToolBar(toolbar)

    def open_las(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(self, "Открыть LAS", "", "LAS (*.las)")
        if not filenames:
            return

        last_dataset = None
        last_well = None
        errors: list[str] = []
        for filename in filenames:
            try:
                dataset = import_las(filename)
                well = self.session.add_dataset(dataset)
                last_dataset = dataset
                last_well = well
                self._log(f"Загружен LAS: {filename}")
            except (OSError, LasImportError) as exc:
                errors.append(f"{Path(filename).name}: {exc}")
                self._log(f"ОШИБКА: {filename}: {exc}")

        if last_dataset is None or last_well is None:
            QMessageBox.critical(self, "Ошибка LAS", "\n".join(errors) or "Файлы не загружены")
            return

        self.curve_view.show_dataset(last_dataset)
        self.tablet_view.set_dataset(last_dataset)
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
        self._refresh_tree()
        self._update_title()
        self.tabs.setCurrentWidget(self.tablet_view)
        self.statusBar().showMessage(f"Загружено LAS-файлов: {len(filenames) - len(errors)}")

    def build_default_tablet(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Планшет", "Сначала откройте LAS-файл")
            return

        curve_names = [curve.metadata.original_mnemonic for curve in dataset.curves.values()]
        gas_order = ["TG", "TOTALGAS", "TG_CALC", "C1", "C2", "C3", "IC4", "NC4", "C4", "IC5", "NC5", "C5"]
        gas_names = [name for name in gas_order if dataset.curve_by_mnemonic(name) is not None]
        remaining = [name for name in curve_names if name not in gas_names]

        tracks = [
            TrackDefinition(new_id(), "Глубина", TrackKind.DEPTH, width=120),
        ]
        if gas_names:
            tracks.append(
                TrackDefinition(new_id(), "Газ", TrackKind.GAS, curve_mnemonics=gas_names[:8], width=360)
            )
        for mnemonic in remaining[:3]:
            tracks.append(
                TrackDefinition(new_id(), mnemonic, TrackKind.CURVE, curve_mnemonics=[mnemonic], width=250)
            )

        self.tablet_view.set_layout_model(TabletLayout(tracks))
        self.tablet_view.set_dataset(dataset)
        self._log(f"Построен базовый планшет: треков {len(tracks)}")

    def add_track(self, kind: TrackKind) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Планшет", "Сначала откройте LAS-файл")
            return

        mnemonics: list[str] = []
        title = kind.value
        width = 250
        if kind == TrackKind.DEPTH:
            title = "Глубина"
            width = 120
        elif kind == TrackKind.GAS:
            title = "Газ"
            for name in ("TG", "TG_CALC", "C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5"):
                if dataset.curve_by_mnemonic(name) is not None:
                    mnemonics.append(name)
            width = 360
        else:
            first = next(iter(dataset.curves.values()), None)
            if first is not None:
                title = first.metadata.original_mnemonic
                mnemonics = [title]

        try:
            self.tablet_view.add_track(
                TrackDefinition(new_id(), title, kind, curve_mnemonics=mnemonics, width=width)
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Планшет", str(exc))
            return
        self.tabs.setCurrentWidget(self.tablet_view)
        self._log(f"Добавлен трек: {title}")

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

    def show_pixler_status(self) -> None:
        QMessageBox.information(
            self,
            "Pixler",
            "Движок профилей Pixler создан. Конкретные формулы не зашиты без "
            "подтверждённой методики и источника.",
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
        root.setData(0, Qt.ItemDataRole.UserRole, ("project", self.session.project.project_id))
        self.tree.addTopLevelItem(root)
        for well in self.session.project.wells.values():
            well_item = QTreeWidgetItem([well.name])
            well_item.setData(0, Qt.ItemDataRole.UserRole, ("well", well.well_id))
            root.addChild(well_item)
            for dataset in well.datasets.values():
                dataset_item = QTreeWidgetItem([f"{dataset.name} ({dataset.kind.value})"])
                dataset_item.setData(0, Qt.ItemDataRole.UserRole, ("dataset", well.well_id, dataset.dataset_id))
                well_item.addChild(dataset_item)
                for curve in dataset.curves.values():
                    curve_item = QTreeWidgetItem([curve.metadata.original_mnemonic])
                    curve_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        ("curve", well.well_id, dataset.dataset_id, curve.metadata.curve_id),
                    )
                    dataset_item.addChild(curve_item)
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
                self.curve_view.show_dataset(dataset)
                self.tablet_view.set_dataset(dataset)
                self.build_default_tablet()
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

    def _show_track_in_inspector(self, track_id: str) -> None:
        track = next(
            (item for item in self.tablet_view.layout_model.tracks if item.track_id == track_id),
            None,
        )
        if track is None:
            return
        self.inspector.setPlainText(
            f"Трек: {track.title}\n"
            f"Тип: {track.kind.value}\n"
            f"Ширина: {track.width}px\n"
            f"Кривые: {', '.join(track.curve_mnemonics) or 'нет'}\n"
            f"Заблокирован: {'да' if track.locked else 'нет'}"
        )

    def _show_visible_depth(self, top: float, bottom: float) -> None:
        self.statusBar().showMessage(f"Видимый интервал: {top:.2f}–{bottom:.2f} м")

    def _update_title(self) -> None:
        marker = " *" if self.session.dirty else ""
        self.setWindowTitle(f"GEOLOG GASRATIO@Pixler 0.4 — {self.session.project.name}{marker}")

    def _log(self, text: str) -> None:
        self.issues.append(text)

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "GEOLOG GASRATIO@Pixler",
            "Версия 0.4.0\n\n"
            "Автор: Сармулдин Ринат\n"
            "E-mail: ura07srr@gmail.com\n\n"
            "Реализовано: загрузка нескольких LAS, просмотр кривых, базовые Gas Ratio, "
            "атомарное сохранение и фундамент многотрекового планшета с общей шкалой глубины.",
        )
