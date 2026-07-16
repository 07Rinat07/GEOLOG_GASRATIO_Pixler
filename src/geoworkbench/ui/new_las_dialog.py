from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.data.las_export_plan import LasExportVersion
from geoworkbench.domain.models import IndexType
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.new_las import NewLasPlan


class NewLasDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.plan: NewLasPlan | None = None
        self.setWindowTitle(self._t("new_las.title"))
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit(self._t("new_las.default_name"))
        self.version_combo = QComboBox()
        self.version_combo.addItem("LAS 2.0", LasExportVersion.V2_0.value)
        self.version_combo.addItem("LAS 1.2", LasExportVersion.V1_2.value)
        self.index_combo = QComboBox()
        for index_type in (IndexType.MD, IndexType.TVD, IndexType.TVDSS):
            self.index_combo.addItem(index_type.value.upper(), index_type.value)
        self.start_input = self._number_input(0.0)
        self.stop_input = self._number_input(1000.0)
        self.step_input = self._number_input(0.1, minimum=0.000001)
        self.null_input = self._number_input(-9999.25, minimum=-1e100, maximum=1e100)
        form.addRow(self._t("new_las.name"), self.name_input)
        form.addRow(self._t("new_las.version"), self.version_combo)
        form.addRow(self._t("new_las.index"), self.index_combo)
        form.addRow(self._t("new_las.start"), self.start_input)
        form.addRow(self._t("new_las.stop"), self.stop_input)
        form.addRow(self._t("new_las.step"), self.step_input)
        form.addRow("NULL", self.null_input)
        root.addLayout(form)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setObjectName("new-las-preview")
        root.addWidget(self.preview)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t("new_las.create")
        )
        self.buttons.accepted.connect(self._accept_validated)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.name_input.textChanged.connect(self._update_preview)
        self.version_combo.currentIndexChanged.connect(self._update_preview)
        self.index_combo.currentIndexChanged.connect(self._update_preview)
        for field in (self.start_input, self.stop_input, self.step_input, self.null_input):
            field.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @staticmethod
    def _number_input(
        value: float,
        *,
        minimum: float = -1_000_000.0,
        maximum: float = 1_000_000.0,
    ) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setDecimals(6)
        field.setRange(minimum, maximum)
        field.setValue(value)
        return field

    def _build_plan(self) -> NewLasPlan:
        version = self.version_combo.currentData()
        index_type = self.index_combo.currentData()
        if not isinstance(version, str) or not isinstance(index_type, str):
            raise ValueError(self._t("new_las.invalid_selection"))
        return NewLasPlan(
            name=self.name_input.text(),
            version=LasExportVersion(version),
            index_type=IndexType(index_type),
            start=self.start_input.value(),
            stop=self.stop_input.value(),
            step=self.step_input.value(),
            null_value=self.null_input.value(),
        )

    def _update_preview(self) -> None:
        try:
            plan = self._build_plan()
        except ValueError as exc:
            self.plan = None
            self.preview.setText(self._t("new_las.invalid", error=str(exc)))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self.plan = plan
        self.preview.setText(
            self._t(
                "new_las.preview",
                samples=plan.sample_count,
                start=plan.start,
                stop=plan.stop,
                step=plan.step,
            )
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _accept_validated(self) -> None:
        self._update_preview()
        if self.plan is not None:
            self.accept()
