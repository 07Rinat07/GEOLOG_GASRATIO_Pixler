from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from geoworkbench.project.logo_catalog_controller import LogoCatalogController, LogoCatalogItem
from geoworkbench.printing.image_asset_rendering import image_asset_pixmap
from geoworkbench.services.localization import AppLanguage


class _LogoMetadataDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        title: str,
        name: str = "",
        category: str = "",
        notes: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.name_input = QLineEdit(name)
        self.category_input = QLineEdit(category)
        self.notes_input = QTextEdit(notes)
        self.notes_input.setMinimumHeight(80)
        form = QFormLayout()
        form.addRow("Название", self.name_input)
        form.addRow("Категория", self.category_input)
        form.addRow("Примечание", self.notes_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(460, 260)

    def values(self) -> tuple[str, str, str]:
        return (
            self.name_input.text().strip(),
            self.category_input.text().strip(),
            self.notes_input.toPlainText().strip(),
        )


class LogoCatalogDialog(QDialog):
    """Separate reusable logo catalog with optional selection mode."""

    def __init__(
        self,
        controller: LogoCatalogController,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        selection_mode: bool = False,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language
        self.selection_mode = selection_mode
        self.selected_asset_id: str | None = None
        self.selected_logo_id: str | None = None
        self.setWindowTitle(
            {
                AppLanguage.RU: "Каталог логотипов",
                AppLanguage.KK: "Логотиптар каталогы",
                AppLanguage.EN: "Logo catalog",
            }[language]
        )
        self.list = QListWidget()
        self.list.setObjectName("logo-catalog-list")
        self.list.itemDoubleClicked.connect(lambda _item: self._use_or_edit())
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(260, 120)
        self.preview.setStyleSheet("QLabel { background: white; border: 1px solid #cbd5e1; }")
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.list.currentItemChanged.connect(lambda *_: self._refresh_details())

        add_button = QPushButton("Добавить...")
        add_button.clicked.connect(self._add)
        self.edit_button = QPushButton("Редактировать...")
        self.edit_button.clicked.connect(self._edit)
        self.replace_button = QPushButton("Заменить изображение...")
        self.replace_button.clicked.connect(self._replace_image)
        self.duplicate_button = QPushButton("Дублировать...")
        self.duplicate_button.clicked.connect(self._duplicate)
        self.delete_button = QPushButton("Удалить")
        self.delete_button.clicked.connect(self._delete)
        self.use_button = QPushButton("Вставить в шапку")
        self.use_button.clicked.connect(self._use)
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.reject)

        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        actions = QHBoxLayout()
        for button in (
            add_button,
            self.edit_button,
            self.replace_button,
            self.duplicate_button,
            self.delete_button,
        ):
            actions.addWidget(button)
        left.addLayout(actions)

        right = QVBoxLayout()
        right.addWidget(self.preview)
        right.addWidget(self.details)
        right.addStretch(1)
        if selection_mode:
            right.addWidget(self.use_button)
        right.addWidget(close_button)

        root = QHBoxLayout(self)
        root.addLayout(left, 2)
        root.addLayout(right, 1)
        self.resize(940, 520)
        self.refresh()

    def refresh(self, selected_logo_id: str | None = None) -> None:
        selected_logo_id = selected_logo_id or self._selected_logo_id()
        self.list.clear()
        for item in self.controller.items(self.language.value):
            label = item.name
            if item.category:
                label += f" — {item.category}"
            if item.read_only:
                label += "  [заводской]"
            row = QListWidgetItem(label)
            row.setData(Qt.ItemDataRole.UserRole, item.logo_id)
            try:
                asset = self.controller.resolve_asset(item.logo_id, install=False)
                row.setIcon(QIcon(image_asset_pixmap(asset)))
            except (KeyError, OSError, ValueError):
                pass
            self.list.addItem(row)
            if item.logo_id == selected_logo_id:
                self.list.setCurrentItem(row)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._refresh_details()

    def _selected_logo_id(self) -> str | None:
        item = self.list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if isinstance(value, str) else None

    def _selected_item(self) -> LogoCatalogItem | None:
        logo_id = self._selected_logo_id()
        if logo_id is None:
            return None
        try:
            return self.controller.item(logo_id, self.language.value)
        except KeyError:
            return None

    def _refresh_details(self) -> None:
        item = self._selected_item()
        if item is None:
            self.preview.clear()
            self.details.clear()
            return
        try:
            asset = self.controller.resolve_asset(item.logo_id, install=False)
            pixmap = image_asset_pixmap(asset)
            self.preview.setPixmap(
                pixmap.scaled(
                    self.preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        except (KeyError, OSError, ValueError):
            self.preview.clear()
        self.details.setText(
            f"<b>{item.name}</b><br>Категория: {item.category or '—'}<br>"
            f"Тип: {'заводской, только чтение' if item.read_only else 'пользовательский'}"
            + (f"<br>{item.notes}" if item.notes else "")
        )
        editable = not item.read_only
        self.edit_button.setEnabled(True)
        self.replace_button.setEnabled(editable)
        self.delete_button.setEnabled(editable)
        self.duplicate_button.setEnabled(True)

    def _add(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить логотип",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.svg)",
        )
        if not filename:
            return
        source = Path(filename)
        dialog = _LogoMetadataDialog(self, title="Новый логотип", name=source.stem)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, category, notes = dialog.values()
        try:
            entry = self.controller.create_from_file(
                source, name=name, category=category, notes=notes
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(entry.logo_id)

    def _edit(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        if item.read_only:
            name, accepted = QInputDialog.getText(
                self,
                "Копировать заводской логотип",
                "Название пользовательской копии",
                text=item.name,
            )
            if not accepted:
                return
            try:
                entry = self.controller.copy_factory(item.logo_id, name=name)
            except (KeyError, ValueError) as exc:
                QMessageBox.warning(self, self.windowTitle(), str(exc))
                return
            self.refresh(entry.logo_id)
            return
        dialog = _LogoMetadataDialog(
            self,
            title="Редактировать логотип",
            name=item.name,
            category=item.category,
            notes=item.notes,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, category, notes = dialog.values()
        try:
            entry = self.controller.update_metadata(
                item.logo_id, name=name, category=category, notes=notes
            )
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(entry.logo_id)

    def _replace_image(self) -> None:
        item = self._selected_item()
        if item is None or item.read_only:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Заменить изображение логотипа",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.svg)",
        )
        if not filename:
            return
        try:
            self.controller.replace_image(item.logo_id, Path(filename))
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(item.logo_id)

    def _duplicate(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        name, accepted = QInputDialog.getText(
            self,
            "Дублировать логотип",
            "Название копии",
            text=f"{item.name} — копия",
        )
        if not accepted:
            return
        try:
            if item.read_only:
                entry = self.controller.copy_factory(item.logo_id, name=name)
            else:
                entry = self.controller.duplicate(item.logo_id, name)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh(entry.logo_id)

    def _delete(self) -> None:
        item = self._selected_item()
        if item is None or item.read_only:
            return
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            f"Удалить логотип '{item.name}' из каталога?\n"
            "Изображение в уже созданных шапках останется доступным.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete(item.logo_id)
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
        try:
            asset = self.controller.resolve_asset(item.logo_id)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.selected_logo_id = item.logo_id
        self.selected_asset_id = asset.asset_id
        self.accept()
