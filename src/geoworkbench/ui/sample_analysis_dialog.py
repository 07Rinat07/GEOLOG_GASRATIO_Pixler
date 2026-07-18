from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: (
        "Анализ пробы",
        "Кальциметрия",
        "ЛБА",
        "Кальцит CaCO₃, %",
        "Доломит CaMg(CO₃)₂, %",
        "Группа битумоида 1–5",
        "Тип битумоида",
        "Интенсивность 1–5",
        "Цвет флуоресценции",
        "Форма / распредение",
        "Cut: тип",
        "Cut: скорость",
        "Cut: цвет",
        "Остаток: тип",
        "Остаток: цвет",
        "Запах",
        "Масляное окрашивание",
        "Описание",
    ),
    AppLanguage.KK: (
        "Үлгіні талдау",
        "Кальциметрия",
        "ЛБА",
        "Кальцит CaCO₃, %",
        "Доломит CaMg(CO₃)₂, %",
        "Битумоид тобы 1–5",
        "Битумоид түрі",
        "Қарқындылық 1–5",
        "Флуоресценция түсі",
        "Пішіні / таралуы",
        "Cut: түрі",
        "Cut: жылдамдығы",
        "Cut: түсі",
        "Қалдық: түрі",
        "Қалдық: түсі",
        "Иіс",
        "Майлы боялу",
        "Сипаттама",
    ),
    AppLanguage.EN: (
        "Sample analysis",
        "Calcimetry",
        "LBA",
        "Calcite CaCO₃, %",
        "Dolomite CaMg(CO₃)₂, %",
        "Bitumoid group 1–5",
        "Bitumoid type",
        "Intensity 1–5",
        "Fluorescence color",
        "Form / distribution",
        "Cut type",
        "Cut speed",
        "Cut color",
        "Residue type",
        "Residue color",
        "Odour",
        "Stain",
        "Description",
    ),
}

_INTENSITY_ITEMS = {
    AppLanguage.RU: (
        "1 — одиночные точки",
        "2 — прерывистое кольцо",
        "3 — тонкое кольцо",
        "4 — толстое кольцо",
        "5 — сплошное пятно",
    ),
    AppLanguage.KK: (
        "1 — жеке нүктелер",
        "2 — үзік сақина",
        "3 — жұқа сақина",
        "4 — қалың сақина",
        "5 — тұтас дақ",
    ),
    AppLanguage.EN: (
        "1 — single points",
        "2 — broken ring",
        "3 — thin ring",
        "4 — thick ring",
        "5 — solid spot",
    ),
}


def _editable_combo(items: list[str]) -> QComboBox:
    control = QComboBox()
    control.setEditable(True)
    control.addItems(["", *items])
    return control


