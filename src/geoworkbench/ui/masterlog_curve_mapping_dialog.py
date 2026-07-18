from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: ("Сопоставление параметров LAS", "Параметры формы", "Сохранить", "Отмена"),
    AppLanguage.EN: ("LAS curve mapping", "Template parameters", "Save", "Cancel"),
    AppLanguage.KK: ("LAS параметрлерін сәйкестендіру", "Үлгі параметрлері", "Сақтау", "Болдырмау"),
}


class MasterlogCurveMappingDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogTemplateController,
        template_id: str,
        dataset: Dataset,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller, self.template_id, self.dataset = controller, template_id, dataset
        title, parameters, save_text, cancel_text = _TEXT[language]
        self.setWindowTitle(title)
        self.selectors: dict[str, QComboBox] = {}
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"{dataset.name} · {parameters}"))
        form = QFormLayout()
        saved = controller.curve_bindings(template_id, dataset)
        curves = sorted(
            dataset.curves.values(), key=lambda item: item.metadata.original_mnemonic.casefold()
        )
        for mnemonic in controller.required_curve_mnemonics(template_id):
            selector = QComboBox()
            selector.setObjectName(f"masterlog-curve-binding-{mnemonic}")
            selector.addItem("—", None)
            for curve in curves:
                metadata = curve.metadata
                label = metadata.original_mnemonic + (
                    f" [{metadata.unit}]" if metadata.unit else ""
                )
                if metadata.description:
                    label += f" · {metadata.description}"
                selector.addItem(label, metadata.curve_id)
            selected = saved.get(mnemonic)
            if selected is None:
                direct = dataset.curve_by_mnemonic(mnemonic)
                selected = direct.metadata.curve_id if direct is not None else None
            if selected is not None:
                selector.setCurrentIndex(selector.findData(selected))
            self.selectors[mnemonic] = selector
            form.addRow(mnemonic, selector)
        root.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(save_text)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(cancel_text)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _save(self) -> None:
        bindings = {
            name: str(selector.currentData())
            for name, selector in self.selectors.items()
            if selector.currentData() is not None
        }
        try:
            self.controller.save_curve_bindings(self.template_id, self.dataset, bindings)
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.accept()
