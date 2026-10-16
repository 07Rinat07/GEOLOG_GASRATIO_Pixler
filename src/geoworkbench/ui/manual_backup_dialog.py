from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import tempfile
from uuid import uuid4

from PySide6.QtCore import QSettings, QSize, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.storage.manual_backup import BackupError, BackupPlan, ManualBackupService
from geoworkbench.ui.window_geometry import fit_window_to_screen


class ManualBackupDialog(QDialog):
    """An explicit backup request; no scheduler or background copies on startup."""

    def __init__(self, current_project: Path | None, parent: QWidget | None = None,
                 *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("title"))
        self._worker: ThreadPoolExecutor | None = None
        self._pending: Future[Path] | None = None
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)
        layout = QVBoxLayout(self)
        note = QLabel(self._t("note"))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.projects = QListWidget()
        layout.addWidget(self.projects)
        self.add_button = QPushButton(self._t("add"))
        self.add_button.clicked.connect(self._choose_projects)
        layout.addWidget(self.add_button)
        self.settings_box = QCheckBox(self._t("settings"))
        self.settings_box.setChecked(False)
        layout.addWidget(self.settings_box)
        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText(self._t("folder"))
        self.folder_button = QPushButton(self._t("folder"))
        self.folder_button.clicked.connect(self._choose_folder)
        row.addWidget(self.folder)
        row.addWidget(self.folder_button)
        layout.addLayout(row)
        self.estimate = QLabel()
        layout.addWidget(self.estimate)
        self.create_button = QPushButton(self._t("create"))
        self.create_button.clicked.connect(self._create)
        layout.addWidget(self.create_button)
        self.close_button = QPushButton(self._t("close"))
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(self.close_button)
        self.projects.itemChanged.connect(self._update_estimate)
        self.settings_box.toggled.connect(self._update_estimate)
        if current_project is not None and current_project.is_file() and current_project.suffix.lower() == ".geologpkg":
            self._add_project(current_project)
        self._update_estimate()
        fit_window_to_screen(
            self, preferred=QSize(680, 460), minimum=QSize(360, 300),
        )

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"backup.manual.{key}", **values)

    def _add_project(self, path: Path) -> None:
        path = path.resolve()
        if any(self.projects.item(index).data(Qt.ItemDataRole.UserRole) == str(path)
               for index in range(self.projects.count())):
            return
        item = QListWidgetItem(str(path))
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self.projects.addItem(item)

    def _selected_projects(self) -> tuple[Path, ...]:
        return tuple(Path(self.projects.item(index).data(Qt.ItemDataRole.UserRole))
                     for index in range(self.projects.count())
                     if self.projects.item(index).checkState() == Qt.CheckState.Checked)

    def _choose_projects(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(self, self._t("add"), "", "GeoLog Package (*.geologpkg)")
        for name in filenames:
            self._add_project(Path(name))
        self._update_estimate()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._t("folder"), self.folder.text())
        if folder:
            self.folder.setText(folder)

    def _update_estimate(self) -> None:
        try:
            size = sum(path.stat().st_size for path in self._selected_projects())
            self.estimate.setText(self._t("estimate", size=f"{size / 1024 ** 2:.1f}"))
        except OSError as exc:
            self.estimate.setText(self._t("failed", error=str(exc)))

    def _create(self) -> None:
        if self._pending is not None:
            return
        try:
            folder = Path(self.folder.text())
            if not self.folder.text() or not folder.is_dir():
                raise BackupError(self._t("choose_folder"))
            self._temporary = tempfile.TemporaryDirectory(prefix="geolog-settings-backup-")
            settings_path: Path | None = None
            if self.settings_box.isChecked():
                settings_path = Path(self._temporary.name) / "preferences.ini"
                current = QSettings()
                current.sync()
                snapshot = QSettings(str(settings_path), QSettings.Format.IniFormat)
                for key in current.allKeys():
                    snapshot.setValue(key, current.value(key))
                snapshot.sync()
                if current.status() != QSettings.Status.NoError or snapshot.status() != QSettings.Status.NoError:
                    raise BackupError(self._t("settings_failed"))
                if not settings_path.exists():
                    settings_path.touch()
            plan = BackupPlan.build(self._selected_projects(), settings_path)
            target = folder / f"GeoLog-backup-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.zip"
            self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="manual-backup")
            self._pending = self._worker.submit(ManualBackupService().create, plan, target)
            self._set_busy(True)
            self._timer.start()
        except (OSError, BackupError, RuntimeError, ValueError) as exc:
            self._cleanup()
            QMessageBox.warning(self, self._t("title"), self._t("failed", error=str(exc)))

    def _set_busy(self, busy: bool) -> None:
        for widget in (self.projects, self.add_button, self.settings_box, self.folder_button,
                       self.create_button, self.close_button):
            widget.setEnabled(not busy)
        self.create_button.setText(self._t("working" if busy else "create"))

    def _poll(self) -> None:
        if self._pending is None or not self._pending.done():
            return
        self._timer.stop()
        try:
            target = self._pending.result()
        except Exception as exc:
            self._cleanup()
            self._set_busy(False)
            QMessageBox.warning(self, self._t("title"), self._t("failed", error=str(exc)))
        else:
            self._cleanup()
            self._set_busy(False)
            QMessageBox.information(self, self._t("title"), self._t("done", path=str(target)))

    def _cleanup(self) -> None:
        if self._worker is not None:
            self._worker.shutdown(wait=True)
        self._worker = None
        self._pending = None
        if self._temporary is not None:
            self._temporary.cleanup()
        self._temporary = None

    def reject(self) -> None:
        if self._pending is None:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._pending is not None:
            event.ignore()
        else:
            super().closeEvent(event)
