from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.domain.localized_content import localized_text
from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    all_lba_color_labels,
    lba_intensity_name,
)
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
        "Интерпретация",
        "Заключение геолога по результатам кальциметрии и ЛБА",
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
        "Интерпретация",
        "Кальциметрия және ЛБА нәтижелері бойынша геолог қорытындысы",
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
        "Interpretation",
        "Geologist conclusion based on calcimetry and LBA results",
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
        self.language = language
        text = _TEXT[language]
        self.top_input = QDoubleSpinBox()
        self.bottom_input = QDoubleSpinBox()
        for control, value in ((self.top_input, top_depth), (self.bottom_input, bottom_depth)):
            control.setRange(-100_000.0, 100_000.0)
            control.setDecimals(3)
            control.setSuffix(" m")
            control.setValue(float(value))
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
        for standard in LBA_STANDARD_GROUPS:
            self.lba_group_input.addItem(
                f"{standard.group} — {standard.code}: "
                f"{standard.localized_type_name(language)}",
                standard.group,
            )
        self.lba_type_input = _editable_combo(
            [standard.code for standard in LBA_STANDARD_GROUPS]
        )
        self.lba_group_input.currentIndexChanged.connect(self._on_lba_group_changed)
        self.lba_intensity_input = QComboBox()
        self.lba_intensity_input.addItem("—", None)
        for intensity in range(1, 6):
            self.lba_intensity_input.addItem(
                f"{intensity} — {lba_intensity_name(intensity, language)}",
                intensity,
            )
        self.lba_color_input = _editable_combo(list(all_lba_color_labels(language)))
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
        interpretation = QWidget()
        interpretation_layout = QVBoxLayout(interpretation)
        self.interpretation_input = QPlainTextEdit()
        self.interpretation_input.setPlaceholderText(text[19])
        interpretation_layout.addWidget(self.interpretation_input)
        tabs.addTab(interpretation, text[18])
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        interval = QFormLayout()
        interval.addRow("От, м", self.top_input)
        interval.addRow("До, м", self.bottom_input)
        layout.addLayout(interval)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self.resize(620, 650)
        if sample is not None:
            self._load_sample(sample)

    @property
    def top_depth(self) -> float:
        return float(self.top_input.value())

    @property
    def bottom_depth(self) -> float:
        return float(self.bottom_input.value())

    def _on_lba_group_changed(self) -> None:
        group = self.lba_group_input.currentData()
        standard = next(
            (item for item in LBA_STANDARD_GROUPS if item.group == group),
            None,
        )
        if standard is not None:
            self.lba_type_input.setCurrentText(standard.code)

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
        self.lba_description_input.setText(
            localized_text(
                sample.lba_description_i18n,
                self.language,
                legacy=sample.lba_description,
            )
        )
        self.interpretation_input.setPlainText(
            localized_text(
                sample.analysis_interpretation_i18n,
                self.language,
                legacy=sample.analysis_interpretation,
            )
        )

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
            "analysis_interpretation": self.interpretation_input.toPlainText(),
        }
