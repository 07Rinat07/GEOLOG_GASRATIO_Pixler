from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.masterlog_columns_dialog import MasterlogColumnsDialog
from geoworkbench.ui.masterlog_header_dialog import MasterlogHeaderDialog


class MasterlogTemplatesDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogTemplateController,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("masterlog_templates.title"))
        self.resize(560, 380)
        self.list = QListWidget()
        self.list.setObjectName("masterlog-template-list")
        self.create_button = QPushButton(self._t("common.create"))
        self.copy_button = QPushButton(self._t("common.copy"))
        self.rename_button = QPushButton(self._t("common.rename"))
        self.columns_button = QPushButton(self._t("masterlog_columns.action"))
        self.header_button = QPushButton(self._t("masterlog_header.action"))
        self.delete_button = QPushButton(self._t("common.delete"))
        close_button = QPushButton(self._t("common.close"))
        self.create_button.clicked.connect(self._create)
        self.copy_button.clicked.connect(self._copy)
        self.rename_button.clicked.connect(self._rename)
        self.columns_button.clicked.connect(self._edit_columns)
        self.header_button.clicked.connect(self._edit_header)
        self.delete_button.clicked.connect(self._delete)
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        for button in (
            self.create_button,
            self.copy_button,
            self.rename_button,
            self.columns_button,
            self.header_button,
            self.delete_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.refresh()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def refresh(self) -> None:
        self.list.clear()
        templates = sorted(
            self.controller.session.project.masterlog_templates.values(),
            key=lambda template: template.name.casefold(),
        )
        for template in templates:
            item = QListWidgetItem(
                self._t(
                    "masterlog_templates.item",
                    name=template.name,
                    version=template.version,
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            self.list.addItem(item)

    def _selected_id(self) -> str | None:
        item = self.list.currentItem()
        if item is None:
            QMessageBox.information(
                self, self.windowTitle(), self._t("masterlog_templates.select")
            )
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _ask_name(self, title: str, initial: str = "") -> str | None:
        name, accepted = QInputDialog.getText(
            self, title, self._t("masterlog_templates.name"), text=initial
        )
        return name if accepted else None

    def _create(self) -> None:
        name = self._ask_name(self._t("masterlog_templates.create"))
        if name is not None:
            self._run(lambda: self.controller.create(name))

    def _copy(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        source = self.controller.session.project.masterlog_templates[template_id]
        name = self._ask_name(
            self._t("masterlog_templates.copy"),
            self._t("masterlog_templates.copy_name", name=source.name),
        )
        if name is not None:
            self._run(lambda: self.controller.copy(template_id, name))

    def _rename(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        source = self.controller.session.project.masterlog_templates[template_id]
        name = self._ask_name(self._t("masterlog_templates.rename"), source.name)
        if name is not None:
            self._run(lambda: self.controller.rename(template_id, name))

    def _delete(self) -> None:
        template_id = self._selected_id()
        if template_id is not None:
            self._run(lambda: self.controller.delete(template_id))

    def _edit_columns(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        MasterlogColumnsDialog(
            self.controller,
            template_id,
            self,
            language=self.localizer.language,
        ).exec()
        self.refresh()

    def _edit_header(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        MasterlogHeaderDialog(
            self.controller,
            template_id,
            self,
            language=self.localizer.language,
        ).exec()
        self.refresh()

    def _run(self, operation: Callable[[], object]) -> None:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()
