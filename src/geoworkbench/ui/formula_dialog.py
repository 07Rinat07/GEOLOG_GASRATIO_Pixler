from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.calculations.controller import (
    FormulaExecutionController,
    FormulaExecutionResult,
)
from geoworkbench.calculations.pixler import FormulaProfileRegistry
from geoworkbench.domain.models import Dataset


class FormulaExecutionDialog(QDialog):
    """Passport viewer and explicit curve-mapping dialog."""

    def __init__(
        self,
        dataset: Dataset,
        registry: FormulaProfileRegistry,
        controller: FormulaExecutionController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.registry = registry
        self.controller = controller
        self.execution_result: FormulaExecutionResult | None = None
        self.input_selectors: dict[str, QComboBox] = {}
        self.setWindowTitle("Профили расчётных формул")
        self.resize(680, 480)

        root = QVBoxLayout(self)
        self.profile_selector = QComboBox()
        self.profile_selector.setObjectName("formula-profile-selector")
        for profile in registry.available():
            self.profile_selector.addItem(profile.display_name, profile.profile_id)
        root.addWidget(self.profile_selector)

        self.passport_label = QLabel()
        self.passport_label.setWordWrap(True)
        self.passport_label.setTextInteractionFlags(self.passport_label.textInteractionFlags())
        root.addWidget(self.passport_label)

        self.mapping_widget = QWidget()
        self.mapping_form = QFormLayout(self.mapping_widget)
        root.addWidget(self.mapping_widget)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Рассчитать")
        self.buttons.accepted.connect(self._execute)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.profile_selector.currentIndexChanged.connect(self._refresh_profile)
        self._refresh_profile()

    def selected_profile_id(self) -> str:
        return str(self.profile_selector.currentData())

    def selected_mapping(self) -> dict[str, str]:
        return {name: selector.currentText() for name, selector in self.input_selectors.items()}

    def _refresh_profile(self) -> None:
        while self.mapping_form.rowCount():
            self.mapping_form.removeRow(0)
        self.input_selectors.clear()
        if self.profile_selector.currentIndex() < 0:
            self.passport_label.setText("Нет зарегистрированных профилей")
            return
        passport = self.registry.passport(self.selected_profile_id())
        self.passport_label.setText(
            f"<b>{passport.display_name}</b> · v{passport.version}<br>"
            f"{passport.expression}<br><br>"
            f"Выход: {passport.output_mnemonic} [{passport.output_unit}]<br>"
            f"Источник: {passport.source}<br><br>{passport.description}"
        )
        curve_names = [curve.metadata.original_mnemonic for curve in self.dataset.curves.values()]
        for input_name in passport.required_inputs:
            selector = QComboBox()
            selector.setObjectName(f"formula-input-{input_name}")
            selector.addItems(curve_names)
            preferred = self.dataset.curve_by_mnemonic(input_name)
            if preferred is not None:
                selector.setCurrentText(preferred.metadata.original_mnemonic)
            unit = passport.input_units[input_name]
            self.mapping_form.addRow(f"{input_name} [{unit}]", selector)
            self.input_selectors[input_name] = selector

    def _execute(self) -> None:
        try:
            self.execution_result = self.controller.execute(
                self.selected_profile_id(),
                self.selected_mapping(),
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Расчёт формулы", str(exc))
            return
        self.accept()
