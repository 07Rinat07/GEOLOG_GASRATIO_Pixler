"""Operator-selected read-only verification of a manual backup restore plan."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.storage.manual_backup import (
    BackupError,
    BackupRestorePlan,
    ManualBackupService,
)
from geoworkbench.ui.window_geometry import fit_window_to_screen


class ManualBackupRestorePreviewDialog(QDialog):
    """Review verified archive contents without creating any output files."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("title"))
        self._worker: ThreadPoolExecutor | None = None
        self._pending: Future[BackupRestorePlan] | None = None
        self._request: tuple[str, str, str] | None = None
        self.verified_plan: BackupRestorePlan | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)

        layout = QVBoxLayout(self)
        note = QLabel(self._t("note"))
        note.setWordWrap(True)
        layout.addWidget(note)

        archive_row = QHBoxLayout()
        self.archive = QLineEdit()
        self.archive.setReadOnly(True)
        self.archive.setPlaceholderText(self._t("archive"))
        self.archive_button = QPushButton(self._t("archive"))
        self.archive_button.clicked.connect(self._choose_archive)
        archive_row.addWidget(self.archive)
        archive_row.addWidget(self.archive_button)
        layout.addLayout(archive_row)

        parent_row = QHBoxLayout()
        self.parent_folder = QLineEdit()
        self.parent_folder.setReadOnly(True)
        self.parent_folder.setPlaceholderText(self._t("parent"))
        self.parent_button = QPushButton(self._t("parent"))
        self.parent_button.clicked.connect(self._choose_parent)
        parent_row.addWidget(self.parent_folder)
        parent_row.addWidget(self.parent_button)
        layout.addLayout(parent_row)

        layout.addWidget(QLabel(self._t("folder_name")))
        self.folder_name = QLineEdit()
        self.folder_name.setText("GeoLog-restored")
        layout.addWidget(self.folder_name)

        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlainText(self._t("empty"))
        layout.addWidget(self.preview_text)

        button_row = QHBoxLayout()
        self.inspect_button = QPushButton(self._t("inspect"))
        self.inspect_button.clicked.connect(self._inspect)
        self.close_button = QPushButton(self._t("close"))
        self.close_button.clicked.connect(self.reject)
        button_row.addWidget(self.inspect_button)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.archive.textChanged.connect(self._invalidate)
        self.parent_folder.textChanged.connect(self._invalidate)
        self.folder_name.textChanged.connect(self._invalidate)
        fit_window_to_screen(
            self, preferred=QSize(700, 480), minimum=QSize(400, 320)
        )

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"backup.restore_review.{key}", **values)

    def _choose_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("archive"), "", "ZIP (*.zip)"
        )
        if path:
            self.archive.setText(path)

    def _choose_parent(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, self._t("parent"), self.parent_folder.text()
        )
        if path:
            self.parent_folder.setText(path)

    def _selection(self) -> tuple[str, str, str]:
        return (
            self.archive.text(),
            self.parent_folder.text(),
            self.folder_name.text(),
        )

    def _invalidate(self) -> None:
        self.verified_plan = None
        self.preview_text.setPlainText(self._t("empty"))

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.archive_button,
            self.parent_button,
            self.folder_name,
            self.inspect_button,
            self.close_button,
        ):
            widget.setEnabled(not busy)
        self.inspect_button.setText(self._t("checking" if busy else "inspect"))

    def _inspect(self) -> None:
        if self._pending is not None:
            return
        try:
            archive, parent, name = self._selection()
            if (
                not archive
                or Path(archive).suffix.casefold() != ".zip"
                or not parent
                or not Path(parent).is_dir()
                or not name
                or Path(name).name != name
                or name in {".", ".."}
                or "/" in name
                or "\\" in name
            ):
                raise BackupError(self._t("choose_valid"))
            destination = Path(parent) / name
            self._invalidate()
            self._request = self._selection()
            self._worker = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="backup-restore-preview"
            )
            self._pending = self._worker.submit(
                ManualBackupService().plan_restore,
                Path(archive),
                destination,
            )
            self._set_busy(True)
            self._timer.start()
        except (OSError, BackupError, RuntimeError, ValueError) as exc:
            self._cleanup()
            QMessageBox.warning(
                self, self._t("title"), self._t("failed", error=str(exc))
            )

    def _poll(self) -> None:
        if self._pending is None or not self._pending.done():
            return
        self._timer.stop()
        try:
            plan = self._pending.result()
            if self._selection() != self._request:
                raise BackupError(self._t("changed"))
        except Exception as exc:
            self._invalidate()
            QMessageBox.warning(
                self, self._t("title"), self._t("failed", error=str(exc))
            )
        else:
            self.verified_plan = plan
            lines = [
                self._t(
                    "summary",
                    target=str(plan.destination),
                    count=len(plan.items),
                    size=plan.total_bytes,
                )
            ]
            lines.extend(
                self._t("entry", name=item.relative_path, size=item.size)
                for item in plan.items
            )
            self.preview_text.setPlainText("\n".join(lines))
        finally:
            self._cleanup()
            self._set_busy(False)

    def _cleanup(self) -> None:
        self._timer.stop()
        if self._worker is not None:
            self._worker.shutdown(wait=True)
        self._pending = None
        self._worker = None
        self._request = None

    def reject(self) -> None:
        if self._pending is None:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._pending is not None:
            event.ignore()
        else:
            super().closeEvent(event)
