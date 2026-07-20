from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
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
from geoworkbench.printing.image_asset_rendering import image_asset_pixmap
from geoworkbench.printing.image_assets import ImageAssetError
from geoworkbench.printing.masterlog_symbols import BUILTIN_MASTERLOG_SYMBOLS
from geoworkbench.services.localization import AppLanguage, Localizer


class MasterlogAssetsDialog(QDialog):
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
        self.setWindowTitle(self.localizer.text("masterlog_assets.title"))
        self.list = QListWidget()
        self.list.setObjectName("masterlog-assets-list")
        self.delete_button = QPushButton(self.localizer.text("common.delete"))
        self.rename_button = QPushButton(self.localizer.text("common.rename"))
        self.symbol_input = QComboBox()
        for symbol in BUILTIN_MASTERLOG_SYMBOLS:
            self.symbol_input.addItem(self.localizer.text(symbol.name_key), symbol.symbol_id)
        self.add_symbol_button = QPushButton(self.localizer.text("masterlog_assets.add_symbol"))
        close_button = QPushButton(self.localizer.text("common.close"))
        self.delete_button.clicked.connect(self._delete)
        self.rename_button.clicked.connect(self._rename)
        self.add_symbol_button.clicked.connect(self._add_symbol)
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.rename_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        symbol_row = QHBoxLayout()
        symbol_row.addWidget(self.symbol_input, 1)
        symbol_row.addWidget(self.add_symbol_button)
        layout.addLayout(symbol_row)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.resize(520, 300)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for asset in sorted(
            self.controller.session.image_assets.values(),
            key=lambda item: item.original_name.casefold(),
        ):
            references = self.controller.image_asset_references(asset.asset_id)
            usage = (
                self.localizer.text("masterlog_assets.used", templates=", ".join(references))
                if references
                else self.localizer.text("masterlog_assets.unused")
            )
            item = QListWidgetItem(
                self.localizer.text(
                    "masterlog_assets.item",
                    name=asset.original_name,
                    size=len(asset.payload),
                    usage=usage,
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, asset.asset_id)
            item.setIcon(QIcon(image_asset_pixmap(asset)))
            self.list.addItem(item)

    def _add_symbol(self) -> None:
        index = self.symbol_input.currentIndex()
        if index < 0:
            return
        symbol = BUILTIN_MASTERLOG_SYMBOLS[index]
        name = self.localizer.text(symbol.name_key)
        try:
            asset = self.controller.install_image_asset(symbol.create_asset(name))
        except (ImageAssetError, KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()
        matches = self.list.findItems(asset.original_name, Qt.MatchFlag.MatchStartsWith)
        if matches:
            self.list.setCurrentItem(matches[0])

    def _delete(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        try:
            self.controller.remove_image_asset(str(item.data(Qt.ItemDataRole.UserRole)))
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()

    def _rename(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        asset_id = str(item.data(Qt.ItemDataRole.UserRole))
        asset = self.controller.session.image_assets[asset_id]
        name, accepted = QInputDialog.getText(
            self,
            self.localizer.text("masterlog_assets.rename"),
            self.localizer.text("masterlog_assets.name"),
            text=asset.original_name,
        )
        if not accepted:
            return
        try:
            self.controller.rename_image_asset(asset_id, name)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()

    def _selected_item(self) -> QListWidgetItem | None:
        item = self.list.currentItem()
        if item is None:
            QMessageBox.information(
                self, self.windowTitle(), self.localizer.text("masterlog_assets.select")
            )
        return item
