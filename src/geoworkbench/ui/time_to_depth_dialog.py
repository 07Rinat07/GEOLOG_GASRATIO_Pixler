from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Dataset, IndexRole
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.time_to_depth_conversion import (
    DepthAggregationMethod,
    TimeToDepthPlan,
)


class TimeToDepthDialog(QDialog):
    def __init__(
        self,
        dataset: Dataset,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.localizer = Localizer.create(language)
        self.plan: TimeToDepthPlan | None = None
        self.setWindowTitle(self._t("time_to_depth.title"))
        self.resize(560, 360)
        root = QVBoxLayout(self)
        info = QLabel(self._t("time_to_depth.description"))
        info.setWordWrap(True)
        root.addWidget(info)
        form = QFormLayout()
        self.depth_index = QComboBox()
        self.time_index = QComboBox()
        self.time_index.addItem(self._t("paradox.not_selected"), None)
        depth_values = None
        for index in dataset.indexes.values():
            label = f"{index.mnemonic} [{index.unit or '—'}]"
            if index.role is IndexRole.DEPTH:
                self.depth_index.addItem(label, index.index_id)
                if depth_values is None:
                    depth_values = np.asarray(index.values, dtype=np.float64)
            elif index.role is IndexRole.TIME:
                self.time_index.addItem(label, index.index_id)
        self.start = _spin()
        self.stop = _spin()
        self.step = _spin(decimals=6, minimum=1e-9)
        if depth_values is not None:
            finite = depth_values[np.isfinite(depth_values)]
            if finite.size:
                self.start.setValue(float(np.min(finite)))
                self.stop.setValue(float(np.max(finite)))
                positive = np.diff(np.sort(np.unique(finite)))
                positive = positive[positive > 0]
                self.step.setValue(float(np.median(positive)) if positive.size else 0.1)
        self.method = QComboBox()
        labels = {
            DepthAggregationMethod.FIRST: "time_to_depth.first",
            DepthAggregationMethod.LAST: "time_to_depth.last",
            DepthAggregationMethod.MEAN: "time_to_depth.mean",
            DepthAggregationMethod.MEDIAN: "time_to_depth.median",
            DepthAggregationMethod.MIN: "time_to_depth.min",
            DepthAggregationMethod.MAX: "time_to_depth.max",
            DepthAggregationMethod.NEAREST: "time_to_depth.nearest",
            DepthAggregationMethod.LINEAR: "time_to_depth.linear",
        }
        for method, key in labels.items():
            self.method.addItem(self._t(key), method)
        self.method.setCurrentIndex(self.method.findData(DepthAggregationMethod.MEAN))
        form.addRow(self._t("time_to_depth.depth_index"), self.depth_index)
        form.addRow(self._t("time_to_depth.time_index"), self.time_index)
        form.addRow(self._t("time_to_depth.start"), self.start)
        form.addRow(self._t("time_to_depth.stop"), self.stop)
        form.addRow(self._t("time_to_depth.step"), self.step)
        form.addRow(self._t("time_to_depth.method"), self.method)
        root.addLayout(form)
        warning = QLabel(self._t("time_to_depth.interpolation_warning"))
        warning.setWordWrap(True)
        root.addWidget(warning)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("time_to_depth.convert"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("common.cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _accept(self) -> None:
        if self.depth_index.currentData() is None:
            QMessageBox.warning(self, self.windowTitle(), self._t("time_to_depth.no_depth"))
            return
        try:
            self.plan = TimeToDepthPlan(
                self.dataset.dataset_id,
                str(self.depth_index.currentData()),
                str(self.time_index.currentData()) if self.time_index.currentData() else None,
                self.start.value(),
                self.stop.value(),
                self.step.value(),
                self.method.currentData(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.accept()


def _spin(*, decimals: int = 3, minimum: float = -1_000_000.0) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setDecimals(decimals)
    widget.setRange(minimum, 10_000_000.0)
    widget.setSingleStep(0.1)
    return widget
