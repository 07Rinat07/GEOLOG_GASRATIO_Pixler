from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_catalog_controller import (
    StratigraphyCatalogController,
)
from geoworkbench.project.stratigraphy_controller import (
    STRATIGRAPHY_RANKS,
    STRATIGRAPHY_TEXT_ORIENTATIONS,
    STRATIGRAPHY_TEXT_POSITIONS,
    StratigraphyController,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class StratigraphyValues(TypedDict):
    top_depth: float
    bottom_depth: float
    rank: str
    code: str
    name: str
    color: str
    description: str
    text_orientation: str
    text_position: str


_TEXT_ORIENTATION_LABELS = {
    "horizontal": {
        AppLanguage.RU: "Горизонтально (0°)",
        AppLanguage.KK: "Көлденең (0°)",
        AppLanguage.EN: "Horizontal (0°)",
    },
    "vertical_bottom_to_top": {
        AppLanguage.RU: "Вертикально снизу вверх (90°)",
        AppLanguage.KK: "Төменнен жоғары тік (90°)",
        AppLanguage.EN: "Vertical bottom to top (90°)",
    },
    "vertical_top_to_bottom": {
        AppLanguage.RU: "Вертикально сверху вниз (90°)",
        AppLanguage.KK: "Жоғарыдан төмен тік (90°)",
        AppLanguage.EN: "Vertical top to bottom (90°)",
    },
}

_TEXT_POSITION_LABELS = {
    "top": {
        AppLanguage.RU: "Ближе к кровле",
        AppLanguage.KK: "Қабат төбесіне жақын",
        AppLanguage.EN: "Near interval top",
    },
    "center": {
        AppLanguage.RU: "По центру интервала",
        AppLanguage.KK: "Аралық ортасында",
        AppLanguage.EN: "Interval centre",
    },
    "bottom": {
        AppLanguage.RU: "Ближе к подошве",
        AppLanguage.KK: "Қабат табанына жақын",
        AppLanguage.EN: "Near interval bottom",
    },
}


def _populate_presentation_combo(
    combo: QComboBox,
    values: tuple[str, ...],
    labels: dict[str, dict[AppLanguage, str]],
    language: AppLanguage,
    selected: str,
) -> None:
    combo.clear()
    for value in values:
        combo.addItem(labels[value].get(language, labels[value][AppLanguage.RU]), value)
    index = combo.findData(selected)
    combo.setCurrentIndex(index if index >= 0 else 0)


def _combo_value(combo: QComboBox, fallback: str) -> str:
    value = combo.currentData()
    return value if isinstance(value, str) and value else fallback


class _CatalogMixin:
    language: AppLanguage
    catalog_controller: StratigraphyCatalogController
    catalog_input: QComboBox
    rank_input: QComboBox
    code_input: QLineEdit
    name_input: QLineEdit
    color_input: QLineEdit

    def _language_code(self) -> str:
        return self.language.value if isinstance(self.language, AppLanguage) else str(self.language)

    def _populate_catalog(self, selected_id: str | None = None) -> None:
        self.catalog_input.blockSignals(True)
        try:
            self.catalog_input.clear()
            self.catalog_input.addItem(self._catalog_none_text(), None)
            for item in self.catalog_controller.available():
                suffix = " *" if item.overridden else ""
                self.catalog_input.addItem(
                    f"{item.code} — {item.localized_name(self._language_code())}{suffix}",
                    item.unit_id,
                )
            if selected_id:
                index = self.catalog_input.findData(selected_id)
                if index >= 0:
                    self.catalog_input.setCurrentIndex(index)
        finally:
            self.catalog_input.blockSignals(False)

    def _catalog_none_text(self) -> str:
        return {
            AppLanguage.RU: "— Выберите из справочника —",
            AppLanguage.KK: "— Анықтамалықтан таңдаңыз —",
            AppLanguage.EN: "— Select from catalog —",
        }.get(self.language, "— Выберите из справочника —")

    def _apply_catalog_selection(self, _index: int = -1) -> None:
        unit_id = self.catalog_input.currentData()
        if not isinstance(unit_id, str) or not unit_id:
            return
        try:
            item = self.catalog_controller.get(unit_id)
        except KeyError:
            return
        self.rank_input.setCurrentText(item.rank)
        self.code_input.setText(item.code)
        self.name_input.setText(item.localized_name(self._language_code()))
        self.color_input.setText(item.color)

    def _choose_color(self) -> None:
        initial = QColor(self.color_input.text())
        color = QColorDialog.getColor(
            initial if initial.isValid() else QColor("#dbeafe"), self  # type: ignore[arg-type]
        )
        if color.isValid():
            self.color_input.setText(color.name())

    def _open_catalog(self) -> None:
        dialog = StratigraphyCatalogDialog(
            self.catalog_controller,
            self,  # type: ignore[arg-type]
            language=self.language,
        )
        dialog.exec()
        selected = self.catalog_input.currentData()
        self._populate_catalog(selected if isinstance(selected, str) else None)


class StratigraphyCatalogDialog(QDialog):
    """Editable project overlay over the bundled ICS-oriented reference catalog."""

    def __init__(
        self,
        controller: StratigraphyCatalogController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._text("Стратиграфический справочник", "Стратиграфиялық анықтамалық", "Stratigraphy catalog"))
        self.resize(1120, 650)
        root = QVBoxLayout(self)
        info = QLabel(
            self._text(
                "Заводские обозначения и цвета можно переопределить в проекте и позднее сбросить. Местные свиты, пачки и горизонты добавляются как пользовательские записи.",
                "Зауыттық белгілер мен түстерді жобада қайта анықтауға және кейін қалпына келтіруге болады. Жергілікті бірліктер пайдаланушы жазбалары ретінде қосылады.",
                "Factory labels and colours can be overridden per project and reset later. Add local formations, members and beds as custom records.",
            )
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.table = QTableWidget(0, 8)
        self.table.setObjectName("stratigraphy-catalog-table")
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                self._text("Ранг", "Ранг", "Rank"),
                self._text("Код", "Код", "Code"),
                "RU",
                "KK",
                "EN",
                self._text("Цвет", "Түс", "Colour"),
                self._text("Источник", "Дереккөз", "Source"),
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table, 1)

        form = QFormLayout()
        self.id_input = QLineEdit()
        self.rank_input = QComboBox()
        self.rank_input.setEditable(True)
        self.rank_input.addItems(STRATIGRAPHY_RANKS)
        self.code_input = QLineEdit()
        self.name_ru_input = QLineEdit()
        self.name_kk_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.parent_input = QLineEdit()
        self.color_input = QLineEdit("#dbeafe")
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_input)
        color_button = QPushButton(self._text("Цвет…", "Түс…", "Colour…"))
        color_button.clicked.connect(self._choose_color)
        color_row.addWidget(color_button)
        self.description_input = QLineEdit()
        for label, control in (
            ("ID", self.id_input),
            (self._text("Ранг", "Ранг", "Rank"), self.rank_input),
            (self._text("Код/аббревиатура", "Код/қысқарту", "Code/abbreviation"), self.code_input),
            (self._text("Название RU", "RU атауы", "Name RU"), self.name_ru_input),
            (self._text("Название KK", "KK атауы", "Name KK"), self.name_kk_input),
            (self._text("Название EN", "EN атауы", "Name EN"), self.name_en_input),
            (self._text("Родительский код", "Ата-ана коды", "Parent code"), self.parent_input),
        ):
            form.addRow(label, control)
        form.addRow(self._text("Цвет", "Түс", "Colour"), color_row)
        form.addRow(self._text("Описание", "Сипаттама", "Description"), self.description_input)
        root.addLayout(form)

        actions = QHBoxLayout()
        for caption, handler in (
            (self._text("Новая запись", "Жаңа жазба", "New record"), self._new),
            (self._text("Сохранить изменения", "Өзгерістерді сақтау", "Save changes"), self._save),
            (self._text("Сбросить заводскую", "Зауыттықты қалпына келтіру", "Reset factory"), self._reset),
            (self._text("Удалить пользовательскую", "Пайдаланушыны жою", "Delete custom"), self._remove),
        ):
            button = QPushButton(caption)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}.get(
            self.language, ru
        )

    def _refresh(self, selected_id: str | None = None) -> None:
        units = self.controller.available()
        self.table.setRowCount(len(units))
        selected_row = -1
        for row, item in enumerate(units):
            source = (
                self._text("Заводской, изменён", "Зауыттық, өзгертілген", "Factory, overridden")
                if item.overridden
                else self._text("Заводской", "Зауыттық", "Factory")
                if item.system
                else self._text("Пользовательский", "Пайдаланушы", "Custom")
            )
            values = (
                item.unit_id,
                item.rank,
                item.code,
                item.name_ru,
                item.name_kk,
                item.name_en,
                item.color,
                source,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, cell)
            if item.unit_id == selected_id:
                selected_row = row
        self.table.resizeColumnsToContents()
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        elif self.table.rowCount():
            self.table.selectRow(0)

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.text() if item is not None else None

    def _load_selected(self) -> None:
        unit_id = self._selected_id()
        if not unit_id:
            return
        try:
            item = self.controller.get(unit_id)
        except KeyError:
            return
        self.id_input.setText(item.unit_id)
        self.rank_input.setCurrentText(item.rank)
        self.code_input.setText(item.code)
        self.name_ru_input.setText(item.name_ru)
        self.name_kk_input.setText(item.name_kk)
        self.name_en_input.setText(item.name_en)
        self.parent_input.setText(item.parent_code)
        self.color_input.setText(item.color)
        self.description_input.setText(item.description)

    def _choose_color(self) -> None:
        initial = QColor(self.color_input.text())
        color = QColorDialog.getColor(initial if initial.isValid() else QColor("#dbeafe"), self)
        if color.isValid():
            self.color_input.setText(color.name())

    def _new(self) -> None:
        self.table.clearSelection()
        self.id_input.clear()
        self.rank_input.setCurrentText("Formation")
        self.code_input.clear()
        self.name_ru_input.clear()
        self.name_kk_input.clear()
        self.name_en_input.clear()
        self.parent_input.clear()
        self.color_input.setText("#dbeafe")
        self.description_input.clear()
        self.id_input.setFocus()

    def _save(self) -> None:
        unit_id = self.id_input.text().strip()
        if not unit_id:
            unit_id = self.controller.new_id(self.code_input.text() or self.name_en_input.text())
            self.id_input.setText(unit_id)
        try:
            saved = self.controller.save(
                unit_id,
                rank=self.rank_input.currentText(),
                code=self.code_input.text(),
                name_ru=self.name_ru_input.text(),
                name_kk=self.name_kk_input.text(),
                name_en=self.name_en_input.text(),
                color=self.color_input.text(),
                parent_code=self.parent_input.text(),
                description=self.description_input.text(),
            )
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._refresh(saved.unit_id)

    def _reset(self) -> None:
        unit_id = self._selected_id()
        if not unit_id:
            return
        try:
            item = self.controller.reset(unit_id)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._refresh(item.unit_id)

    def _remove(self) -> None:
        unit_id = self._selected_id()
        if not unit_id:
            return
        try:
            self.controller.remove(unit_id)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._refresh()


