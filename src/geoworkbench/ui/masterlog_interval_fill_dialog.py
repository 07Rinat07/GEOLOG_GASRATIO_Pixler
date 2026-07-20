from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: {
        "create": "Состав шлама",
        "edit": "Редактирование пробы шлама",
        "top": "Кровля, м",
        "bottom": "Подошва, м",
        "code": "Код",
        "rock": "Порода",
        "total": "Сумма пород должна быть равна 100%",
        "limit": "В одной пробе допускается не более четырёх пород",
        "interval": "Кровля должна быть меньше подошвы",
        "hint": "Изменение состава не удаляет ЛБА, кальциметрию и описание этой пробы.",
    },
    AppLanguage.KK: {
        "create": "Шлам құрамы",
        "edit": "Шлам үлгісін өңдеу",
        "top": "Жоғарғы шекара, м",
        "bottom": "Төменгі шекара, м",
        "code": "Код",
        "rock": "Тау жынысы",
        "total": "Жыныстар қосындысы 100% болуы керек",
        "limit": "Бір үлгіде төрт жыныстан артық болмауы керек",
        "interval": "Жоғарғы шекара төменгі шекарадан кіші болуы керек",
        "hint": "Құрамды өзгерту осы үлгінің ЛБА, кальциметрия және сипаттамасын жоймайды.",
    },
    AppLanguage.EN: {
        "create": "Cuttings composition",
        "edit": "Edit cuttings sample",
        "top": "Top, m",
        "bottom": "Bottom, m",
        "code": "Code",
        "rock": "Rock",
        "total": "Rock percentages must total 100%",
        "limit": "A sample may contain no more than four rock types",
        "interval": "Top must be less than bottom",
        "hint": "Changing composition preserves this sample's LBA, calcimetry and description.",
    },
}


class CuttingsCompositionDialog(QDialog):
    """Create or edit one cuttings sample composition.

    The dialog edits the existing sample in place.  Only interval bounds and up
    to four rock percentages are changed; laboratory analysis and description
    stay attached to the same sample ID.
    """

    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        catalog: tuple[CatalogLithotype, ...],
        *,
        language: AppLanguage,
        sample: CuttingsSample | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self._text = _TEXT[language]
        self.setWindowTitle(self._text["edit"] if sample is not None else self._text["create"])

        layout = QVBoxLayout(self)
        hint = QLabel(self._text["hint"])
        hint.setWordWrap(True)
        hint.setObjectName("cuttings-edit-hint")
        layout.addWidget(hint)

        interval_form = QFormLayout()
        self.top_input = self._depth_input(top_depth)
        self.top_input.setObjectName("cuttings-edit-top")
        self.bottom_input = self._depth_input(bottom_depth)
        self.bottom_input.setObjectName("cuttings-edit-bottom")
        interval_form.addRow(self._text["top"], self.top_input)
        interval_form.addRow(self._text["bottom"], self.bottom_input)
        layout.addLayout(interval_form)

        self.table = QTableWidget(len(catalog), 3)
        self.table.setObjectName("cuttings-composition-table")
        self.table.setHorizontalHeaderLabels([self._text["code"], self._text["rock"], "%"])
        existing = {
            component.lithotype_id: float(component.percentage)
            for component in (sample.components if sample is not None else ())
        }
        for row, item in enumerate(catalog):
            code = QTableWidgetItem(item.code)
            code.setData(256, item.lithotype_id)
            self.table.setItem(row, 0, code)
            self.table.setItem(row, 1, QTableWidgetItem(item.localized_name(language.value)))
            percentage = QDoubleSpinBox()
            percentage.setObjectName(f"cuttings-percentage-{item.lithotype_id}")
            percentage.setRange(0, 100)
            percentage.setDecimals(1)
            percentage.setSuffix(" %")
            percentage.setValue(existing.get(item.lithotype_id, 0.0))
            self.table.setCellWidget(row, 2, percentage)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        self.validation_label = QLabel("")
        self.validation_label.setObjectName("cuttings-validation")
        self.validation_label.setStyleSheet("color: #dc2626; font-weight: 600;")
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.resize(560, 680)

    @staticmethod
    def _depth_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        control.setSuffix(" m")
        control.setValue(float(value))
        return control

    @property
    def top_depth(self) -> float:
        return float(self.top_input.value())

    @property
    def bottom_depth(self) -> float:
        return float(self.bottom_input.value())

    def components(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            control = self.table.cellWidget(row, 2)
            assert item is not None and isinstance(control, QDoubleSpinBox)
            if control.value() > 0:
                result[str(item.data(256))] = float(control.value())
        return result

    def _accept_if_valid(self) -> None:
        self.validation_label.clear()
        if self.top_depth >= self.bottom_depth:
            self.validation_label.setText(self._text["interval"])
            return
        components = self.components()
        if len(components) > 4:
            self.validation_label.setText(self._text["limit"])
            return
        if abs(sum(components.values()) - 100.0) > 0.01:
            self.validation_label.setText(self._text["total"])
            return
        self.accept()
