from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.catalogs.sensors import SensorCatalog, default_sensor_catalog
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.mnemonic_registry import UserMnemonicRegistry, UserMnemonicRule


_CATEGORIES = ("gas", "drilling", "mud", "petrophysics", "dexp", "other")
_FAMILIES = (
    "gas",
    "rop",
    "rotary_speed",
    "wob",
    "torque",
    "pressure",
    "hookload",
    "flow",
    "drilling_depth",
    "mud_density",
    "temperature",
    "pit_volume",
    "conductivity",
    "chlorides",
    "gamma_ray",
    "sp",
    "caliper",
    "bulk_density",
    "neutron",
    "sonic",
    "resistivity",
    "pef",
    "dexp",
    "other",
)


class MnemonicRuleDialog(QDialog):
    def __init__(self, rule: UserMnemonicRule | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rule_id = rule.rule_id if rule else str(uuid4())
        self.setWindowTitle("Правило мнемоники")
        form = QFormLayout(self)
        self.foreign = QLineEdit(rule.foreign_mnemonic if rule else "")
        self.canonical = QLineEdit(rule.canonical_mnemonic if rule else "")
        self.name = QLineEdit(rule.name_ru if rule else "")
        self.unit = QLineEdit(rule.unit if rule else "")
        self.aliases = QLineEdit(", ".join(rule.aliases) if rule else "")
        self.category = QComboBox()
        self.category.addItems(_CATEGORIES)
        self.family = QComboBox()
        self.family.addItems(_FAMILIES)
        if rule:
            self.category.setCurrentText(rule.category)
            self.family.setCurrentText(rule.family)
        self.minimum = QDoubleSpinBox()
        self.minimum.setRange(-1e12, 1e12)
        self.minimum.setDecimals(6)
        self.maximum = QDoubleSpinBox()
        self.maximum.setRange(-1e12, 1e12)
        self.maximum.setDecimals(6)
        self.minimum.setSpecialValueText("не задан")
        self.maximum.setSpecialValueText("не задан")
        self.minimum.setMinimum(-1e12)
        self.maximum.setMinimum(-1e12)
        if rule and rule.default_min is not None:
            self.minimum.setValue(rule.default_min)
        else:
            self.minimum.setValue(-1e12)
        if rule and rule.default_max is not None:
            self.maximum.setValue(rule.default_max)
        else:
            self.maximum.setValue(-1e12)
        form.addRow("Мнемоника в чужом LAS", self.foreign)
        form.addRow("Каноническая мнемоника", self.canonical)
        form.addRow("Название параметра", self.name)
        form.addRow("Единица", self.unit)
        form.addRow("Дополнительные псевдонимы", self.aliases)
        form.addRow("Категория", self.category)
        form.addRow("Семейство дорожки", self.family)
        form.addRow("Рекомендуемый минимум", self.minimum)
        form.addRow("Рекомендуемый максимум", self.maximum)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def rule(self) -> UserMnemonicRule:
        aliases = tuple(x.strip() for x in self.aliases.text().split(",") if x.strip())
        min_value = None if self.minimum.value() <= -1e12 else self.minimum.value()
        max_value = None if self.maximum.value() <= -1e12 else self.maximum.value()
        return UserMnemonicRule(
            self._rule_id,
            self.foreign.text(),
            self.canonical.text(),
            self.name.text(),
            self.unit.text(),
            self.category.currentText(),
            self.family.currentText(),
            aliases,
            min_value,
            max_value,
        ).validate()

    def accept(self) -> None:
        try:
            self.rule()
        except ValueError as exc:
            QMessageBox.warning(self, "Правило мнемоники", str(exc))
            return
        super().accept()


class SensorCatalogDialog(QDialog):
    catalog_changed = Signal(object)

    def __init__(
        self,
        catalog: SensorCatalog,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        registry: UserMnemonicRegistry | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.registry = registry or UserMnemonicRegistry()
        self._base_catalog = default_sensor_catalog()
        self._catalog = self.registry.catalog(self._base_catalog)
        self.setWindowTitle(self._t("sensors.title"))
        self.resize(1240, 760)
        root = QVBoxLayout(self)
        self.info = QLabel()
        self.info.setWordWrap(True)
        root.addWidget(self.info)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self._t("sensors.search"))
        self.search.textChanged.connect(self._refresh)
        controls.addWidget(self.search, 1)
        for text, slot in (
            ("Добавить правило", self._add_rule),
            ("Изменить", self._edit_rule),
            ("Удалить", self._delete_rule),
            ("Импорт словаря", self._import_rules),
            ("Экспорт словаря", self._export_rules),
            (self._t("sensors.open_json"), self._open_external_catalog),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            controls.addWidget(button)
        root.addLayout(controls)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnCount(9)
        self.tree.setHeaderLabels(
            [
                self._t("sensors.canonical"),
                self._t("sensors.name"),
                self._t("sensors.unit"),
                self._t("sensors.category"),
                self._t("sensors.family"),
                self._t("sensors.range"),
                self._t("sensors.aliases"),
                self._t("sensors.source"),
                self._t("sensors.id"),
            ]
        )
        header = self.tree.header()
        for column in (0, 2, 3, 4, 5, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in (1, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(lambda *_: self._edit_rule())
        root.addWidget(self.tree, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    @property
    def catalog(self) -> SensorCatalog:
        return self._catalog

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _refresh(self) -> None:
        entries = self._catalog.search(self.search.text())
        self.info.setText(
            self._t(
                "sensors.summary",
                name=self._catalog.catalog_name,
                visible=len(entries),
                total=len(self._catalog.sensors),
            )
        )
        self.tree.clear()
        for sensor in entries:
            item = QTreeWidgetItem(
                [
                    sensor.canonical_mnemonic,
                    sensor.name_ru,
                    sensor.unit or "—",
                    sensor.category,
                    sensor.family,
                    sensor.default_range_text,
                    ", ".join(sensor.aliases),
                    sensor.source or "—",
                    sensor.sensor_id,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, sensor.sensor_id)
            self.tree.addTopLevelItem(item)

    def _selected_rule(self) -> UserMnemonicRule | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        sensor_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(sensor_id, str) or not sensor_id.startswith("user:"):
            return None
        rule_id = sensor_id.split(":", 1)[1]
        return next((x for x in self.registry.rules() if x.rule_id == rule_id), None)

    def _rebuild(self) -> None:
        self._catalog = self.registry.catalog(self._base_catalog)
        self._refresh()
        self.catalog_changed.emit(self._catalog)

    def _add_rule(self) -> None:
        dialog = MnemonicRuleDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.registry.upsert(dialog.rule())
                self._rebuild()
            except ValueError as exc:
                QMessageBox.warning(self, self._t("sensors.title"), str(exc))

    def _edit_rule(self) -> None:
        rule = self._selected_rule()
        if rule is None:
            QMessageBox.information(
                self, self._t("sensors.title"), "Изменять можно только пользовательские правила"
            )
            return
        dialog = MnemonicRuleDialog(rule, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.registry.upsert(dialog.rule())
                self._rebuild()
            except ValueError as exc:
                QMessageBox.warning(self, self._t("sensors.title"), str(exc))

    def _delete_rule(self) -> None:
        rule = self._selected_rule()
        if rule is None:
            return
        if (
            QMessageBox.question(
                self,
                self._t("sensors.title"),
                f"Удалить правило {rule.foreign_mnemonic} → {rule.canonical_mnemonic}?",
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.registry.delete(rule.rule_id)
            self._rebuild()

    def _import_rules(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт словаря мнемоник", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.registry.import_json(path)
            self._rebuild()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, self._t("sensors.title"), str(exc))

    def _export_rules(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт словаря мнемоник", "mnemonics.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            self.registry.export_json(path)
        except OSError as exc:
            QMessageBox.warning(self, self._t("sensors.title"), str(exc))

    def _open_external_catalog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("sensors.open_title"), "", "Sensors JSON (*.json);;JSON (*.json)"
        )
        if not path:
            return
        try:
            self._base_catalog = SensorCatalog.from_json(Path(path))
            self._rebuild()
        except ValueError as exc:
            QMessageBox.warning(self, self._t("sensors.title"), str(exc))
