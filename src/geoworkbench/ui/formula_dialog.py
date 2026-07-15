from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QDoubleSpinBox,
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
from geoworkbench.services.localization import AppLanguage, Localizer


class FormulaExecutionDialog(QDialog):
    """Passport viewer and explicit curve-mapping dialog."""

    def __init__(
        self,
        dataset: Dataset,
        registry: FormulaProfileRegistry,
        controller: FormulaExecutionController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.dataset = dataset
        self.registry = registry
        self.controller = controller
        self.execution_result: FormulaExecutionResult | None = None
        self.input_selectors: dict[str, QComboBox] = {}
        self.parameter_editors: dict[str, QDoubleSpinBox] = {}
        self.setWindowTitle(self._t("formula.profiles_title"))
        self.resize(680, 480)

        root = QVBoxLayout(self)
        self.profile_selector = QComboBox()
        self.profile_selector.setObjectName("formula-profile-selector")
        for profile in registry.available():
            display_name = self.localizer.catalog.get(
                f"formula.profile.{profile.profile_id}.name", profile.display_name
            )
            self.profile_selector.addItem(display_name, profile.profile_id)
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
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t("formula.calculate")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t("common.cancel")
        )
        self.buttons.accepted.connect(self._execute)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.profile_selector.currentIndexChanged.connect(self._refresh_profile)
        self._refresh_profile()

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    def selected_profile_id(self) -> str:
        return str(self.profile_selector.currentData())

    def selected_mapping(self) -> dict[str, str]:
        return {name: selector.currentText() for name, selector in self.input_selectors.items()}

    def selected_parameters(self) -> dict[str, float]:
        return {name: editor.value() for name, editor in self.parameter_editors.items()}

    def _refresh_profile(self) -> None:
        while self.mapping_form.rowCount():
            self.mapping_form.removeRow(0)
        self.input_selectors.clear()
        self.parameter_editors.clear()
        if self.profile_selector.currentIndex() < 0:
            self.passport_label.setText(self._t("formula.no_profiles"))
            return
        passport = self.registry.passport(self.selected_profile_id())
        profile_key = self.selected_profile_id()
        display_name = self.localizer.catalog.get(
            f"formula.profile.{profile_key}.name", passport.display_name
        )
        description = self.localizer.catalog.get(
            f"formula.profile.{profile_key}.description", passport.description
        )
        self.passport_label.setText(
            f"<b>{display_name}</b> · v{passport.version}<br>"
            f"{passport.expression}<br><br>"
            f"{self._t('formula.output')}: {passport.output_mnemonic} "
            f"[{passport.output_unit}]<br>"
            f"{self._t('formula.source')}: {passport.source}<br><br>{description}"
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
        for name, specification in passport.parameters.items():
            editor = QDoubleSpinBox()
            editor.setObjectName(f"formula-parameter-{name}")
            editor.setRange(specification.minimum, 1_000_000_000.0)
            editor.setDecimals(6)
            editor.setValue(0.0)
            self.mapping_form.addRow(f"{name} [{specification.unit}]", editor)
            self.parameter_editors[name] = editor

    def _execute(self) -> None:
        try:
            self.execution_result = self.controller.execute(
                self.selected_profile_id(),
                self.selected_mapping(),
                parameters=self.selected_parameters(),
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("formula.calculation"), str(exc))
            return
        self.accept()
