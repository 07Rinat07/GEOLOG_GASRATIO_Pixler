from __future__ import annotations

from copy import deepcopy
import re

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.well_passport import (
    CONSTRUCTION_FIELDS,
    DATE_FIELDS,
    LOCALIZED_FIELDS,
    NUMERIC_FIELDS,
    SHARED_TEXT_FIELDS,
    WellPassport,
)
from geoworkbench.printing.header_fields import (
    editable_header_field_definitions,
    header_field_label,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_passport_controller import WellPassportController
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: {
        "title": "Паспорт скважины",
        "general": "Общие данные",
        "original": "Исходный текст",
        "hint": (
            "Один паспорт используется всеми шапками этой скважины. После сохранения "
            "незаполненные поля паспорта будут пустыми, а не взятыми из старой шапки. "
            "Для переноса старых значений явно выберите шапку под нужным полем; "
            "её исходные данные останутся без изменений. Интервал печати и масштаб "
            "настраиваются отдельно в форме."
        ),
        "languages": (
            "Введите переводы отдельно на каждой языковой вкладке. Автоматический перевод "
            "не выполняется: если перевод отсутствует, при просмотре может выводиться "
            "текст на другом заполненном языке."
        ),
        "manual": "Оставить текущее / ввести вручную",
        "source": "Перенести из шапки",
        "number": "Число в метрах, например 1250,5",
        "coordinate": "Десятичные градусы, например 46,4683",
        "diameter": "Число в миллиметрах, например 177,8",
        "date": "ГГГГ-ММ-ДД, например 2026-09-05",
        "customer_logo": "Логотип заказчика",
        "contractor_logo": "Логотип исполнителя",
        "default_logo": "Использовать логотип макета",
        "no_logo": "Без логотипа",
        "missing_logo": "Сохранённый логотип недоступен",
        "logos_hint": (
            "Можно выбрать изображение, уже добавленное в проект. Вариант «Использовать "
            "логотип макета» сохраняет оформление шапки, включая BP Services по умолчанию."
        ),
        "save": "Сохранить",
        "cancel": "Отмена",
        "invalid": "Проверьте данные паспорта",
        "invalid_hint": (
            "Используйте числа без единиц измерения, даты ГГГГ-ММ-ДД и координаты "
            "в десятичных градусах. Проверьте диапазоны, порядок дат и наличие логотипа "
            "в проекте. Изменения не сохранены."
        ),
    },
    AppLanguage.KK: {
        "title": "Ұңғыма паспорты",
        "general": "Ортақ деректер",
        "original": "Бастапқы мәтін",
        "hint": (
            "Бір паспорт осы ұңғыманың барлық тақырыптарына қолданылады. Сақтағаннан кейін "
            "толтырылмаған паспорт өрістері ескі тақырыптан алынбай, бос қалады. Ескі "
            "мәндерді көшіру үшін тиісті өрістің астынан тақырыпты нақты таңдаңыз; "
            "оның бастапқы деректері өзгермейді. Басып шығару аралығы мен масштаб "
            "пішінде бөлек реттеледі."
        ),
        "languages": (
            "Аудармаларды әр тіл қойындысына бөлек енгізіңіз. Автоматты аударма "
            "жасалмайды: аударма жоқ болса, қарау кезінде басқа толтырылған тілдегі "
            "мәтін көрсетілуі мүмкін."
        ),
        "manual": "Ағымдағыны сақтау / қолмен енгізу",
        "source": "Тақырыптан көшіру",
        "number": "Метрмен сан, мысалы 1250,5",
        "coordinate": "Ондық градус, мысалы 46,4683",
        "diameter": "Миллиметрмен сан, мысалы 177,8",
        "date": "ЖЖЖЖ-АА-КК, мысалы 2026-09-05",
        "customer_logo": "Тапсырыс берушінің логотипі",
        "contractor_logo": "Орындаушының логотипі",
        "default_logo": "Макет логотипін қолдану",
        "no_logo": "Логотипсіз",
        "missing_logo": "Сақталған логотип қолжетімсіз",
        "logos_hint": (
            "Жобаға бұрын қосылған суретті таңдауға болады. «Макет логотипін қолдану» "
            "нұсқасы тақырып безендіруін, соның ішінде әдепкі BP Services логотипін сақтайды."
        ),
        "save": "Сақтау",
        "cancel": "Бас тарту",
        "invalid": "Паспорт деректерін тексеріңіз",
        "invalid_hint": (
            "Өлшем бірлігінсіз сандарды, ЖЖЖЖ-АА-КК күндерін және ондық градустағы "
            "координаттарды пайдаланыңыз. Ауқымдарды, күндердің ретін және жобада "
            "логотиптің бар-жоғын тексеріңіз. Өзгерістер сақталмады."
        ),
    },
    AppLanguage.EN: {
        "title": "Well passport",
        "general": "Shared data",
        "original": "Original text",
        "hint": (
            "One passport supplies all headers for this well. Once saved, unfilled passport "
            "fields remain blank instead of using old header values. To adopt an old value, "
            "explicitly select its header beneath the field; the original header stays "
            "unchanged. Print interval and scale are configured separately in the form."
        ),
        "languages": (
            "Enter translations separately on each language tab. No automatic translation "
            "is performed: a missing translation may display text from another populated "
            "language during preview."
        ),
        "manual": "Keep current / enter manually",
        "source": "Adopt from header",
        "number": "Number in metres, e.g. 1250.5",
        "coordinate": "Decimal degrees, e.g. 46.4683",
        "diameter": "Number in millimetres, e.g. 177.8",
        "date": "YYYY-MM-DD, e.g. 2026-09-05",
        "customer_logo": "Customer logo",
        "contractor_logo": "Contractor logo",
        "default_logo": "Use layout logo",
        "no_logo": "No logo",
        "missing_logo": "Saved logo unavailable",
        "logos_hint": (
            "Choose an image already added to the project. “Use layout logo” retains the "
            "header design, including the default BP Services logo."
        ),
        "save": "Save",
        "cancel": "Cancel",
        "invalid": "Check passport data",
        "invalid_hint": (
            "Use numbers without units, YYYY-MM-DD dates and coordinates in decimal "
            "degrees. Check valid ranges, date order and that the logo exists in the "
            "project. Changes have not been saved."
        ),
    },
}


