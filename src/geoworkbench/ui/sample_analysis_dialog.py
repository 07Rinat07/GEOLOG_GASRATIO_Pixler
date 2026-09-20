from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QSize
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
from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    all_lba_color_labels,
    lba_intensity_name,
)
from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES
from geoworkbench.ui.authored_source_language_selector import AuthoredSourceLanguageSelector
from geoworkbench.ui.window_geometry import fit_window_to_screen


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
        "Язык оригинала заключения",
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
        "Қорытындының түпнұсқа тілі",
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
        "Conclusion source language",
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
        self._sample = sample
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
                f"{standard.group} — {standard.code}: {standard.localized_type_name(language)}",
                standard.group,
            )
        self.lba_type_input = _editable_combo([standard.code for standard in LBA_STANDARD_GROUPS])
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
        self._initial_lba_description_i18n: dict[str, str] = {}
        self._initial_interpretation_i18n: dict[str, str] = {}
        self._lba_description_dirty_languages: set[str] = set()
        self._interpretation_dirty_languages: set[str] = set()
        self.lba_description_tabs = QTabWidget()
        self.lba_description_tabs.setObjectName("lba-description-language-tabs")
        self.lba_description_inputs: dict[str, QLineEdit] = {}
        for content_language in AppLanguage:
            language_code = content_language.value
            lba_editor = QLineEdit()
            lba_editor.setObjectName(f"lba-description-{language_code}")
            lba_editor.textChanged.connect(
                lambda _text, code=language_code: self._lba_description_dirty_languages.add(code)
            )
            self.lba_description_inputs[language_code] = lba_editor
            self.lba_description_tabs.addTab(lba_editor, LANGUAGE_NAMES[content_language])
        self.lba_description_tabs.setCurrentIndex(tuple(AppLanguage).index(language))
        self.lba_description_input = self.lba_description_inputs[language.value]
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
            (text[17], self.lba_description_tabs),
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
        interpretation_source_form = QFormLayout()
        self.interpretation_source_language_input = AuthoredSourceLanguageSelector(
            interpretation,
            language=language,
        )
        self.interpretation_source_language_input.setObjectName(
            "analysis-interpretation-source-language"
        )
        if sample is not None:
            self.interpretation_source_language_input.load_existing(
                self._persisted_interpretation_source_language(sample)
            )
        interpretation_source_form.addRow(
            text[20], self.interpretation_source_language_input
        )
        interpretation_layout.addLayout(interpretation_source_form)
        self.interpretation_language_tabs = QTabWidget()
        self.interpretation_language_tabs.setObjectName("analysis-interpretation-language-tabs")
        self.interpretation_inputs: dict[str, QPlainTextEdit] = {}
        for content_language in AppLanguage:
            language_code = content_language.value
            interpretation_editor = QPlainTextEdit()
            interpretation_editor.setObjectName(f"analysis-interpretation-{language_code}")
            interpretation_editor.setPlaceholderText(_TEXT[content_language][19])
            interpretation_editor.textChanged.connect(
                lambda code=language_code: self._interpretation_dirty_languages.add(code)
            )
            self.interpretation_inputs[language_code] = interpretation_editor
            self.interpretation_language_tabs.addTab(
                interpretation_editor, LANGUAGE_NAMES[content_language]
            )
        self.interpretation_language_tabs.setCurrentIndex(tuple(AppLanguage).index(language))
        self.interpretation_input = self.interpretation_inputs[language.value]
        interpretation_layout.addWidget(self.interpretation_language_tabs)
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
        layout.addWidget(tabs, 1)
        layout.addWidget(buttons)
        fit_window_to_screen(
            self,
            preferred=QSize(620, 650),
            minimum=QSize(460, 340),
        )
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

    def _persisted_interpretation_source_language(
        self, sample: CuttingsSample
    ) -> str | None:
        parent = self.parentWidget()
        controller = getattr(parent, "cuttings_controller", None)
        getter = getattr(controller, "analysis_interpretation_source_language", None)
        if not callable(getter):
            return None
        try:
            value = getter(sample.sample_id)
        except (KeyError, RuntimeError):
            return None
        if value is None:
            return None
        try:
            return AppLanguage(str(value)).value
        except ValueError:
            return None

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
        self._initial_lba_description_i18n = dict(sample.lba_description_i18n)
        self._initial_interpretation_i18n = dict(sample.analysis_interpretation_i18n)
        self._lba_description_dirty_languages.clear()
        self._interpretation_dirty_languages.clear()
        for language_code, lba_editor in self.lba_description_inputs.items():
            value = sample.lba_description_i18n.get(language_code, "")
            if language_code == "ru" and not value:
                value = sample.lba_description or ""
            lba_editor.blockSignals(True)
            lba_editor.setText(value)
            lba_editor.blockSignals(False)
        for language_code, interpretation_editor in self.interpretation_inputs.items():
            value = sample.analysis_interpretation_i18n.get(language_code, "")
            if language_code == "ru" and not value:
                value = sample.analysis_interpretation or ""
            interpretation_editor.blockSignals(True)
            interpretation_editor.setPlainText(value)
            interpretation_editor.blockSignals(False)

    def values(self) -> dict[str, Any]:
        interpretation_source_language = (
            self.interpretation_source_language_input.submitted_language()
        )
        if (
            self._sample is None
            and interpretation_source_language is not None
            and not self.interpretation_inputs[
                interpretation_source_language
            ].toPlainText().strip()
        ):
            interpretation_source_language = None
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
            "lba_description_i18n": self._localized_values(
                self._initial_lba_description_i18n,
                self.lba_description_inputs,
                self._lba_description_dirty_languages,
            ),
            "analysis_interpretation": self.interpretation_input.toPlainText(),
            "analysis_interpretation_i18n": self._localized_values(
                self._initial_interpretation_i18n,
                self.interpretation_inputs,
                self._interpretation_dirty_languages,
            ),
            "analysis_interpretation_source_language": interpretation_source_language,
        }

    @staticmethod
    def _localized_values(
        initial: dict[str, str],
        editors: Mapping[str, QLineEdit | QPlainTextEdit],
        dirty_languages: set[str],
    ) -> dict[str, str]:
        values = dict(initial)
        for language in dirty_languages:
            editor = editors[language]
            text = (
                editor.text() if isinstance(editor, QLineEdit) else editor.toPlainText()
            ).strip()
            if text:
                values[language] = text
            else:
                values.pop(language, None)
        return values
