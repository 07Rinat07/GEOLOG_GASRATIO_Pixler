from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.importers.skf_importer import import_skf_file
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.printing.header_catalog import HeaderCatalogItem
from geoworkbench.services.localization import AppLanguage


class HeaderCatalogDialog(QDialog):
    """Independent catalog of factory and user-editable print headers."""

    def __init__(
        self,
        controller: MasterlogTemplateController,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        selection_mode: bool = False,
        target_template_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language
        self.selection_mode = selection_mode
        self.target_template_id = target_template_id
        self.selected_catalog_id: str | None = None
        self._refreshing = False
        self.setWindowTitle(
            {
                AppLanguage.RU: "Каталог печатных шапок",
                AppLanguage.KK: "Баспа тақырыптарының каталогы",
                AppLanguage.EN: "Print header catalog",
            }[language]
        )
        self.list = QListWidget()
        self.list.setObjectName("header-catalog-list")
        self.list.currentItemChanged.connect(lambda *_: self._refresh_details())
        self.list.itemDoubleClicked.connect(lambda _item: self._use_or_edit())
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.orientation = QComboBox()
        self.orientation.addItem("Книжная и альбомная", "both")
        self.orientation.addItem("Книжная", "portrait")
        self.orientation.addItem("Альбомная", "landscape")
        self.orientation.currentIndexChanged.connect(self._orientation_changed)

        add_button = QPushButton("Добавить...")
        add_button.clicked.connect(self._add)
        import_button = QPushButton("Импорт шапки из SKF...")
        import_button.clicked.connect(self._import_skf)
        self.edit_button = QPushButton("Редактировать...")
        self.edit_button.clicked.connect(self._edit)
        self.duplicate_button = QPushButton("Дублировать...")
        self.duplicate_button.clicked.connect(self._duplicate)
        self.rename_button = QPushButton("Переименовать...")
        self.rename_button.clicked.connect(self._rename)
        self.delete_button = QPushButton("Удалить")
        self.delete_button.clicked.connect(self._delete)
        self.use_button = QPushButton("Использовать шапку")
        self.use_button.clicked.connect(self._use)
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        for button in (
            add_button,
            import_button,
            self.edit_button,
            self.duplicate_button,
            self.rename_button,
            self.delete_button,
        ):
            buttons.addWidget(button)

        right = QVBoxLayout()
        right.addWidget(self.details)
        form = QFormLayout()
        form.addRow("Рекомендуемая ориентация", self.orientation)
        right.addLayout(form)
        right.addStretch(1)
        if selection_mode:
            right.addWidget(self.use_button)
        right.addWidget(close_button)

        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        left.addLayout(buttons)

        root = QHBoxLayout(self)
        root.addLayout(left, 2)
        root.addLayout(right, 1)
        self.resize(1050, 560)
        self.refresh()

    def refresh(self, selected_id: str | None = None) -> None:
        selected_id = selected_id or self._selected_id()
        self._refreshing = True
        self.list.clear()
        for item in self.controller.header_catalog_items(self.language):
            label = item.name + ("  [заводская]" if item.read_only else "")
            row = QListWidgetItem(label)
            row.setData(Qt.ItemDataRole.UserRole, item.catalog_id)
            self.list.addItem(row)
            if item.catalog_id == selected_id:
                self.list.setCurrentItem(row)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._refresh_details()
        self._refreshing = False

    def _selected_id(self) -> str | None:
        row = self.list.currentItem()
        if row is None:
            return None
        value = row.data(Qt.ItemDataRole.UserRole)
        return str(value) if isinstance(value, str) else None

    def _selected_item(self) -> HeaderCatalogItem | None:
        selected = self._selected_id()
        if selected is None:
            return None
        return next(
            (
                item
                for item in self.controller.header_catalog_items(self.language)
                if item.catalog_id == selected
            ),
            None,
        )

    def _refresh_details(self) -> None:
        item = self._selected_item()
        if item is None:
            self.details.clear()
            return
        orientation_names = {
            "both": "книжная и альбомная",
            "portrait": "книжная",
            "landscape": "альбомная",
        }
        self.details.setText(
            f"<b>{item.name}</b><br>"
            f"Элементов: {item.element_count}<br>"
            f"Высота: {item.header_height_mm:g} мм<br>"
            f"Тип: {'заводская, только чтение' if item.read_only else 'пользовательская'}<br>"
            f"Ориентация: {orientation_names.get(item.preferred_orientation, item.preferred_orientation)}"
            + (f"<br><br>{item.description}" if item.description else "")
        )
        index = self.orientation.findData(item.preferred_orientation)
        self.orientation.blockSignals(True)
        self.orientation.setCurrentIndex(max(0, index))
        self.orientation.blockSignals(False)
        self.orientation.setEnabled(not item.read_only)
        editable = not item.read_only
        self.rename_button.setEnabled(editable)
        self.delete_button.setEnabled(editable)
        self.edit_button.setEnabled(True)
        self.duplicate_button.setEnabled(True)

    def _orientation_changed(self) -> None:
        if self._refreshing:
            return
        item = self._selected_item()
        if item is None or item.read_only:
            return
        template = self.controller.session.project.masterlog_templates.get(item.catalog_id)
        if template is None:
            return
        template.properties["preferred_orientation"] = str(
            self.orientation.currentData() or "both"
        )
        template.version += 1
        self.controller.session.dirty = True
        self._refresh_details()

    def _ask_name(self, title: str, value: str) -> str | None:
        name, accepted = QInputDialog.getText(self, title, "Название", text=value)
        return name.strip() if accepted else None

    def _add(self) -> None:
        name = self._ask_name("Новая печатная шапка", "Новая шапка")
        if name is None:
            return
        try:
            template = self.controller.create_header_template(
                name,
                preferred_orientation=str(self.orientation.currentData() or "both"),
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(template.template_id)
        self._open_editor(template.template_id)

    def _import_skf(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт печатной шапки",
            "",
            "Delphi SKF (*.skf);;All files (*)",
        )
        if not filename:
            return
        source = Path(filename)
        try:
            result = import_skf_file(source)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        name = self._ask_name("Импорт печатной шапки", result.header_template.name)
        if name is None:
            return
        try:
            template = self.controller.import_header_template(
                result.header_template, result.image_assets, name
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(template.template_id)
        warning = ""
        if result.report.warnings:
            warning = "\n\nПредупреждения:\n- " + "\n- ".join(result.report.warnings)
        QMessageBox.information(
            self,
            self.windowTitle(),
            f"Шапка импортирована: {template.name}\n"
            f"Элементов: {len(template.header_elements)}\n"
            f"Изображений: {len(result.image_assets)}{warning}",
        )

    def _edit(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        catalog_id = item.catalog_id
        if item.read_only:
            name = self._ask_name("Копировать заводскую шапку", item.name)
            if name is None:
                return
            try:
                template = self.controller.copy_header_catalog_item(catalog_id, name)
            except ValueError as exc:
                QMessageBox.warning(self, self.windowTitle(), str(exc))
                return
            catalog_id = template.template_id
            self.refresh(catalog_id)
        self._open_editor(catalog_id)

    def _open_editor(self, template_id: str) -> None:
        from geoworkbench.ui.masterlog_header_dialog import MasterlogHeaderDialog

        MasterlogHeaderDialog(
            self.controller,
            template_id,
            self,
            language=self.language,
        ).exec()
        self.refresh(template_id)

    def _duplicate(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        name = self._ask_name("Дублировать печатную шапку", f"{item.name} — копия")
        if name is None:
            return
        try:
            template = self.controller.copy_header_catalog_item(item.catalog_id, name)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(template.template_id)

    def _rename(self) -> None:
        item = self._selected_item()
        if item is None or item.read_only:
            return
        name = self._ask_name("Переименовать печатную шапку", item.name)
        if name is None:
            return
        try:
            self.controller.rename(item.catalog_id, name)
            template = self.controller.session.project.masterlog_templates[item.catalog_id]
            template.properties["preferred_orientation"] = str(
                self.orientation.currentData() or "both"
            )
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(item.catalog_id)

    def _delete(self) -> None:
        item = self._selected_item()
        if item is None or item.read_only:
            return
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            f"Удалить печатную шапку '{item.name}' из каталога?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete(item.catalog_id)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()

    def _use_or_edit(self) -> None:
        if self.selection_mode:
            self._use()
        else:
            self._edit()

    def _use(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        if self.target_template_id is not None:
            try:
                self.controller.apply_header_catalog_item(
                    self.target_template_id, item.catalog_id
                )
            except (KeyError, ValueError) as exc:
                QMessageBox.warning(self, self.windowTitle(), str(exc))
                return
        self.selected_catalog_id = item.catalog_id
        self.accept()