class WellPassportDialog(QDialog):
    """Edit a detached passport; only accepting the dialog changes the session."""

    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.controller = WellPassportController(session)
        self._draft = self.controller.draft()
        self._text = _TEXT[language]
        self.inputs: dict[str, QLineEdit | QTextEdit] = {}
        self.localized_inputs: dict[str, dict[str, QLineEdit | QTextEdit]] = {}
        self.source_combos: dict[tuple[str, str], QComboBox] = {}
        self.logo_inputs: dict[str, QComboBox] = {}
        self.setWindowTitle(self._text["title"])
        self.resize(800, 720)

        layout = QVBoxLayout(self)
        hint = QLabel(self._text["hint"])
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._build_shared_tab(session)
        for content_language, title in (("ru", "Русский"), ("kk", "Қазақша"), ("en", "English")):
            self._build_language_tab(content_language, title)
        self._build_original_tab()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self._text["save"])
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._text["cancel"])
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_tab(self, title: str) -> QFormLayout:
        content = QWidget()
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.tabs.addTab(scroll, title)
        return form

    def _build_shared_tab(self, session: ProjectSession) -> None:
        form = self._add_tab(self._text["general"])
        for definition in editable_header_field_definitions():
            field_name = definition.field_id
            if field_name not in SHARED_TEXT_FIELDS | NUMERIC_FIELDS | DATE_FIELDS:
                continue
            editor = self._new_editor(
                field_name, self._draft.values.get(field_name, ""), definition.multiline
            )
            if isinstance(editor, QLineEdit):
                if field_name in NUMERIC_FIELDS:
                    key = (
                        "coordinate"
                        if field_name in {"header.latitude", "header.longitude"}
                        else "number"
                    )
                    if field_name in CONSTRUCTION_FIELDS and field_name.endswith("_diameter"):
                        key = "diameter"
                    editor.setPlaceholderText(self._text[key])
                elif field_name in DATE_FIELDS:
                    editor.setPlaceholderText(self._text["date"])
            self.inputs[field_name] = editor
            form.addRow(definition.label(self.language), editor)
            self._add_sources(form, field_name, "", editor)

        for role in ("customer", "contractor"):
            combo = QComboBox()
            combo.setObjectName(f"passport-logo-{role}")
            combo.addItem(self._text["default_logo"], None)
            combo.addItem(self._text["no_logo"], "")
            for asset in sorted(session.image_assets.values(), key=lambda item: item.original_name):
                combo.addItem(asset.original_name, asset.asset_id)
            selected = self._draft.logo_refs.get(role)
            index = combo.findData(selected)
            if index < 0 and selected:
                combo.addItem(self._text["missing_logo"], selected)
                index = combo.count() - 1
            combo.setCurrentIndex(max(0, index))
            self.logo_inputs[role] = combo
            form.addRow(self._text[f"{role}_logo"], combo)
        hint = QLabel(self._text["logos_hint"])
        hint.setWordWrap(True)
        form.addRow(hint)

    def _build_language_tab(self, language: str, title: str) -> None:
        form = self._add_tab(title)
        hint = QLabel(self._text["languages"])
        hint.setWordWrap(True)
        form.addRow(hint)
        inputs: dict[str, QLineEdit | QTextEdit] = {}
        self.localized_inputs[language] = inputs
        for definition in editable_header_field_definitions():
            field_name = definition.field_id
            if field_name not in LOCALIZED_FIELDS:
                continue
            value = self._draft.texts_i18n.get(field_name, {}).get(language, "")
            editor = self._new_editor(field_name, value, definition.multiline, language)
            inputs[field_name] = editor
            form.addRow(definition.label(self.language), editor)
            self._add_sources(form, field_name, language, editor)

    def _build_original_tab(self) -> None:
        original = {
            field_name: values["und"]
            for field_name, values in self._draft.texts_i18n.items()
            if values.get("und")
        }
        if not original:
            return
        form = self._add_tab(self._text["original"])
        for field_name, value in original.items():
            editor = self._new_editor(field_name, value, True, "und")
            editor.setReadOnly(True)
            form.addRow(header_field_label(field_name, self.language), editor)

    @staticmethod
    def _new_editor(
        field_name: str, value: str | float, multiline: bool, language: str = ""
    ) -> QLineEdit | QTextEdit:
        editor: QLineEdit | QTextEdit
        if multiline:
            editor = QTextEdit()
            editor.setAcceptRichText(False)
            editor.setMaximumHeight(100)
            editor.setPlainText(str(value))
        else:
            editor = QLineEdit(str(value))
        editor.setObjectName(f"passport-{field_name}-{language}")
        return editor

    def _add_sources(
        self,
        form: QFormLayout,
        field_name: str,
        language: str,
        editor: QLineEdit | QTextEdit,
    ) -> None:
        candidates = self.controller.legacy_candidates(field_name, language or "ru")
        if not candidates:
            return
        combo = QComboBox()
        combo.setObjectName(f"passport-source-{field_name}-{language}")
        combo.addItem(self._text["manual"], None)
        for candidate in candidates:
            value = candidate.value
            if field_name in CONSTRUCTION_FIELDS and field_name in NUMERIC_FIELDS:
                unit = r"(?:мм|mm)" if field_name.endswith("_diameter") else r"(?:м|m)"
                match = re.fullmatch(rf"\s*Ø?\s*([+-]?\d+(?:[.,]\d+)?)\s*{unit}?\s*", value)
                if match:
                    value = match.group(1)
            combo.addItem(f"{candidate.template_name}: {candidate.value}", value)
        combo.currentIndexChanged.connect(
            lambda _index, target=editor, source=combo: self._adopt_source(target, source)
        )
        self.source_combos[field_name, language] = combo
        form.addRow(self._text["source"], combo)

    @staticmethod
    def _adopt_source(editor: QLineEdit | QTextEdit, combo: QComboBox) -> None:
        value = combo.currentData()
        if value is None:
            return
        if isinstance(editor, QTextEdit):
            editor.setPlainText(value)
        else:
            editor.setText(value)

    @staticmethod
    def _input_text(editor: QLineEdit | QTextEdit) -> str:
        return (editor.toPlainText() if isinstance(editor, QTextEdit) else editor.text()).strip()

    def _show_validation_error(self, field_name: str = "") -> None:
        label = header_field_label(field_name, self.language) if field_name in self.inputs else ""
        message = f"{label}\n\n" if label else ""
        QMessageBox.warning(self, self._text["invalid"], message + self._text["invalid_hint"])
        if field_name in self.inputs:
            self.tabs.setCurrentIndex(0)
            self.inputs[field_name].setFocus()

    def accept(self) -> None:
        draft: WellPassport = deepcopy(self._draft)
        for field_name, editor in self.inputs.items():
            value = self._input_text(editor)
            if not value:
                draft.values.pop(field_name, None)
            elif field_name in NUMERIC_FIELDS:
                try:
                    draft.values[field_name] = float(value.replace(",", "."))
                except ValueError:
                    self._show_validation_error(field_name)
                    return
            else:
                draft.values[field_name] = value
        for language, inputs in self.localized_inputs.items():
            for field_name, editor in inputs.items():
                value = self._input_text(editor)
                values = draft.texts_i18n.setdefault(field_name, {})
                if value:
                    values[language] = value
                else:
                    values.pop(language, None)
                if not values:
                    draft.texts_i18n.pop(field_name, None)
        for role, combo in self.logo_inputs.items():
            selected = combo.currentData()
            if selected is None:
                draft.logo_refs.pop(role, None)
            else:
                draft.logo_refs[role] = selected
        try:
            self.controller.save(draft)
        except ValueError as exc:
            self._show_validation_error(getattr(exc, "field_name", ""))
            return
        super().accept()
