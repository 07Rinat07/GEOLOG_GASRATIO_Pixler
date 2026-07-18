from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.calculations.normal_compaction import NormalCompactionResult
from geoworkbench.project.nct_controller import NctCalculationController
from geoworkbench.services.localization import AppLanguage, Localizer


class NctCalculationDialog(QDialog):
    def __init__(
        self,
        controller: NctCalculationController,
        depth_minimum: float,
        depth_maximum: float,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.calculation_result: NormalCompactionResult | None = None
        self.setWindowTitle(self._t("nct.window_title"))
        root = QVBoxLayout(self)
        warning = QLabel(self._t("nct.warning"))
        warning.setWordWrap(True)
        root.addWidget(warning)
        form = QFormLayout()
        self.top_input = self._depth_input(depth_minimum, depth_maximum, depth_minimum)
        self.bottom_input = self._depth_input(depth_minimum, depth_maximum, depth_maximum)
        self.minimum_points_input = QSpinBox()
        self.minimum_points_input.setRange(2, 1_000_000)
        self.minimum_points_input.setValue(3)
        form.addRow(self._t("nct.calibration_top"), self.top_input)
        form.addRow(self._t("nct.calibration_bottom"), self.bottom_input)
        form.addRow(self._t("nct.minimum_points"), self.minimum_points_input)
        root.addLayout(form)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("nct.calculate"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t("common.cancel")
        )
        self.buttons.accepted.connect(self._calculate)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    @staticmethod
    def _depth_input(minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(3)
        field.setValue(value)
        return field

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _calculate(self) -> None:
        try:
            self.calculation_result = self.controller.calculate(
                self.top_input.value(),
                self.bottom_input.value(),
                minimum_points=self.minimum_points_input.value(),
            )
        except (RuntimeError, ValueError) as exc:
            self.summary.setText(str(exc))
            return
        self.summary.setText(
            self._t(
                "nct.result",
                points=self.calculation_result.calibration_points,
                slope=f"{self.calculation_result.slope:.8g}",
                rmse=f"{self.calculation_result.rmse:.8g}",
            )
        )
        self.accept()
