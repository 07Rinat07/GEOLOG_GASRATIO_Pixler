from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.depth_axis import analyze_depth_axis
from geoworkbench.services.localization import AppLanguage, Localizer


class LasEditorOperation(StrEnum):
    CREATE = "create"
    OPEN = "open"
    TABLE = "table"
    REVERSE_DEPTH = "reverse_depth"
    RESAMPLE = "resample"
    INSERT_CURVES = "insert_curves"
    MERGE = "merge"
    EXPORT_COPY = "export_copy"


class LasEditorDialog(QDialog):
    """One entry point for safe LAS creation, repair and combination workflows."""

    def __init__(
        self,
        dataset: Dataset | None,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.dataset = dataset
        self.operation: LasEditorOperation | None = None
        self.setWindowTitle(self._t("las_editor.title"))
        self.resize(760, 520)

        root = QVBoxLayout(self)
        title = QLabel(self._t("las_editor.heading"))
        title.setStyleSheet("font-size:20px; font-weight:700;")
        root.addWidget(title)

        summary = QLabel(self._summary_text())
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary.setStyleSheet(
            "padding:10px; border:1px solid #cbd5e1; border-radius:6px; background:#f8fafc;"
        )
        root.addWidget(summary)

        group = QGroupBox(self._t("las_editor.operations"))
        grid = QGridLayout(group)
        buttons = (
            (LasEditorOperation.CREATE, "las_editor.create", "las_editor.create_hint", True),
            (LasEditorOperation.OPEN, "las_editor.open", "las_editor.open_hint", True),
            (LasEditorOperation.TABLE, "las_editor.table", "las_editor.table_hint", dataset is not None),
            (
                LasEditorOperation.REVERSE_DEPTH,
                "las_editor.reverse",
                "las_editor.reverse_hint",
                dataset is not None,
            ),
            (
                LasEditorOperation.RESAMPLE,
                "las_editor.resample",
                "las_editor.resample_hint",
                dataset is not None,
            ),
            (
                LasEditorOperation.INSERT_CURVES,
                "las_editor.insert",
                "las_editor.insert_hint",
                dataset is not None,
            ),
            (LasEditorOperation.MERGE, "las_editor.merge", "las_editor.merge_hint", dataset is not None),
            (
                LasEditorOperation.EXPORT_COPY,
                "las_editor.export",
                "las_editor.export_hint",
                dataset is not None,
            ),
        )
        for position, (operation, text_key, hint_key, enabled) in enumerate(buttons):
            button = QPushButton(self._t(text_key))
            button.setToolTip(self._t(hint_key))
            button.setMinimumHeight(72)
            button.setEnabled(enabled)
            button.clicked.connect(lambda _checked=False, value=operation: self._choose(value))
            grid.addWidget(button, position // 2, position % 2)
        root.addWidget(group, 1)

        note = QLabel(self._t("las_editor.safety_note"))
        note.setWordWrap(True)
        note.setStyleSheet("color:#475569;")
        root.addWidget(note)

        buttons_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons_box.rejected.connect(self.reject)
        root.addWidget(buttons_box)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _choose(self, operation: LasEditorOperation) -> None:
        self.operation = operation
        self.accept()

    def _summary_text(self) -> str:
        if self.dataset is None:
            return self._t("las_editor.no_dataset")
        report = analyze_depth_axis(self.dataset.depth)
        start = report.start if report.start is not None else 0.0
        stop = report.stop if report.stop is not None else 0.0
        step = report.nominal_step if report.nominal_step is not None else 0.0
        return self._t(
            "las_editor.dataset_summary",
            name=self.dataset.name,
            start=f"{start:g}",
            stop=f"{stop:g}",
            step=f"{step:g}",
            direction=self._t(f"depth.direction.{report.direction.value}"),
            samples=self.dataset.depth.size,
            curves=len(self.dataset.curves),
        )
