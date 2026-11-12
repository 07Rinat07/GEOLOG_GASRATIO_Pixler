"""Explicit preview of selected GIS observations and geology in a gas interval."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_input_inventory import GIS_SAMPLE_FAMILIES
from geoworkbench.services.gis_interval_sample_review import MAX_GIS_INTERVAL_CURVES
from geoworkbench.services.interpretation_gis_interval_evidence import review_gas_geology_gis_interval
from geoworkbench.services.interpretation_gis_interval_evidence_html import (
    geology_gis_interval_evidence_html,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.window_geometry import fit_window_to_screen


_TEXT = {
    AppLanguage.RU: (
        "Газ, геология и ГИС (MD)",
        "Выберите до восьми кривых. Просмотр не подтверждает данные для отчёта.",
        "Показать наблюдения", "Выберите от одной до восьми кривых.",
        "Источник или интервал изменился. Откройте просмотр заново.",
        "Не удалось проверить исходные данные.",
    ),
    AppLanguage.KK: (
        "Газ, геология және ГИС (MD)",
        "Сегізге дейін қисық таңдаңыз. Қарау есеп үшін деректерді растамайды.",
        "Бақылауларды көрсету", "Бірден сегізге дейін қисық таңдаңыз.",
        "Дереккөз немесе аралық өзгерді. Қарауды қайта ашыңыз.",
        "Бастапқы деректерді тексеру мүмкін болмады.",
    ),
    AppLanguage.EN: (
        "Gas, geology and GIS (MD)",
        "Select up to eight curves. Preview does not approve data for a report.",
        "Show observations", "Select one to eight curves.",
        "The source or interval changed. Reopen the preview.",
        "Could not review the source data.",
    ),
}


class GisGeologyEvidenceDialog(QDialog):
    """Read-only preview with explicit curve selection and fresh candidate guard."""

    def __init__(
        self, session: ProjectSession, dataset: Dataset, bounds: tuple[float, float],
        validate_bounds: Callable[[], tuple[float, float] | None],
        parent: QWidget | None = None, *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.dataset = dataset
        self.bounds = bounds
        self.validate_bounds = validate_bounds
        self.language = language
        self.words = _TEXT[language]
        self.setObjectName("gis-geology-evidence-dialog")
        self.setWindowTitle(self.words[0])
        layout = QVBoxLayout(self)
        notice = QLabel(f"{bounds[0]:.17g}–{bounds[1]:.17g} m MD · {self.words[1]}", self)
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.curves = QListWidget(self)
        self.curves.setObjectName("gis-geology-evidence-curves")
        self.curves.setMaximumHeight(160)
        for key, curve in dataset.curves.items():
            semantic = curve.metadata.semantic
            if semantic is None or semantic.family not in GIS_SAMPLE_FAMILIES:
                continue
            item = QListWidgetItem(f"{key} ({curve.metadata.original_mnemonic})")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.curves.addItem(item)
        layout.addWidget(self.curves)
        self.review = QPushButton(self.words[2], self)
        self.review.setObjectName("gis-geology-evidence-review")
        self.review.clicked.connect(self._review)
        layout.addWidget(self.review)
        self.status = QLabel(self)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.viewer = QTextBrowser(self)
        self.viewer.setObjectName("gis-geology-evidence-content")
        self.viewer.setOpenLinks(False)
        layout.addWidget(self.viewer, 1)
        self.curves.itemChanged.connect(self._clear)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            Localizer.create(language).text("common.close")
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(1100, 720), minimum=QSize(520, 360))

    def _clear(self, _item: QListWidgetItem | None = None) -> None:
        self.viewer.clear()
        self.status.clear()

    def _review(self) -> None:
        self._clear()
        keys = tuple(
            self.curves.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.curves.count())
            if self.curves.item(row).checkState() == Qt.CheckState.Checked
        )
        if not 1 <= len(keys) <= MAX_GIS_INTERVAL_CURVES:
            self.status.setText(self.words[3])
            return
        if self.session.current_dataset is not self.dataset or self.validate_bounds() != self.bounds:
            self.status.setText(self.words[4])
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            evidence = review_gas_geology_gis_interval(
                self.session, top_depth=self.bounds[0], bottom_depth=self.bounds[1],
                curve_keys=keys,
            )
            html = geology_gis_interval_evidence_html(evidence, self.language)
        except (ValueError, RuntimeError, TypeError, OverflowError):
            self.status.setText(self.words[5])
            return
        finally:
            QApplication.restoreOverrideCursor()
        if self.session.current_dataset is not self.dataset or self.validate_bounds() != self.bounds:
            self.status.setText(self.words[4])
            return
        self.viewer.setHtml(html)
