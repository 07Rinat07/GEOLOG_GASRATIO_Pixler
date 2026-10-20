"""Editable independent DataLog observations, shared by both cuttings dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.oil_show_observations import (
    OilShowMethod,
    OilShowObservation,
    OilShowQuality,
    validate_oil_show_observations,
)
from geoworkbench.services.localization import AppLanguage


_LABELS: dict[AppLanguage, tuple[str, ...]] = {
    AppLanguage.RU: (
        "Метод", "Площадь, %", "Цвет", "Яркость / выраженность",
        "Распределение", "Скорость реакции", "Примечание", "Контроль",
        "Отдельные наблюдения DataLog (UV− и UV+). Пропуск означает «не исследовано». "
        "Баллы ЛБА Флоровской сюда не переносятся автоматически.",
    ),
    AppLanguage.KK: (
        "Әдіс", "Ауданы, %", "Түсі", "Жарқырауы / айқындылығы",
        "Таралуы", "Реакция жылдамдығы", "Ескерту", "Тексеру",
        "DataLog бақылаулары бөлек (UV− және UV+). Бос ұяшық — «зерттелмеген». "
        "Флоровская ЛБА балы автоматты түрде көшірілмейді.",
    ),
    AppLanguage.EN: (
        "Test", "Coverage, %", "Colour", "Brightness / strength",
        "Distribution", "Reaction speed", "Notes", "QC",
        "Independent DataLog tests (UV− and UV+). Empty means unmeasured. "
        "Do not automatically translate the Florovskaya LBA score into these tests.",
    ),
}
_METHOD_LABELS: dict[OilShowMethod, tuple[str, str, str]] = {
    OilShowMethod.ODOUR: ("Запах", "Иіс", "Odour"),
    OilShowMethod.VISIBLE_STAIN: ("Пятна, видимый свет", "Көрінетін дақтар", "Stain, daylight"),
    OilShowMethod.DIRECT_FLUORESCENCE_UV: ("Прямое свечение, UV+", "Тікелей жарқырау, UV+", "Direct fluorescence, UV+"),
    OilShowMethod.SOLVENT_CUT_DAYLIGHT: ("Cut, видимый свет", "Cut, қалыпты жарық", "Solvent cut, daylight"),
    OilShowMethod.SOLVENT_CUT_UV: ("Cut, UV+", "Cut, UV+", "Solvent cut, UV+"),
    OilShowMethod.RESIDUE_DAYLIGHT: ("Остаток cut, видимый свет", "Cut қалдығы, қалыпты жарық", "Post-cut residue, daylight"),
    OilShowMethod.RESIDUE_UV: ("Остаток cut, UV+", "Cut қалдығы, UV+", "Post-cut residue, UV+"),
    OilShowMethod.CAPILLARY_DAYLIGHT: ("Вытяжка, видимый свет", "Сығынды, қалыпты жарық", "Capillary extract, daylight"),
    OilShowMethod.CAPILLARY_UV: ("Вытяжка, UV+", "Сығынды, UV+", "Capillary extract, UV+"),
}
_QUALITY_LABELS: dict[OilShowQuality, tuple[str, str, str]] = {
    OilShowQuality.UNCHECKED: ("Не проверено", "Тексерілмеген", "Unchecked"),
    OilShowQuality.VERIFIED: ("Проверено", "Тексерілді", "Verified"),
    OilShowQuality.SUSPECT: ("Сомнительно", "Күмәнді", "Suspect"),
}


class OilShowObservationEditor(QWidget):
    """One independent row per method, no overwrite of legacy LBA fields."""

    def __init__(
        self,
        language: AppLanguage,
        observations: list[OilShowObservation] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        labels = _LABELS[language]
        locale_index = (AppLanguage.RU, AppLanguage.KK, AppLanguage.EN).index(language)
        layout = QVBoxLayout(self)
        hint = QLabel(labels[8])
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(len(OilShowMethod), 8, self)
        self.table.setObjectName("datalog-independent-show-table")
        self.table.setHorizontalHeaderLabels(list(labels[:8]))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(265)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self._editors: dict[
            OilShowMethod,
            tuple[QDoubleSpinBox, tuple[QLineEdit, ...], QComboBox],
        ] = {}
        previous = {item.method: item for item in validate_oil_show_observations(observations or [])}
        for row, method in enumerate(OilShowMethod):
            title = QTableWidgetItem(_METHOD_LABELS[method][locale_index])
            self.table.setItem(row, 0, title)
            area = QDoubleSpinBox()
            area.setObjectName(f"show-{method.value}-area")
            area.setRange(-1.0, 100.0)
            area.setDecimals(1)
            area.setSpecialValueText("—")
            area.setValue(-1)
            self.table.setCellWidget(row, 1, area)
            fields: list[QLineEdit] = []
            for column, field_name in enumerate(
                ("colour", "brightness", "distribution", "reaction_speed", "notes"),
                start=2,
            ):
                entry = QLineEdit()
                entry.setObjectName(f"show-{method.value}-{field_name}")
                entry.setMaxLength(2_000 if field_name == "notes" else 100)
                self.table.setCellWidget(row, column, entry)
                fields.append(entry)
            quality = QComboBox()
            quality.setObjectName(f"show-{method.value}-quality")
            for kind in OilShowQuality:
                quality.addItem(_QUALITY_LABELS[kind][locale_index], kind)
            self.table.setCellWidget(row, 7, quality)
            self._editors[method] = (area, tuple(fields), quality)
            stored = previous.get(method)
            if stored is not None:
                if stored.area_percent is not None:
                    area.setValue(stored.area_percent)
                for widget, name in zip(
                    fields, ("colour", "brightness", "distribution", "reaction_speed", "notes"),
                    strict=True,
                ):
                    widget.setText(getattr(stored, name) or "")
                quality.setCurrentIndex(quality.findData(stored.quality))
        layout.addWidget(self.table)

    def observations(self) -> list[OilShowObservation]:
        result: list[OilShowObservation] = []
        for method, (area, widgets, quality) in self._editors.items():
            area_value = area.value() if area.value() >= 0 else None
            values = tuple(widget.text().strip() or None for widget in widgets)
            if area_value is None and not any(values):
                continue
            result.append(OilShowObservation(
                method=method,
                area_percent=area_value,
                colour=values[0],
                brightness=values[1],
                distribution=values[2],
                reaction_speed=values[3],
                notes=values[4],
                quality=quality.currentData(),
            ))
        return validate_oil_show_observations(result)


__all__ = ["OilShowObservationEditor"]
