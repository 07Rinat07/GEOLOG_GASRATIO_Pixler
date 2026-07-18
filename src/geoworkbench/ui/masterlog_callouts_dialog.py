from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geoworkbench.project.masterlog_inspection_controller import (
    MasterlogInspectionController,
)
from geoworkbench.services.localization import AppLanguage


class MasterlogCalloutsDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogInspectionController,
        template_id: str,
        *,
        language: AppLanguage,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.template_id = template_id
        self.language = language
        self.setWindowTitle(
            {
                AppLanguage.RU: "Печатные выноски",
                AppLanguage.KK: "Баспа белгілері",
                AppLanguage.EN: "Print callouts",
            }[language]
        )
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [
                {AppLanguage.RU: "Глубина", AppLanguage.KK: "Тереңдік", AppLanguage.EN: "Depth"}[
                    language
                ],
                {AppLanguage.RU: "Колонка", AppLanguage.KK: "Баған", AppLanguage.EN: "Column"}[
                    language
                ],
                {AppLanguage.RU: "Текст", AppLanguage.KK: "Мәтін", AppLanguage.EN: "Text"}[
                    language
                ],
            ]
        )
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.remove_button = QPushButton(
            {AppLanguage.RU: "Удалить", AppLanguage.KK: "Жою", AppLanguage.EN: "Remove"}[language]
        )
        self.remove_button.clicked.connect(self._remove)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(720, 420)
        self.refresh()

    def refresh(self) -> None:
        callouts = self.controller.available(self.template_id)
        template = self.controller.session.project.masterlog_templates.get(self.template_id)
        columns = {item.column_id: item.title for item in template.columns} if template else {}
        self.table.setRowCount(len(callouts))
        for row, item in enumerate(callouts):
            top = item.top_depth if item.top_depth is not None else item.y
            depth = (
                f"{top:g}–{item.bottom_depth:g} м"
                if item.bottom_depth is not None
                else f"{top:g} м"
            )
            depth_item = QTableWidgetItem(depth)
            depth_item.setData(Qt.ItemDataRole.UserRole, item.object_id)
            self.table.setItem(row, 0, depth_item)
            self.table.setItem(
                row, 1, QTableWidgetItem(columns.get(item.track_id or "", item.track_id or ""))
            )
            self.table.setItem(row, 2, QTableWidgetItem(str(item.properties.get("text", ""))))
        self.table.resizeColumnsToContents()

    def _remove(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(self, self.windowTitle(), "Select a callout")
            return
        try:
            self.controller.remove(self.template_id, str(item.data(Qt.ItemDataRole.UserRole)))
        except (KeyError, RuntimeError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()
