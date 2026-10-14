"""Select a measured gas row for a report-owned VALUE callout."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLabel, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_gas_value_flags import (
    ReportGasValueSample, report_gas_channels, report_gas_value_at_depth,
)
from geoworkbench.ui.window_geometry import fit_window_to_screen


class ReportGasValueFlagDialog(QDialog):
    """Dialog validates a source row before its owner mutates the report."""

    def __init__(
        self, dataset: Dataset, parent: QWidget | None = None,
        *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.language = language
        self.setObjectName("report-gas-value-flag-dialog")
        self.setWindowTitle(self._text(
            "Флажок газового значения", "Газ мәнінің жалаушасы", "Gas value flag",
        ))
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.channel = QComboBox(self)
        self.channel.setObjectName("report-gas-value-channel")
        for mnemonic in report_gas_channels(dataset):
            self.channel.addItem(mnemonic, mnemonic)
        form.addRow(self._text("Газовый канал", "Газ арнасы", "Gas channel"), self.channel)
        self.depth_spin = QDoubleSpinBox(self)
        self.depth_spin.setObjectName("report-gas-value-depth")
        self.depth_spin.setDecimals(9)
        depth_values = np.asarray(dataset.depth, dtype=np.float64)
        finite = depth_values[np.isfinite(depth_values)]
        if finite.size:
            self.depth_spin.setRange(float(finite.min()), float(finite.max()))
            self.depth_spin.setValue(float(finite.min()))
        else:
            self.depth_spin.setRange(0.0, 0.0)
        self.depth_spin.setSuffix(f" {dataset.active_index.unit or 'м'}")
        form.addRow(self._text("Глубина MD", "MD тереңдігі", "MD depth"), self.depth_spin)
        root.addLayout(form)
        self.sample_label = QLabel(self)
        self.sample_label.setObjectName("report-gas-value-source-sample")
        self.sample_label.setWordWrap(True)
        root.addWidget(self.sample_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.channel.currentIndexChanged.connect(self._update_sample)
        self.depth_spin.valueChanged.connect(self._update_sample)
        self._update_sample()
        fit_window_to_screen(
            self, preferred=QSize(520, 300), minimum=QSize(360, 240),
        )

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[self.language]

    def selected_sample(self) -> ReportGasValueSample | None:
        mnemonic = self.channel.currentData()
        if not isinstance(mnemonic, str):
            return None
        return report_gas_value_at_depth(self.dataset, mnemonic, self.depth_spin.value())

    def _update_sample(self) -> None:
        sample = self.selected_sample()
        if sample is None:
            self.sample_label.setText(self._text(
                "Нет однозначного измерения в этой точке (пропуск, разрыв или повторная MD).",
                "Бұл нүктеде анық өлшеу жоқ (бос орын, үзіліс немесе қайталанған MD).",
                "No unambiguous measured sample at this depth (gap or repeated MD).",
            ))
        else:
            self.sample_label.setText(sample.caption)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(sample is not None)

    def accept(self) -> None:
        if self.selected_sample() is None:
            return
        super().accept()
