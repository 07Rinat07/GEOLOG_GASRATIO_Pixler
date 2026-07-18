from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.services.depth_axis import DepthResamplePlan
from geoworkbench.services.localization import AppLanguage, Localizer


class DepthResampleDialog(QDialog):
    def __init__(
        self,
        controller: DepthAxisController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.plan: DepthResamplePlan | None = None
        report = controller.analyze_current()
        if report.start is None or report.stop is None:
            raise ValueError(self._t("resample.no_range"))

        self.setWindowTitle(self._t("resample.title"))
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.start_input = self._depth_input(report.start)
        self.stop_input = self._depth_input(report.stop)
        default_step = report.nominal_step if report.nominal_step is not None else 0.1
        self.step_input = self._depth_input(default_step, minimum=0.000001)
        form.addRow(self._t("resample.start"), self.start_input)
        form.addRow(self._t("resample.stop"), self.stop_input)
        form.addRow(self._t("resample.step"), self.step_input)
        root.addLayout(form)

        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setObjectName("resample-preview")
        root.addWidget(self.preview)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t("resample.create")
        )
        self.buttons.accepted.connect(self._accept_validated)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        for field in (self.start_input, self.stop_input, self.step_input):
            field.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @staticmethod
    def _depth_input(value: float, *, minimum: float = -1_000_000.0) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setDecimals(6)
        field.setRange(minimum, 1_000_000.0)
        field.setValue(value)
        return field

    def _update_preview(self) -> None:
        try:
            plan = self.controller.analyze_resample(
                self.start_input.value(), self.stop_input.value(), self.step_input.value()
            )
        except (RuntimeError, ValueError) as exc:
            self.plan = None
            self.preview.setText(self._t("resample.invalid", error=str(exc)))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self.plan = plan
        self.preview.setText(
            self._t(
                "resample.preview",
                source=plan.source_sample_count,
                target=plan.target_sample_count,
                curves=plan.curve_count,
                indexes=plan.index_count,
            )
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _accept_validated(self) -> None:
        self._update_preview()
        if self.plan is not None:
            self.accept()
