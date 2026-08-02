from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QProcess, QUrl, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.printing.print_job import PrintOutputFormat
from geoworkbench.services.localization import AppLanguage, Localizer


OpenPathCallback = Callable[[Path], bool]


def _start_detached(program: str, arguments: list[str]) -> bool:
    """Normalize QProcess.startDetached across supported PySide6 versions."""

    result = QProcess.startDetached(program, arguments)
    if isinstance(result, tuple):
        return bool(result[0])
    return bool(result)


class PrintJobStatusDialog(QDialog):
    """Persistent readiness state for one print or file-export operation."""

    def __init__(
        self,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        output_format: PrintOutputFormat,
        target: Path | None = None,
        open_path_callback: OpenPathCallback | None = None,
        open_folder_callback: OpenPathCallback | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.output_format = output_format
        self.target = target
        self._working = True
        self._ready = False
        self._primary_path: Path | None = None
        self._open_path_callback = open_path_callback or self._open_document_path
        self._open_folder_callback = open_folder_callback or self._reveal_path

        self.setWindowTitle(self._t("print_center.status_title"))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        self.status_label = QLabel(self._t("print_center.status_preparing"))
        self.status_label.setObjectName("print-job-status-title")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        root.addWidget(self.status_label)

        self.detail_label = QLabel(self._working_detail())
        self.detail_label.setObjectName("print-job-status-detail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(self.detail_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("print-job-status-progress")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.open_button = QPushButton(self._t("print_center.open_result"))
        self.open_button.setObjectName("print-job-open-result")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_result)
        self.folder_button = QPushButton(self._t("print_center.open_folder"))
        self.folder_button.setObjectName("print-job-open-folder")
        self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self._open_folder)
        self.close_button = QPushButton(self._t("common.close"))
        self.close_button.setObjectName("print-job-close")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.open_button)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.close_button)
        root.addLayout(actions)

    @property
    def working(self) -> bool:
        return self._working

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def primary_path(self) -> Path | None:
        return self._primary_path

    def show_rendering(self) -> None:
        self._set_working_stage("print_center.status_rendering")

    def show_sending(self) -> None:
        self._set_working_stage("print_center.status_sending")

    def mark_ready(self, *, page_count: int, paths: tuple[Path, ...] = ()) -> None:
        self._working = False
        self._ready = True
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.setFormat("100%")
        self.status_label.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #15803d;"
        )
        normalized_paths = tuple(Path(path) for path in paths)
        existing_paths = tuple(path for path in normalized_paths if path.is_file())

        if self.output_format is PrintOutputFormat.PRINTER:
            self.status_label.setText(self._t("print_center.status_ready_printer"))
            detail = self._t("print_center.status_ready_printer_detail", count=page_count)
            if existing_paths:
                self._primary_path = existing_paths[0]
                detail += f"\n\nPDF: {self._primary_path}"
                self.open_button.setEnabled(True)
                self.folder_button.setEnabled(True)
            self.detail_label.setText(detail)
        else:
            if not normalized_paths or len(existing_paths) != len(normalized_paths):
                self.mark_failed(self._t("print_center.status_missing_output"))
                return
            self._primary_path = existing_paths[0]
            self.status_label.setText(self._t("print_center.status_ready_file"))
            self.detail_label.setText(
                self._t(
                    "print_center.status_ready_file_detail",
                    name=self._primary_path.name,
                    count=page_count,
                )
            )
            self.open_button.setEnabled(True)
            self.folder_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def mark_failed(self, message: str) -> None:
        self._working = False
        self._ready = False
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_label.setText(self._t("print_center.status_failed"))
        self.status_label.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #b91c1c;"
        )
        self.detail_label.setText(
            self._t("print_center.status_failed_detail", error=message)
        )
        self.open_button.setEnabled(False)
        self.folder_button.setEnabled(
            self.target is not None and self.target.parent.is_dir()
        )
        self.close_button.setEnabled(True)

    def reject(self) -> None:
        if self._working:
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._working:
            event.ignore()
            return
        super().closeEvent(event)

    def _set_working_stage(self, key: str) -> None:
        if not self._working:
            return
        self.status_label.setText(self._t(key))
        self.detail_label.setText(self._working_detail())

    def _working_detail(self) -> str:
        if self.output_format is PrintOutputFormat.PRINTER:
            return self._t("print_center.status_working_printer_detail")
        target = str(self.target) if self.target is not None else ""
        return self._t("print_center.status_working_file_detail", path=target)

    def _open_result(self) -> None:
        if self._primary_path is not None and self._primary_path.is_file():
            self._invoke_open_action(self._open_path_callback, self._primary_path)

    def _open_folder(self) -> None:
        if self._primary_path is not None and self._primary_path.is_file():
            self._invoke_open_action(self._open_folder_callback, self._primary_path)
            return
        if self.target is not None and self.target.parent.is_dir():
            self._invoke_open_action(self._open_folder_callback, self.target.parent)

    def _invoke_open_action(self, callback: OpenPathCallback, path: Path) -> None:
        try:
            opened = bool(callback(path))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self._show_open_failure(path, exc)
            return
        if not opened:
            self._show_open_failure(path)

    def _show_open_failure(self, path: Path, error: Exception | None = None) -> None:
        message = f"{self.open_button.text()} / {self.folder_button.text()}\n{path}"
        if error is not None and str(error).strip():
            message += f"\n\n{error}"
        QMessageBox.warning(
            self,
            self._t("print_center.status_title"),
            message,
        )

    @staticmethod
    def _open_document_path(path: Path) -> bool:
        resolved = path.resolve()
        if sys.platform == "win32":
            startfile = getattr(os, "startfile", None)
            if callable(startfile):
                startfile(str(resolved))
                return True
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))

    @staticmethod
    def _reveal_path(path: Path) -> bool:
        resolved = path.resolve()
        if sys.platform == "win32":
            if resolved.is_file():
                return _start_detached("explorer.exe", ["/select,", str(resolved)])
            return _start_detached("explorer.exe", [str(resolved)])
        if sys.platform == "darwin":
            if resolved.is_file():
                return _start_detached("open", ["-R", str(resolved)])
            return _start_detached("open", [str(resolved)])
        folder = resolved.parent if resolved.is_file() else resolved
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
