from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.catalogs.description_templates import load_rock_description_templates
from geoworkbench.catalogs.lithotypes import load_lithotype_catalog
from geoworkbench.domain.localized_content import (
    SUPPORTED_CONTENT_LANGUAGES,
    localized_text,
)
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES, Localizer
from geoworkbench.ui.window_geometry import fit_window_to_screen


_LITHOTYPE_TEMPLATE_ALIASES = {
    "claystone": "argillite",
    "gravelite": "gravelstone",
}
_TEMPLATE_ID_ROLE = 257
_SOURCE_LANGUAGE_LABELS = {
    AppLanguage.RU: "Язык оригинала",
    AppLanguage.KK: "Түпнұсқа тілі",
    AppLanguage.EN: "Source language",
}
_SOURCE_LANGUAGE_UNSET = {
    AppLanguage.RU: "— не задан —",
    AppLanguage.KK: "— көрсетілмеген —",
    AppLanguage.EN: "— not set —",
}


class LithologyDialog(QDialog):
    def __init__(
        self,
        controller: LithologyController,
        parent: QWidget | None = None,
        *,
        catalog: tuple[CatalogLithotype, ...] | None = None,
        description_templates: tuple[tuple[str, str], ...] = (),
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.localizer = Localizer.create(language)
        self.controller = controller
        self.catalog = catalog if catalog is not None else load_lithotype_catalog()
        self._custom_description_templates = tuple(description_templates)
        self._description_template_catalog = load_rock_description_templates()
        self.setWindowTitle(self._t("lithology.window_title"))
        root = QVBoxLayout(self)
        self.content_scroll = QScrollArea(self)
        self.content_scroll.setObjectName("lithology-content-scroll")
        self.content_scroll.setWidgetResizable(True)
        content = QWidget(self.content_scroll)
        content_layout = QVBoxLayout(content)
        self.content_scroll.setWidget(content)
        root.addWidget(self.content_scroll, 1)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("lithology-intervals-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("lithology.top"),
                self._t("lithology.bottom"),
                self._t("lithology.lithotype"),
                self._t("lithology.description"),
            ]
        )
        self.table.itemSelectionChanged.connect(self._load_selected)
        content_layout.addWidget(self.table)

        form = QFormLayout()
        self.top_input = self._depth_input()
        self.bottom_input = self._depth_input()
        self.lithotype_input = QComboBox()
        self.lithotype_input.setEditable(True)
        for item in self.catalog:
            if language is AppLanguage.KK:
                name = item.name_kk or item.name_ru
            elif language is AppLanguage.EN:
                name = item.name_en
            else:
                name = item.name_ru
            self.lithotype_input.addItem(f"{name} ({item.lithotype_id})", item.lithotype_id)
        self.description_language_tabs = QTabWidget()
        self.description_language_tabs.setObjectName("lithology-description-language-tabs")
        self.description_inputs: dict[str, QLineEdit] = {}
        self._initial_description_i18n: dict[str, str] = {}
        self._description_dirty_languages: set[str] = set()
        for content_language in AppLanguage:
            language_code = content_language.value
            editor = QLineEdit()
            editor.setObjectName(f"lithology-description-{language_code}")
            editor.textEdited.connect(
                lambda _text, language_code=language_code: self._description_edited(language_code)
            )
            self.description_inputs[language_code] = editor
            self.description_language_tabs.addTab(editor, LANGUAGE_NAMES[content_language])
        self.description_language_tabs.setCurrentIndex(tuple(AppLanguage).index(language))
        self.description_input = self.description_inputs[language.value]

        self.source_language_input = QComboBox()
        self.source_language_input.setObjectName("lithology-source-language")
        self.source_language_input.addItem(_SOURCE_LANGUAGE_UNSET[language], None)
        for source_language in AppLanguage:
            self.source_language_input.addItem(
                LANGUAGE_NAMES[source_language], source_language.value
            )

        self.template_language_input = QComboBox()
        self.template_language_input.setObjectName("description-template-language")
        for template_language in AppLanguage:
            self.template_language_input.addItem(
                LANGUAGE_NAMES[template_language], template_language.value
            )
        self.template_language_input.setCurrentIndex(
            self.template_language_input.findData(language.value)
        )
        self.template_input = QComboBox()
        self.template_input.setObjectName("description-template-selector")
        self.template_formula = QLabel()
        self.template_formula.setObjectName("description-template-formula")
        self.template_formula.setWordWrap(True)
        self.template_formula.setStyleSheet("color:#475569; font-size:11px;")
        self.template_warning = QLabel()
        self.template_warning.setObjectName("description-template-warning")
        self.template_warning.setWordWrap(True)
        self.template_warning.setStyleSheet(
            "background:#fff7ed; color:#9a3412; border:1px solid #fdba74; "
            "border-radius:4px; padding:4px 6px;"
        )
        self.template_language_input.currentIndexChanged.connect(self._template_language_changed)
        self.template_input.currentIndexChanged.connect(self._insert_template)
        self.lithotype_input.currentIndexChanged.connect(self._suggest_description_template)
        self._refresh_description_templates()
        form.addRow(self._t("lithology.top"), self.top_input)
        form.addRow(self._t("lithology.bottom"), self.bottom_input)
        form.addRow(self._t("lithology.lithotype_id"), self.lithotype_input)
        form.addRow(self._t("lithology.description"), self.description_language_tabs)
        form.addRow(_SOURCE_LANGUAGE_LABELS[language], self.source_language_input)
        form.addRow(self._t("lithology.template_language"), self.template_language_input)
        form.addRow(self._t("lithology.description_template"), self.template_input)
        form.addRow("", self.template_formula)
        form.addRow("", self.template_warning)
        content_layout.addLayout(form)

        actions = QHBoxLayout()
        for object_name, title, handler in (
            ("lithology-add-button", self._t("common.add"), self._add),
            ("lithology-update-button", self._t("common.update"), self._update),
            ("lithology-remove-button", self._t("common.remove"), self._remove),
        ):
            button = QPushButton(title)
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            actions.addWidget(button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        fit_window_to_screen(
            self,
            preferred=QSize(820, 520),
            minimum=QSize(520, 360),
        )
        self._refresh()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @staticmethod
    def _depth_input() -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(-100_000.0, 100_000.0)
        field.setDecimals(3)
        return field

    def _refresh(self) -> None:
        intervals = self.controller.available()
        self.table.setRowCount(len(intervals))
        for row, interval in enumerate(intervals):
            top_item = QTableWidgetItem(f"{interval.top_depth:g}")
            top_item.setData(256, interval.interval_id)
            self.table.setItem(row, 0, top_item)
            self.table.setItem(row, 1, QTableWidgetItem(f"{interval.bottom_depth:g}"))
            self.table.setItem(row, 2, QTableWidgetItem(interval.lithotype_id))
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(
                    localized_text(
                        interval.description_i18n,
                        self.language,
                        legacy=interval.description,
                    )
                ),
            )
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(256)) if item is not None else None

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        items = [self.table.item(row, column) for column in range(4)] if row >= 0 else []
        if len(items) != 4 or any(item is None for item in items):
            return
        top_item, bottom_item, lithotype_item, description_item = items
        assert top_item is not None
        assert bottom_item is not None
        assert lithotype_item is not None
        assert description_item is not None
        self.top_input.setValue(float(top_item.text()))
        self.bottom_input.setValue(float(bottom_item.text()))
        index = self.lithotype_input.findData(lithotype_item.text())
        if index >= 0:
            self.lithotype_input.setCurrentIndex(index)
        else:
            self.lithotype_input.setEditText(lithotype_item.text())
        interval_id = self._selected_id()
        if interval_id is None:
            return
        interval = self.controller.get(interval_id)
        self._initial_description_i18n = dict(interval.description_i18n)
        self._description_dirty_languages.clear()
        for language_code, editor in self.description_inputs.items():
            text = interval.description_i18n.get(language_code, "")
            if language_code == "ru" and not text:
                text = interval.description or ""
            editor.setText(text)
        self._set_source_language(self.controller.source_language(interval_id))

    def _add(self) -> None:
        if self._run(
            lambda: self.controller.add(
                self.top_input.value(),
                self.bottom_input.value(),
                self._lithotype_id(),
                description_i18n=self._description_values(),
                source_language=self._source_language(),
            )
        ):
            for editor in self.description_inputs.values():
                editor.clear()
            self._initial_description_i18n.clear()
            self._description_dirty_languages.clear()
            self._set_source_language(None)

    def _update(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(
                self, self._t("lithology.title"), self._t("lithology.select_interval")
            )
            return
        self._run(
            lambda: self.controller.update(
                interval_id,
                top_depth=self.top_input.value(),
                bottom_depth=self.bottom_input.value(),
                lithotype_id=self._lithotype_id(),
                description_i18n=self._description_values(),
                source_language=self._source_language(),
            )
        )

    def _remove(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(
                self, self._t("lithology.title"), self._t("lithology.select_interval")
            )
            return
        self._run(lambda: self.controller.remove(interval_id))

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("lithology.title"), str(exc))
            return False
        self._refresh()
        return True

    def _lithotype_id(self) -> str:
        data = self.lithotype_input.currentData()
        return str(data) if data is not None else self.lithotype_input.currentText().strip()

    def _description_edited(self, language_code: str) -> None:
        self._description_dirty_languages.add(language_code)
        if self._source_language() is None:
            self._set_source_language(language_code)

    def _source_language(self) -> str | None:
        value = self.source_language_input.currentData()
        return str(value) if isinstance(value, str) and value else None

    def _set_source_language(self, language_code: str | None) -> None:
        index = self.source_language_input.findData(language_code)
        self.source_language_input.setCurrentIndex(index if index >= 0 else 0)

    def _ensure_source_language(self, language_code: str) -> None:
        if self._source_language() is None:
            self._set_source_language(language_code)

    def _insert_template(self, index: int) -> None:
        template_id = self.template_input.itemData(index, _TEMPLATE_ID_ROLE)
        template = next(
            (
                item
                for item in self._description_template_catalog.templates
                if item.template_id == template_id
            ),
            None,
        )
        if template is not None:
            self._ensure_source_language(self._template_language().value)
            for language_code in SUPPORTED_CONTENT_LANGUAGES:
                _name, text = template.localized(language_code)
                self.description_inputs[language_code].setText(text)
                self._description_dirty_languages.add(language_code)
            return
        text = self.template_input.itemData(index)
        if isinstance(text, str):
            language_code = self._template_language().value
            self._ensure_source_language(language_code)
            self.description_inputs[language_code].setText(text)
            self._description_dirty_languages.add(language_code)

    def _template_language_changed(self, _index: int) -> None:
        language = self._template_language()
        self.description_input = self.description_inputs[language.value]
        self.description_language_tabs.setCurrentIndex(tuple(AppLanguage).index(language))
        self._refresh_description_templates()

    def _description_values(self) -> dict[str, str]:
        descriptions = dict(self._initial_description_i18n)
        for language_code in self._description_dirty_languages:
            text = self.description_inputs[language_code].text().strip()
            if text:
                descriptions[language_code] = text
            else:
                descriptions.pop(language_code, None)
        return descriptions

    def _refresh_description_templates(self) -> None:
        language = self._template_language()
        self.template_input.blockSignals(True)
        self.template_input.clear()
        self.template_input.addItem(self._t("lithology.select_template"), None)
        for template in self._description_template_catalog.templates:
            name, text = template.localized(language.value)
            self.template_input.addItem(name, text)
            self.template_input.setItemData(
                self.template_input.count() - 1,
                template.template_id,
                _TEMPLATE_ID_ROLE,
            )
        if self._custom_description_templates:
            self.template_input.insertSeparator(self.template_input.count())
            for name, text in self._custom_description_templates:
                self.template_input.addItem(name, text)
        self.template_input.setCurrentIndex(0)
        self.template_input.blockSignals(False)

        formula, warning = self._description_template_catalog.localized_guidance(language.value)
        self.template_formula.setText(self._t("lithology.template_formula", formula=formula))
        self.template_warning.setText(self._t("lithology.template_warning", warning=warning))
        self._suggest_description_template(self.lithotype_input.currentIndex())

    def _template_language(self) -> AppLanguage:
        try:
            return AppLanguage(str(self.template_language_input.currentData()))
        except ValueError:
            return self.language

    def _suggest_description_template(self, _index: int) -> None:
        lithotype_id = self._lithotype_id()
        template_id = _LITHOTYPE_TEMPLATE_ALIASES.get(lithotype_id, lithotype_id)
        for index in range(1, self.template_input.count()):
            if self.template_input.itemData(index, _TEMPLATE_ID_ROLE) == template_id:
                self.template_input.setCurrentIndex(index)
                return
