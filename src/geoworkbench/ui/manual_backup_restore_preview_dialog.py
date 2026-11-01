"""Operator-confirmed restore from a previously inspected manual backup ZIP."""

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
    """Inspect a ZIP, then restore only after separate operator confirmation."""

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
        self._pending: Future[BackupRestorePlan | Path] | None = None
        self._request: tuple[str, str, str] | None = None
        self._verified_request: tuple[str, str, str] | None = None
        self._operation: str | None = None
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
        self.restore_button = QPushButton(self._t("restore"))
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self._restore)
        self.close_button = QPushButton(self._t("close"))
        self.close_button.clicked.connect(self.reject)
        button_row.addWidget(self.inspect_button)
        button_row.addWidget(self.restore_button)
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
        self._verified_request = None
        self.restore_button.setEnabled(False)
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
        self.restore_button.setEnabled(not busy and self.verified_plan is not None)
        restore_key = "restoring" if busy and self._operation == "restore" else "restore"
        self.restore_button.setText(self._t(restore_key))

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
            self._operation = "inspect"
            self._set_busy(True)
            self._timer.start()
        except (OSError, BackupError, RuntimeError, ValueError) as exc:
            self._cleanup()
            QMessageBox.warning(
                self, self._t("title"), self._t("failed", error=str(exc))
            )

    @staticmethod
    def _restore_verified(plan: BackupRestorePlan) -> Path:
        """Reject a stale preview before the service's own exclusive restore."""
        service = ManualBackupService()
        fresh = service.plan_restore(plan.archive, plan.destination)
        if fresh != plan:
            raise BackupError("Backup contents or destination changed after preview")
        # restore() independently re-inspects and exclusively claims a new folder.
        return service.restore(plan.archive, plan.destination)

    def _restore(self) -> None:
        if self._pending is not None or self.verified_plan is None:
            return
        plan = self.verified_plan
        if self._selection() != self._verified_request:
            self._invalidate()
            return
        answer = QMessageBox.question(
            self,
            self._t("title"),
            self._t(
                "confirm", target=str(plan.destination),
                count=len(plan.items), size=plan.total_bytes,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        # The confirmation dialog must not authorize a different selection.
        if self._selection() != self._verified_request:
            self._invalidate()
            return
        try:
            self._request = self._selection()
            self.verified_plan = None
            self._verified_request = None
            self._worker = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="backup-restore-write"
            )
            self._pending = self._worker.submit(self._restore_verified, plan)
            self._operation = "restore"
            self._set_busy(True)
            self._timer.start()
        except (OSError, BackupError, RuntimeError, ValueError) as exc:
            self._cleanup()
            self._invalidate()
            QMessageBox.warning(
                self, self._t("title"), self._t("restore_failed", error=str(exc))
            )

    def _poll(self) -> None:
        if self._pending is None or not self._pending.done():
            return
        self._timer.stop()
        operation = self._operation
        try:
            result = self._pending.result()
            if self._selection() != self._request:
                raise BackupError(self._t("changed"))
        except Exception as exc:
            self._invalidate()
            key = "restore_failed" if operation == "restore" else "failed"
            QMessageBox.warning(
                self, self._t("title"), self._t(key, error=str(exc))
            )
        else:
            if operation == "inspect":
                if not isinstance(result, BackupRestorePlan):
                    raise RuntimeError("Unexpected restore preview result")
                self.verified_plan = result
                self._verified_request = self._request
                lines = [
                    self._t(
                        "summary",
                        target=str(result.destination),
                        count=len(result.items),
                        size=result.total_bytes,
                    )
                ]
                lines.extend(
                    self._t("entry", name=item.relative_path, size=item.size)
                    for item in result.items
                )
                self.preview_text.setPlainText("\n".join(lines))
            elif operation == "restore":
                if not isinstance(result, Path):
                    raise RuntimeError("Unexpected restore result")
                self._invalidate()
                self.preview_text.setPlainText(
                    self._t("restored", target=str(result))
                )
                QMessageBox.information(
                    self, self._t("title"),
                    self._t("restored", target=str(result)),
                )
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
        self._operation = None

    def reject(self) -> None:
        if self._pending is None:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._pending is not None:
            event.ignore()
        else:
            super().closeEvent(event)
