from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.lithology_patterns import lithology_brush, supported_pattern_keys
from geoworkbench.ui.dunham_reference_widget import DunhamClassificationReference
from geoworkbench.ui.lithotype_visuals import lithotype_icon, pattern_icon


class LithologyPatternPreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = "#c9a66b"
        self._pattern_key = "solid"
        self.setMinimumHeight(64)
        self.setObjectName("lithology-pattern-preview")

    def set_pattern(self, color: str, pattern_key: str) -> None:
        self._color = color
        self._pattern_key = pattern_key
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#404040"), 1))
        painter.setBrush(lithology_brush(self._color, self._pattern_key))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.end()
        super().paintEvent(event)


class LithotypeCatalogDialog(QDialog):
    def __init__(
        self,
        controller: LithotypeCatalogController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.language = language
        self.controller = controller
        self.setWindowTitle(self._t("catalog.window_title"))
        self.resize(1100, 620)

        root = QVBoxLayout(self)
        self.sections = QTabWidget(self)
        self.sections.setObjectName("lithotype-reference-tabs")
        self.sections.setDocumentMode(True)
        root.addWidget(self.sections, 1)
        self._build_las_codes_page()
        catalog_page = QWidget(self.sections)
        catalog_page.setObjectName("lithotype-catalog-section")
        catalog_root = QVBoxLayout(catalog_page)
        self.sections.addTab(
            catalog_page,
            {
                AppLanguage.RU: "Литотипы",
                AppLanguage.KK: "Литотиптер",
                AppLanguage.EN: "Lithotypes",
            }[language],
        )
        info = QLabel(
            {
                AppLanguage.RU: (
                    "Стандартный набор включает встроенные обозначения и 117 переданных "
                    "литологических рисунков. Заводскую запись можно изменить: программа "
                    "создаст проектное переопределение, которое затем можно сбросить."
                ),
                AppLanguage.KK: (
                    "Стандартты жинақта кірістірілген белгілер және берілген 117 литологиялық "
                    "сурет бар. Зауыттық жазбаны өзгерткенде жобалық қайта анықтау жасалады."
                ),
                AppLanguage.EN: (
                    "The standard set contains the built-in symbols and all 117 supplied "
                    "lithology bitmaps. Editing a factory row creates a project override that "
                    "can later be reset."
                ),
            }[language]
        )
        info.setWordWrap(True)
        catalog_root.addWidget(info)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            {
                AppLanguage.RU: "Поиск по коду, названию, ID, псевдониму или рисунку...",
                AppLanguage.KK: "Код, атау, ID, бүркеншік ат немесе сурет бойынша іздеу...",
                AppLanguage.EN: "Search by code, name, ID, alias or pattern...",
            }[language]
        )
        self.search_input.textChanged.connect(self._apply_filter)
        catalog_root.addWidget(self.search_input)
        self.table = QTableWidget(0, 9)
        self.table.setObjectName("lithotype-catalog-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("catalog.source"),
                self._t("catalog.code"),
                self._t("catalog.id"),
                self._t("catalog.name_ru"),
                self._t("catalog.name_kk"),
                self._t("catalog.name_en"),
                self._t("catalog.category"),
                self._t("catalog.color"),
                self._t("catalog.pattern"),
            ]
        )
        self.table.itemSelectionChanged.connect(self._load_selected)
        catalog_root.addWidget(self.table)

        form = QFormLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText(self._t("catalog.id_example"))
        self.code_input = QLineEdit()
        self.name_ru_input = QLineEdit()
        self.name_kk_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.category_input = QLineEdit()
        self.color_input = QLineEdit("#c9a66b")
        self.pattern_input = QComboBox()
        self.pattern_input.setEditable(True)
        for pattern_key in supported_pattern_keys():
            self.pattern_input.addItem(
                pattern_icon("#f8fafc", pattern_key),
                pattern_key,
                pattern_key,
            )
        for label, field in (
            (self._t("catalog.id"), self.id_input),
            (self._t("catalog.code"), self.code_input),
            (self._t("catalog.name_ru"), self.name_ru_input),
            (self._t("catalog.name_kk"), self.name_kk_input),
            (self._t("catalog.name_en"), self.name_en_input),
            (self._t("catalog.category"), self.category_input),
            (self._t("catalog.pattern_key"), self.pattern_input),
        ):
            form.addRow(label, field)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.color_input)
        self.color_button = QPushButton(self._t("common.choose"))
        self.color_button.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_button)
        form.addRow(self._t("catalog.color_hex"), color_row)
        self.pattern_preview = LithologyPatternPreview()
        form.addRow(self._t("catalog.preview"), self.pattern_preview)
        self.color_input.textChanged.connect(self._update_preview)
        self.pattern_input.currentTextChanged.connect(self._update_preview)
        catalog_root.addLayout(form)

        actions = QHBoxLayout()
        for object_name, title, handler in (
            ("catalog-new-button", self._t("catalog.new"), self._clear_form),
            ("catalog-add-button", self._t("common.add"), self._add),
            ("catalog-update-button", self._t("common.update"), self._update),
            (
                "catalog-remove-button",
                {
                    AppLanguage.RU: "Сбросить / удалить",
                    AppLanguage.KK: "Қалпына келтіру / жою",
                    AppLanguage.EN: "Reset / delete",
                }[language],
                self._remove,
            ),
        ):
            button = QPushButton(title)
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            actions.addWidget(button)
        catalog_root.addLayout(actions)

        self.dunham_reference = DunhamClassificationReference(
            self.sections,
            language=language,
        )
        self.sections.addTab(
            self.dunham_reference,
            {
                AppLanguage.RU: "Классификация Данэма",
                AppLanguage.KK: "Данэм жіктемесі",
                AppLanguage.EN: "Dunham classification",
            }[language],
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()
        self._update_preview()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _las_text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[self.language]

    def _build_las_codes_page(self) -> None:
        page = QWidget(self.sections)
        layout = QVBoxLayout(page)
        note = QLabel(self._las_text(
            "Соответствия кодов действуют в текущем проекте. Неопознанные породы показаны нейтрально. "
            "Выберите подтверждённый литотип; его название, цвет и рисунок будут использованы на экране и в PDF. "
            "Новые литотипы добавляются в основном каталоге. Исходный LAS и ручные интервалы не изменяются.",
            "Код сәйкестіктері ағымдағы жобада қолданылады. Анықталмаған жыныстар бейтарап көрсетіледі. "
            "Расталған литотипті таңдаңыз: атауы, түсі және өрнегі экранда және PDF ішінде қолданылады. "
            "Жаңа литотиптер негізгі каталогта қосылады. Бастапқы LAS және қолмен енгізілген аралықтар өзгермейді.",
            "Code mappings apply within this project. Unidentified rocks use neutral symbols. "
            "Select a confirmed lithotype for its name, colour and pattern in the view and PDF. "
            "Add new lithotypes in the main catalog. Source LAS and manual intervals are unchanged.",
        ))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.las_codes_table = QTableWidget(0, 3)
        self.las_codes_table.setObjectName("las-rock-code-mappings")
        self.las_codes_table.setHorizontalHeaderLabels([
            self._las_text("Код LAS", "LAS коды", "LAS code"),
            self._las_text("Литотип из единого каталога", "Бірыңғай каталогтағы литотип", "Lithotype from unified catalog"),
            self._las_text("Действие", "Әрекет", "Action"),
        ])
        header = self.las_codes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.las_codes_table)
        self.las_code_input = QLineEdit()
        self.las_code_input.setPlaceholderText(self._las_text("Добавить код (1–999999)", "Код қосу (1–999999)", "Add code (1–999999)"))
        layout.addWidget(self.las_code_input)
        buttons = QHBoxLayout()
        for texts, action in (
            (("Прочитать коды текущего LAS", "Ағымдағы LAS кодтарын оқу", "Read current LAS codes"), self._read_las_codes),
            (("Добавить код", "Код қосу", "Add code"), self._add_las_code),
            (("Применить соответствия", "Сәйкестіктерді қолдану", "Apply mappings"), self._apply_las_codes),
            (("Импорт справочника", "Справочникті импорттау", "Import dictionary"), self._import_dictionary),
            (("Экспорт справочника", "Справочникті экспорттау", "Export dictionary"), self._export_dictionary),
        ):
            button = QPushButton(self._las_text(*texts))
            button.clicked.connect(action)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.sections.addTab(page, self._las_text("Коды пород LAS", "LAS жыныс кодтары", "LAS rock codes"))
        self._refresh_las_codes()

    def _refresh_las_codes(self) -> None:
        records = [r for r in self.controller.available() if r.lithotype_id.startswith("las-code-")]
        catalog = self.controller.available()
        self.las_codes_table.setRowCount(len(records))
        for row, record in enumerate(records):
            item = QTableWidgetItem(record.lithotype_id.removeprefix("las-code-"))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.las_codes_table.setItem(row, 0, item)
            choices = QComboBox()
            for option in catalog:
                choices.addItem(f"{option.code} — {option.localized_name(str(self.language))}", option.lithotype_id)
            choices.setCurrentIndex(choices.findData(record.lithotype_id))
            self.las_codes_table.setCellWidget(row, 1, choices)
            reset = QPushButton(self._las_text("Сбросить", "Қалпына келтіру", "Reset"))
            reset.clicked.connect(lambda _checked=False, code=int(item.text()): self._reset_las_code(code))
            self.las_codes_table.setCellWidget(row, 2, reset)

    def _read_las_codes(self) -> None:
        from geoworkbench.services.las_geology import import_las_geology

        result = import_las_geology(self.controller.session)
        self._refresh_las_codes()
        self._refresh()
        if result.invalid_composition_rows:
            QMessageBox.warning(self, self.windowTitle(), self._las_text(
                f"Пропущено строк с некорректным составом: {result.invalid_composition_rows}",
                f"Қате құрамы бар өткізіп жіберілген жолдар: {result.invalid_composition_rows}",
                f"Rows with invalid composition skipped: {result.invalid_composition_rows}",
            ))

    def _import_dictionary(self) -> None:
        from geoworkbench.services.rock_code_dictionary import RockCodeDictionaryError

        path, _ = QFileDialog.getOpenFileName(
            self,
            self._las_text("Импорт справочника кодов", "Кодтар справочнигін импорттау", "Import rock-code dictionary"),
            "",
            "Rock code dictionary (*.rock-codes.json *.json)",
        )
        if not path:
            return
        try:
            _loaded, created, updated = self.controller.import_rock_dictionary(Path(path))
        except (OSError, RockCodeDictionaryError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._refresh_las_codes()
        self._refresh()
        QMessageBox.information(
            self,
            self.windowTitle(),
            self._las_text(
                f"Импортировано записей: {created + updated} (новых: {created}, обновлено: {updated})",
                f"Импортталған жазбалар: {created + updated} (жаңа: {created}, жаңартылған: {updated})",
                f"Imported entries: {created + updated} (new: {created}, updated: {updated})",
            ),
        )

    def _export_dictionary(self) -> None:
        from geoworkbench.services.rock_code_dictionary import RockCodeDictionaryError

        path, _ = QFileDialog.getSaveFileName(
            self,
            self._las_text("Экспорт справочника кодов", "Кодтар справочнигін экспорттау", "Export rock-code dictionary"),
            "rock-codes.rock-codes.json",
            "Rock code dictionary (*.rock-codes.json *.json)",
        )
        if not path:
            return
        try:
            self.controller.export_current_rock_dictionary(Path(path))
        except (OSError, RockCodeDictionaryError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        QMessageBox.information(
            self,
            self.windowTitle(),
            self._las_text(
                "Справочник экспортирован",
                "Справочник экспортталды",
                "Dictionary exported",
            ),
        )
    def _add_las_code(self) -> None:
        from geoworkbench.services.las_geology import las_code_id, unmapped_las_lithotype

        try:
            code = int(self.las_code_input.text().strip())
            identity = las_code_id(code)
        except ValueError:
            QMessageBox.warning(self, self.windowTitle(), self._las_text("Введите целый код 1–999999", "1–999999 бүтін кодын енгізіңіз", "Enter an integer code 1–999999"))
            return
        project = self.controller.session.project
        if identity not in project.lithotypes:
            project.lithotypes[identity] = unmapped_las_lithotype(code)
            self.controller.session.dirty = True
        self._refresh_las_codes()
        self._refresh()

    def _reset_las_code(self, code: int) -> None:
        self.controller.reset_las_code(code)
        self._refresh_las_codes()
        self._refresh()

    def _apply_las_codes(self) -> None:
        for row in range(self.las_codes_table.rowCount()):
            item = self.las_codes_table.item(row, 0)
            choices = self.las_codes_table.cellWidget(row, 1)
            if item is not None and isinstance(choices, QComboBox):
                code = int(item.text())
                selected = str(choices.currentData())
                if selected != f"las-code-{code}":
                    self.controller.adapt_las_code(code, selected)
        self._refresh_las_codes()
        self._refresh()

    def _refresh(self) -> None:
        records = self.controller.available()
        self._records = records
        self._record_by_id = {record.lithotype_id: record for record in records}
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            if record.overridden:
                source = {
                    AppLanguage.RU: "Переопределён в проекте",
                    AppLanguage.KK: "Жобада қайта анықталған",
                    AppLanguage.EN: "Project override",
                }[self.language]
            elif record.source == "factory":
                source = {
                    AppLanguage.RU: "Стандартный рисунок",
                    AppLanguage.KK: "Стандартты сурет",
                    AppLanguage.EN: "Standard bitmap",
                }[self.language]
            elif record.system:
                source = self._t("catalog.system")
            else:
                source = self._t("catalog.project")
            values = (
                source,
                record.code,
                record.lithotype_id,
                record.name_ru,
                record.name_kk,
                record.name_en,
                record.category,
                record.color,
                record.pattern_key,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, record.lithotype_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, record.system)
                item.setData(Qt.ItemDataRole.UserRole + 2, record.overridden)
                if column == 0:
                    item.setIcon(lithotype_icon(record))
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 30)
        self.table.resizeColumnsToContents()
        self._apply_filter(self.search_input.text())

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        values = [self.table.item(row, column) for column in range(9)]
        if any(item is None for item in values):
            return
        source, code, lithotype_id, name_ru, name_kk, name_en, category, color, pattern = (
            cast(QTableWidgetItem, item) for item in values
        )
        self.id_input.setText(lithotype_id.text())
        self.id_input.setReadOnly(True)
        self.code_input.setText(code.text())
        self.name_ru_input.setText(name_ru.text())
        self.name_kk_input.setText(name_kk.text())
        self.name_en_input.setText(name_en.text())
        self.category_input.setText(category.text())
        self.color_input.setText(color.text())
        self.pattern_input.setCurrentText(pattern.text())

    def _clear_form(self) -> None:
        self.table.clearSelection()
        self.id_input.setReadOnly(False)
        for field in (
            self.id_input,
            self.code_input,
            self.name_ru_input,
            self.name_kk_input,
            self.name_en_input,
            self.category_input,
        ):
            field.clear()
        self.pattern_input.setCurrentText("solid")
        self.color_input.setText("#c9a66b")
        self.id_input.setFocus()

    def _values(self) -> tuple[str, str, str, str, str, str, str, str]:
        return (
            self.id_input.text(),
            self.code_input.text(),
            self.name_ru_input.text(),
            self.name_en_input.text(),
            self.category_input.text(),
            self.color_input.text(),
            self.pattern_input.currentText(),
            self.name_kk_input.text(),
        )

    def _choose_color(self) -> None:
        initial = QColor(self.color_input.text())
        selected = QColorDialog.getColor(initial, self, self._t("catalog.color_title"))
        if selected.isValid():
            self.color_input.setText(selected.name())

    def _update_preview(self) -> None:
        self.pattern_preview.set_pattern(self.color_input.text(), self.pattern_input.currentText())

    def _add(self) -> None:
        self._run(lambda: self.controller.add(*self._values()))

    def _update(self) -> None:
        lithotype_id = self._selected_id()
        if lithotype_id is None:
            QMessageBox.information(
                self, self._t("catalog.title"), self._t("catalog.select_project")
            )
            return
        _, code, name_ru, name_en, category, color, pattern, name_kk = self._values()
        self._run(
            lambda: self.controller.update(
                lithotype_id,
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                category=category,
                color=color,
                pattern_key=pattern,
                name_kk=name_kk,
            )
        )

    def _remove(self) -> None:
        lithotype_id = self._selected_id()
        if lithotype_id is None:
            QMessageBox.information(
                self, self._t("catalog.title"), self._t("catalog.select_project")
            )
            return
        self._run(lambda: self.controller.remove(lithotype_id))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _apply_filter(self, query: str) -> None:
        needle = query.strip().casefold()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            lithotype_id = str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""
            record = getattr(self, "_record_by_id", {}).get(lithotype_id)
            if record is None or not needle:
                self.table.setRowHidden(row, False)
                continue
            values = (
                record.lithotype_id,
                record.code,
                record.name_ru,
                record.name_kk,
                record.name_en,
                record.category,
                record.pattern_key,
                *record.aliases,
            )
            self.table.setRowHidden(
                row,
                not any(needle in str(value).casefold() for value in values),
            )

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("catalog.title"), str(exc))
            return False
        self._refresh()
        return True
