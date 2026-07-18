from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.services.localization import AppLanguage


class CuttingsCompositionDialog(QDialog):
    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        catalog: tuple[CatalogLithotype, ...],
        *,
        language: AppLanguage,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(
            {
                AppLanguage.RU: "Состав шлама",
                AppLanguage.KK: "Шлам құрамы",
                AppLanguage.EN: "Cuttings composition",
            }[language]
        )
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{top_depth:g}–{bottom_depth:g} м"))
        self.table = QTableWidget(len(catalog), 3)
        self.table.setHorizontalHeaderLabels(
            [
                {AppLanguage.RU: "Код", AppLanguage.KK: "Код", AppLanguage.EN: "Code"}[language],
                {AppLanguage.RU: "Порода", AppLanguage.KK: "Тау жынысы", AppLanguage.EN: "Rock"}[
                    language
                ],
                "%",
            ]
        )
        for row, item in enumerate(catalog):
            code = QTableWidgetItem(item.code)
            code.setData(256, item.lithotype_id)
            self.table.setItem(row, 0, code)
            self.table.setItem(row, 1, QTableWidgetItem(item.localized_name(language.value)))
            percentage = QDoubleSpinBox()
            percentage.setRange(0, 100)
            percentage.setDecimals(1)
            self.table.setCellWidget(row, 2, percentage)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(520, 600)

    def components(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            control = self.table.cellWidget(row, 2)
            assert item is not None and isinstance(control, QDoubleSpinBox)
            if control.value() > 0:
                result[str(item.data(256))] = control.value()
        return result

    def _accept_if_valid(self) -> None:
        total = sum(self.components().values())
        if abs(total - 100.0) <= 0.01:
            self.accept()
            return
        self.setWindowTitle(
            {
                AppLanguage.RU: "Сумма должна быть 100%",
                AppLanguage.KK: "Қосынды 100% болуы керек",
                AppLanguage.EN: "Total must be 100%",
            }[self.language]
        )
