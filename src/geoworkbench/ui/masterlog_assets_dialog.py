from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
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
        close_button = QPushButton(self.localizer.text("common.close"))
        self.delete_button.clicked.connect(self._delete)
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
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
                self.localizer.text(
                    "masterlog_assets.used", templates=", ".join(references)
                )
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
            self.list.addItem(item)

    def _delete(self) -> None:
        item = self.list.currentItem()
        if item is None:
            QMessageBox.information(
                self, self.windowTitle(), self.localizer.text("masterlog_assets.select")
            )
            return
        try:
            self.controller.remove_image_asset(
                str(item.data(Qt.ItemDataRole.UserRole))
            )
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()
