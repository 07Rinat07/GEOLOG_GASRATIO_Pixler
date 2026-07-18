from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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

from geoworkbench.catalogs.sensors import SensorCatalog, SensorDefinition
from geoworkbench.services.localization import AppLanguage, Localizer


class SensorCatalogDialog(QDialog):
    catalog_changed = Signal(object)

    def __init__(
        self,
        catalog: SensorCatalog,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self._catalog = catalog
        self.setWindowTitle(self._t("sensors.title"))
        self.resize(1180, 720)

        root = QVBoxLayout(self)
        self.info = QLabel()
        self.info.setWordWrap(True)
        root.addWidget(self.info)

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self._t("sensors.search"))
        self.search.textChanged.connect(self._refresh)
        controls.addWidget(self.search, 1)
        self.open_button = QPushButton(self._t("sensors.open_json"))
        self.open_button.clicked.connect(self._open_external_catalog)
        controls.addWidget(self.open_button)
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
        for column in (0, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in (1, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
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
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        for sensor in entries:
            item = self._item(sensor)
            self.tree.addTopLevelItem(item)
        self.tree.setUpdatesEnabled(True)

    def _item(self, sensor: SensorDefinition) -> QTreeWidgetItem:
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
        item.setToolTip(6, "\n".join(sensor.aliases))
        return item

    def _open_external_catalog(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            self._t("sensors.open_title"),
            "",
            "Sensors JSON (*.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            catalog = SensorCatalog.from_json(Path(path))
        except ValueError as exc:
            QMessageBox.warning(self, self._t("sensors.title"), str(exc))
            return
        self._catalog = catalog
        self.search.clear()
        self._refresh()
        self.catalog_changed.emit(catalog)
        QMessageBox.information(
            self,
            self._t("sensors.title"),
            self._t("sensors.loaded", count=len(catalog.sensors)),
        )
