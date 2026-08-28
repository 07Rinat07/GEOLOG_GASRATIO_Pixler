from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.catalogs.description_templates import load_rock_description_templates
from geoworkbench.project.description_template_controller import DescriptionTemplateController
from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES, Localizer


_TEMPLATE_SOURCE_ROLE = 256


class DescriptionTemplatesDialog(QDialog):
    def __init__(
        self,
        controller: DescriptionTemplateController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.language = language
        self.controller = controller
        self._factory_catalog = load_rock_description_templates()
        self.setWindowTitle(self._t("templates.window_title"))
        self.resize(900, 620)
        root = QVBoxLayout(self)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel(self._t("templates.language")))
        self.template_language_input = QComboBox()
        self.template_language_input.setObjectName("templates-language-selector")
        for template_language in AppLanguage:
            self.template_language_input.addItem(
                LANGUAGE_NAMES[template_language], template_language.value
            )
        self.template_language_input.setCurrentIndex(
            self.template_language_input.findData(language.value)
        )
        self.template_language_input.currentIndexChanged.connect(self._refresh)
        language_row.addWidget(self.template_language_input)
        language_row.addStretch(1)
        root.addLayout(language_row)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName("description-templates-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("templates.name"),
                self._t("templates.text"),
                self._t("templates.source"),
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setWordWrap(False)
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)

        self.catalog_formula = QLabel()
        self.catalog_formula.setWordWrap(True)
        self.catalog_formula.setStyleSheet("color:#475569; font-size:11px;")
        root.addWidget(self.catalog_formula)
        self.catalog_warning = QLabel()
        self.catalog_warning.setWordWrap(True)
        self.catalog_warning.setStyleSheet(
            "background:#fff7ed; color:#9a3412; border:1px solid #fdba74; "
            "border-radius:4px; padding:4px 6px;"
        )
        root.addWidget(self.catalog_warning)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.text_input = QTextEdit()
        form.addRow(self._t("templates.name"), self.name_input)
        form.addRow(self._t("templates.text"), self.text_input)
        root.addLayout(form)
        actions = QHBoxLayout()
        self.add_button = QPushButton(self._t("common.add"))
        self.add_button.setObjectName("template-add-button")
        self.add_button.clicked.connect(self._add)
        actions.addWidget(self.add_button)
        self.update_button = QPushButton(self._t("common.update"))
        self.update_button.setObjectName("template-update-button")
        self.update_button.clicked.connect(self._update)
        actions.addWidget(self.update_button)
        self.remove_button = QPushButton(self._t("common.remove"))
        self.remove_button.setObjectName("template-remove-button")
        self.remove_button.clicked.connect(self._remove)
        actions.addWidget(self.remove_button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _refresh(self) -> None:
        language = self._template_language()
        factory_templates = [
            template.localized(language.value) for template in self._factory_catalog.templates
        ]
        project_templates = list(self.controller.available())
        rows = [
            (name, text, "system") for name, text in factory_templates
        ] + [
            (name, text, "project") for name, text in project_templates
        ]
        self.table.setRowCount(len(rows))
        for row, (name, text, source) in enumerate(rows):
            name_item = QTableWidgetItem(name)
            name_item.setData(_TEMPLATE_SOURCE_ROLE, source)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(text))
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(self._t(f"templates.source.{source}")),
            )
        formula, warning = self._factory_catalog.localized_guidance(language.value)
        self.catalog_formula.setText(self._t("templates.formula", formula=formula))
        self.catalog_warning.setText(self._t("templates.warning", warning=warning))
        self._update_action_state()

    def _selected_name(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.text() if item is not None else None

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        name = self.table.item(row, 0) if row >= 0 else None
        text = self.table.item(row, 1) if row >= 0 else None
        if name is not None and text is not None:
            self.name_input.setText(name.text())
            self.text_input.setPlainText(text.text())
        self._update_action_state()

    def _add(self) -> None:
        self._run(
            lambda: self.controller.add(self.name_input.text(), self.text_input.toPlainText())
        )

    def _update(self) -> None:
        original_name = self._selected_name()
        if original_name is None:
            QMessageBox.information(
                self, self._t("templates.title"), self._t("templates.select_first")
            )
            return
        if self._selected_is_system():
            QMessageBox.information(
                self, self._t("templates.title"), self._t("templates.system_read_only")
            )
            return
        self._run(
            lambda: self.controller.update(
                original_name, self.name_input.text(), self.text_input.toPlainText()
            )
        )

    def _remove(self) -> None:
        name = self._selected_name()
        if name is None:
            QMessageBox.information(
                self, self._t("templates.title"), self._t("templates.select_first")
            )
            return
        if self._selected_is_system():
            QMessageBox.information(
                self, self._t("templates.title"), self._t("templates.system_read_only")
            )
            return
        self._run(lambda: self.controller.remove(name))

    def _run(self, operation: Callable[[], object]) -> None:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("templates.title"), str(exc))
            return
        self._refresh()

    def _selected_is_system(self) -> bool:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item is not None and item.data(_TEMPLATE_SOURCE_ROLE) == "system"

    def _update_action_state(self) -> None:
        selected = self._selected_name() is not None
        editable = selected and not self._selected_is_system()
        self.update_button.setEnabled(editable)
        self.remove_button.setEnabled(editable)

    def _template_language(self) -> AppLanguage:
        try:
            return AppLanguage(str(self.template_language_input.currentData()))
        except ValueError:
            return self.language
