from __future__ import annotations

from pathlib import Path

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

from geoworkbench.data.las_adapter import LasImportError, import_las
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_codec import ProjectFormatError
from geoworkbench.tablet import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.visualization.curve_view import CurveView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project_controller = ProjectController()
        self.tablet_controller = TabletController(self.session)
        self._selected_track_id: str | None = None
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

        self.open_project_action = QAction("Открыть проект...", self)
        self.open_project_action.setShortcut("Ctrl+O")
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)

        self.open_action = QAction("Импортировать LAS...", self)
        self.open_action.setShortcut("Ctrl+L")
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
        self._selected_track_id = None
        self._refresh_tree()
        self._show_current_dataset()
        self.session.dirty = False
        self._update_title()
        self._log(f"Проект открыт: {source}")
        self.statusBar().showMessage(f"Проект открыт: {source.name}")

    def _show_current_dataset(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            self.curve_view.clear()
            self.tablet_view.set_layout_model(TabletLayout())
            self.tablet_view.set_dataset(None)
            return
        self.curve_view.show_dataset(dataset)
        self.tablet_view.set_dataset(dataset)
        saved_layout = self.session.current_tablet_layout
        if saved_layout is None:
            self.build_default_tablet()
        else:
            self.tablet_view.set_layout_model(saved_layout)
        self.tabs.setCurrentWidget(self.tablet_view)

    def build_default_tablet(self) -> None:
        dataset = self.session.current_dataset
        if dataset is None:
            QMessageBox.information(self, "Планшет", "Сначала откройте LAS-файл")
            return

        layout = self.tablet_controller.build_default_layout()
        self.tablet_view.set_layout_model(layout)
        self.tablet_view.set_dataset(dataset)
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
        try:
            saved_path = self.project_controller.save_project(Path(filename))
        except OSError as exc:
            QMessageBox.critical(self, "Сохранение", str(exc))
            return
        self._update_title()
        self._log(f"Проект сохранён: {saved_path}")

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

    def _show_track_in_inspector(self, track_id: str) -> None:
        self._selected_track_id = track_id
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
            f"Шкала X: {track.x_scale.value}\n"
            f"Диапазон X: "
            f"{f'{track.x_min:g}–{track.x_max:g}' if track.x_min is not None else 'авто'}\n"
            f"Заблокирован: {'да' if track.locked else 'нет'}"
        )

    def _show_visible_depth(self, top: float, bottom: float) -> None:
        if self.tablet_controller.set_visible_depth(top, bottom):
            self._update_title()
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