class StratigraphyIntervalDialog(QDialog, _CatalogMixin):
    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        catalog_controller: StratigraphyCatalogController | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog_controller = catalog_controller or StratigraphyCatalogController(
            ProjectSession()
        )
        self.language = language
        self.localizer = Localizer.create(language)
        self.setWindowTitle(
            f"{self.localizer.text('stratigraphy.title')} — {top_depth:g}–{bottom_depth:g} м"
        )
        self.top_input = self._depth_input(top_depth)
        self.bottom_input = self._depth_input(bottom_depth)
        self.catalog_input = QComboBox()
        self.catalog_input.setEditable(True)
        self.catalog_input.currentIndexChanged.connect(self._apply_catalog_selection)
        catalog_row = QHBoxLayout()
        catalog_row.addWidget(self.catalog_input, 1)
        catalog_button = QPushButton(
            {AppLanguage.RU: "Справочник…", AppLanguage.KK: "Анықтамалық…", AppLanguage.EN: "Catalog…"}.get(language, "Справочник…")
        )
        catalog_button.clicked.connect(self._open_catalog)
        catalog_row.addWidget(catalog_button)
        self.rank_input = QComboBox()
        self.rank_input.setEditable(True)
        self.rank_input.addItems(["", *STRATIGRAPHY_RANKS])
        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.color_input = QLineEdit("#dbeafe")
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_input)
        color_button = QPushButton("…")
        color_button.clicked.connect(self._choose_color)
        color_row.addWidget(color_button)
        self.description_input = QLineEdit()
        self.text_orientation_input = QComboBox()
        _populate_presentation_combo(
            self.text_orientation_input,
            STRATIGRAPHY_TEXT_ORIENTATIONS,
            _TEXT_ORIENTATION_LABELS,
            language,
            "horizontal",
        )
        self.text_position_input = QComboBox()
        _populate_presentation_combo(
            self.text_position_input,
            STRATIGRAPHY_TEXT_POSITIONS,
            _TEXT_POSITION_LABELS,
            language,
            "center",
        )
        layout = QFormLayout(self)
        layout.addRow(self.localizer.text("stratigraphy.top"), self.top_input)
        layout.addRow(self.localizer.text("stratigraphy.bottom"), self.bottom_input)
        layout.addRow(
            {AppLanguage.RU: "Шаблон", AppLanguage.KK: "Үлгі", AppLanguage.EN: "Template"}.get(language, "Шаблон"),
            catalog_row,
        )
        for key, control in (
            ("stratigraphy.rank", self.rank_input),
            ("stratigraphy.code", self.code_input),
            ("stratigraphy.name", self.name_input),
        ):
            layout.addRow(self.localizer.text(key), control)
        layout.addRow(self.localizer.text("stratigraphy.color"), color_row)
        layout.addRow(self.localizer.text("stratigraphy.description"), self.description_input)
        layout.addRow(
            self.localizer.text("stratigraphy.text_orientation"),
            self.text_orientation_input,
        )
        layout.addRow(
            self.localizer.text("stratigraphy.text_position"),
            self.text_position_input,
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._populate_catalog()

    @staticmethod
    def _depth_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        control.setValue(value)
        return control

    @property
    def top_depth(self) -> float:
        return self.top_input.value()

    @property
    def bottom_depth(self) -> float:
        return self.bottom_input.value()

    def set_text_presentation(self, orientation: str, position: str) -> None:
        orientation_index = self.text_orientation_input.findData(orientation)
        if orientation_index >= 0:
            self.text_orientation_input.setCurrentIndex(orientation_index)
        position_index = self.text_position_input.findData(position)
        if position_index >= 0:
            self.text_position_input.setCurrentIndex(position_index)

    def values(self) -> StratigraphyValues:
        return {
            "top_depth": self.top_input.value(),
            "bottom_depth": self.bottom_input.value(),
            "rank": self.rank_input.currentText(),
            "code": self.code_input.text(),
            "name": self.name_input.text(),
            "color": self.color_input.text(),
            "description": self.description_input.text(),
            "text_orientation": _combo_value(
                self.text_orientation_input, "horizontal"
            ),
            "text_position": _combo_value(self.text_position_input, "center"),
        }


class StratigraphyDialog(QDialog, _CatalogMixin):
    def __init__(
        self,
        controller: StratigraphyController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        catalog_controller: StratigraphyCatalogController | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.catalog_controller = catalog_controller or StratigraphyCatalogController(
            controller.session
        )
        self.language = language
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("stratigraphy.window_title"))
        self.resize(1100, 660)
        root = QVBoxLayout(self)
        info = QLabel(
            {
                AppLanguage.RU: "Выберите заводскую или пользовательскую единицу из справочника, затем задайте фактический интервал по скважине. Код, название и цвет можно изменить для требований месторождения.",
                AppLanguage.KK: "Анықтамалықтан бірлікті таңдап, ұңғымадағы нақты аралықты беріңіз. Кодты, атауды және түсті кен орны талаптарына сай өзгертуге болады.",
                AppLanguage.EN: "Choose a factory or project unit, then enter the actual well interval. Code, name and colour remain editable for field-specific requirements.",
            }.get(language, "")
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.table = QTableWidget(0, 9)
        self.table.setObjectName("stratigraphy-intervals-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("stratigraphy.top"),
                self._t("stratigraphy.bottom"),
                self._t("stratigraphy.rank"),
                self._t("stratigraphy.code"),
                self._t("stratigraphy.name"),
                self._t("stratigraphy.color"),
                self._t("stratigraphy.description"),
                self._t("stratigraphy.text_orientation"),
                self._t("stratigraphy.text_position"),
            ]
        )
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table, 1)

        form = QFormLayout()
        self.top_input = self._depth_input()
        self.bottom_input = self._depth_input()
        self.catalog_input = QComboBox()
        self.catalog_input.setEditable(True)
        self.catalog_input.currentIndexChanged.connect(self._apply_catalog_selection)
        catalog_row = QHBoxLayout()
        catalog_row.addWidget(self.catalog_input, 1)
        catalog_button = QPushButton(
            {AppLanguage.RU: "Редактировать справочник…", AppLanguage.KK: "Анықтамалықты өңдеу…", AppLanguage.EN: "Edit catalog…"}.get(language, "Редактировать справочник…")
        )
        catalog_button.clicked.connect(self._open_catalog)
        catalog_row.addWidget(catalog_button)
        self.rank_input = QComboBox()
        self.rank_input.setEditable(True)
        self.rank_input.addItems(["", *STRATIGRAPHY_RANKS])
        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.color_input = QLineEdit("#dbeafe")
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_input)
        color_button = QPushButton("…")
        color_button.clicked.connect(self._choose_color)
        color_row.addWidget(color_button)
        self.description_input = QLineEdit()
        self.text_orientation_input = QComboBox()
        _populate_presentation_combo(
            self.text_orientation_input,
            STRATIGRAPHY_TEXT_ORIENTATIONS,
            _TEXT_ORIENTATION_LABELS,
            language,
            "horizontal",
        )
        self.text_position_input = QComboBox()
        _populate_presentation_combo(
            self.text_position_input,
            STRATIGRAPHY_TEXT_POSITIONS,
            _TEXT_POSITION_LABELS,
            language,
            "center",
        )
        form.addRow(
            {AppLanguage.RU: "Справочник", AppLanguage.KK: "Анықтамалық", AppLanguage.EN: "Catalog"}.get(language, "Справочник"),
            catalog_row,
        )
        for label, control in (
            (self._t("stratigraphy.top"), self.top_input),
            (self._t("stratigraphy.bottom"), self.bottom_input),
            (self._t("stratigraphy.rank"), self.rank_input),
            (self._t("stratigraphy.code"), self.code_input),
            (self._t("stratigraphy.name"), self.name_input),
        ):
            form.addRow(label, control)
        form.addRow(self._t("stratigraphy.color"), color_row)
        form.addRow(self._t("stratigraphy.description"), self.description_input)
        form.addRow(
            self._t("stratigraphy.text_orientation"), self.text_orientation_input
        )
        form.addRow(self._t("stratigraphy.text_position"), self.text_position_input)
        root.addLayout(form)

        actions = QHBoxLayout()
        for object_name, title, handler in (
            ("stratigraphy-add-button", self._t("common.add"), self._add),
            ("stratigraphy-update-button", self._t("common.update"), self._update),
            ("stratigraphy-remove-button", self._t("common.remove"), self._remove),
        ):
            button = QPushButton(title)
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._populate_catalog()
        self._refresh()

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    @staticmethod
    def _depth_input() -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        return control

    def _refresh(self) -> None:
        intervals = self.controller.available()
        self.table.setRowCount(len(intervals))
        for row, interval in enumerate(intervals):
            values = (
                f"{interval.top_depth:g}",
                f"{interval.bottom_depth:g}",
                interval.rank or "",
                interval.code,
                interval.name or "",
                interval.color,
                interval.description or "",
                _TEXT_ORIENTATION_LABELS[interval.text_orientation].get(
                    self.language, interval.text_orientation
                ),
                _TEXT_POSITION_LABELS[interval.text_position].get(
                    self.language, interval.text_position
                ),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, interval.interval_id)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _load_selected(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            return
        try:
            interval = self.controller.get(interval_id)
        except (KeyError, RuntimeError):
            return
        self.top_input.setValue(interval.top_depth)
        self.bottom_input.setValue(interval.bottom_depth)
        self.rank_input.setCurrentText(interval.rank or "")
        self.code_input.setText(interval.code)
        self.name_input.setText(interval.name or "")
        self.color_input.setText(interval.color)
        self.description_input.setText(interval.description or "")
        orientation_index = self.text_orientation_input.findData(interval.text_orientation)
        if orientation_index >= 0:
            self.text_orientation_input.setCurrentIndex(orientation_index)
        position_index = self.text_position_input.findData(interval.text_position)
        if position_index >= 0:
            self.text_position_input.setCurrentIndex(position_index)

    def _values(self) -> StratigraphyValues:
        return {
            "top_depth": self.top_input.value(),
            "bottom_depth": self.bottom_input.value(),
            "rank": self.rank_input.currentText(),
            "code": self.code_input.text(),
            "name": self.name_input.text(),
            "color": self.color_input.text(),
            "description": self.description_input.text(),
            "text_orientation": _combo_value(
                self.text_orientation_input, "horizontal"
            ),
            "text_position": _combo_value(self.text_position_input, "center"),
        }

    def _add(self) -> None:
        if self._run(lambda: self.controller.add(**self._values())):
            self.code_input.clear()
            self.name_input.clear()
            self.description_input.clear()

    def _update(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(
                self, self._t("stratigraphy.title"), self._t("stratigraphy.select_interval")
            )
            return
        self._run(lambda: self.controller.update(interval_id, **self._values()))

    def _remove(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(
                self, self._t("stratigraphy.title"), self._t("stratigraphy.select_interval")
            )
            return
        self._run(lambda: self.controller.remove(interval_id))

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("stratigraphy.title"), str(exc))
            return False
        self._refresh()
        return True