class SampleAnalysisDialog(QDialog):
    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        *,
        language: AppLanguage,
        sample: CuttingsSample | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        text = _TEXT[language]
        self.setWindowTitle(f"{text[0]} — {top_depth:g}–{bottom_depth:g} м")
        self.calcite_input = QDoubleSpinBox()
        self.dolomite_input = QDoubleSpinBox()
        for control in (self.calcite_input, self.dolomite_input):
            control.setRange(-1.0, 100.0)
            control.setDecimals(1)
            control.setSuffix(" %")
            control.setSpecialValueText("—")
            control.setValue(-1.0)
        calcimetry = QWidget()
        calcimetry_form = QFormLayout(calcimetry)
        calcimetry_form.addRow(text[3], self.calcite_input)
        calcimetry_form.addRow(text[4], self.dolomite_input)

        self.lba_group_input = QComboBox()
        self.lba_group_input.addItem("—", None)
        for group in range(1, 6):
            self.lba_group_input.addItem(str(group), group)
        self.lba_type_input = _editable_combo(["ЛБ", "МБ", "МСБ", "СБ", "САБ"])
        self.lba_intensity_input = QComboBox()
        self.lba_intensity_input.addItem("—", None)
        for intensity, label in enumerate(_INTENSITY_ITEMS[language], start=1):
            self.lba_intensity_input.addItem(label, intensity)
        self.lba_color_input = _editable_combo(
            [
                "БГ — беловато-голубой",
                "Б — белый",
                "БЖ",
                "СЖ",
                "ГЖ",
                "ЗЖ",
                "Ж",
                "ОЖ",
                "О",
                "СК",
                "ОК",
                "К",
                "ТК",
                "ЗК",
                "ЧЗ",
                "КК",
                "ЧК",
                "Ч",
            ]
        )
        self.lba_distribution_input = _editable_combo(["Pinpoint", "Spotty", "Patchy", "Even"])
        self.lba_cut_input = _editable_combo(
            ["Flash", "Blooming", "Streaming", "Cloudy", "Diffuse"]
        )
        self.lba_cut_speed_input = _editable_combo(["Instant", "Fast", "Moderate", "Slow"])
        self.lba_cut_color_input = _editable_combo(
            ["Pale straw", "Straw", "Amber", "Light brown", "Medium brown", "Dark brown"]
        )
        self.lba_residue_type_input = _editable_combo(["Excellent", "Good", "Trace"])
        self.lba_residue_color_input = _editable_combo(
            ["Pale straw", "Straw", "Amber", "Light brown", "Medium brown", "Dark brown"]
        )
        self.lba_odour_input = _editable_combo(["None", "Faint", "Moderate", "Strong"])
        self.lba_stain_input = _editable_combo(["Pinpoint", "Spotty", "Patchy", "Even"])
        self.lba_description_input = QLineEdit()
        lba = QWidget()
        lba_form = QFormLayout(lba)
        analysis_rows: tuple[tuple[str, QWidget], ...] = (
            (text[5], self.lba_group_input),
            (text[6], self.lba_type_input),
            (text[7], self.lba_intensity_input),
            (text[8], self.lba_color_input),
            (text[9], self.lba_distribution_input),
            (text[10], self.lba_cut_input),
            (text[11], self.lba_cut_speed_input),
            (text[12], self.lba_cut_color_input),
            (text[13], self.lba_residue_type_input),
            (text[14], self.lba_residue_color_input),
            (text[15], self.lba_odour_input),
            (text[16], self.lba_stain_input),
            (text[17], self.lba_description_input),
        )
        for label, analysis_control in analysis_rows:
            lba_form.addRow(label, analysis_control)

        tabs = QTabWidget()
        tabs.addTab(calcimetry, text[1])
        lba_scroll = QScrollArea()
        lba_scroll.setWidgetResizable(True)
        lba_scroll.setWidget(lba)
        tabs.addTab(lba_scroll, text[2])
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self.resize(620, 650)
        if sample is not None:
            self._load_sample(sample)

    def _load_sample(self, sample: CuttingsSample) -> None:
        if sample.calcite_percent is not None:
            self.calcite_input.setValue(sample.calcite_percent)
        if sample.dolomite_percent is not None:
            self.dolomite_input.setValue(sample.dolomite_percent)
        if sample.lba_group is not None:
            self.lba_group_input.setCurrentIndex(self.lba_group_input.findData(sample.lba_group))
        self.lba_type_input.setCurrentText(sample.lba_type_id or "")
        if sample.lba_intensity is not None:
            self.lba_intensity_input.setCurrentIndex(
                self.lba_intensity_input.findData(sample.lba_intensity)
            )
        self.lba_color_input.setCurrentText(sample.lba_color or "")
        self.lba_distribution_input.setCurrentText(sample.lba_distribution or "")
        self.lba_cut_input.setCurrentText(sample.lba_cut or "")
        self.lba_cut_speed_input.setCurrentText(sample.lba_cut_speed or "")
        self.lba_cut_color_input.setCurrentText(sample.lba_cut_color or "")
        self.lba_residue_type_input.setCurrentText(sample.lba_residue_type or "")
        self.lba_residue_color_input.setCurrentText(sample.lba_residue_color or "")
        self.lba_odour_input.setCurrentText(sample.lba_odour or "")
        self.lba_stain_input.setCurrentText(sample.lba_stain or "")
        self.lba_description_input.setText(sample.lba_description or "")

    def values(self) -> dict[str, Any]:
        return {
            "calcite_percent": self.calcite_input.value()
            if self.calcite_input.value() >= 0
            else None,
            "dolomite_percent": self.dolomite_input.value()
            if self.dolomite_input.value() >= 0
            else None,
            "lba_group": self.lba_group_input.currentData(),
            "lba_type_id": self.lba_type_input.currentText(),
            "lba_intensity": self.lba_intensity_input.currentData(),
            "lba_color": self.lba_color_input.currentText(),
            "lba_distribution": self.lba_distribution_input.currentText(),
            "lba_cut": self.lba_cut_input.currentText(),
            "lba_cut_speed": self.lba_cut_speed_input.currentText(),
            "lba_cut_color": self.lba_cut_color_input.currentText(),
            "lba_residue_type": self.lba_residue_type_input.currentText(),
            "lba_residue_color": self.lba_residue_color_input.currentText(),
            "lba_odour": self.lba_odour_input.currentText(),
            "lba_stain": self.lba_stain_input.currentText(),
            "lba_description": self.lba_description_input.text(),
        }
