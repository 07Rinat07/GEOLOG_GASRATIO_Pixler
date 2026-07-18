from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.catalogs.sensors import SensorCatalog, active_sensor_catalog
from geoworkbench.domain.models import Dataset
from geoworkbench.services.curve_catalog import (
    CurveCatalogEntry,
    CurveCategory,
    analyze_dataset_curves,
    recommended_curve_mnemonics,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class LasCurveBrowser(QWidget):
    build_requested = Signal(object)
    add_requested = Signal(object)
    replace_requested = Signal(object)
    preview_requested = Signal(object)

    def __init__(self, *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__()
        self.localizer = Localizer.create(language)
        self._dataset: Dataset | None = None
        self._entries: dict[str, CurveCatalogEntry] = {}
        self._can_replace = False
        self._sensor_catalog: SensorCatalog = active_sensor_catalog()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        intro = QLabel(self._t("curve_browser.help"))
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self._t("curve_browser.search"))
        self.search_input.textChanged.connect(self._apply_filter)
        root.addWidget(self.search_input)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(8)
        self.tree.setHeaderLabels(
            [
                self._t("curve_browser.mnemonic"),
                self._t("curve_browser.canonical"),
                self._t("curve_browser.unit"),
                self._t("curve_browser.category"),
                self._t("curve_browser.coverage"),
                self._t("curve_browser.range"),
                self._t("curve_browser.reference_range"),
                self._t("curve_browser.description"),
            ]
        )
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.itemChanged.connect(self._selection_changed)
        self.tree.itemDoubleClicked.connect(self._item_double_clicked)
        header = self.tree.header()
        for column in range(7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.tree, 1)

        self.summary = QLabel(self._t("curve_browser.empty"))
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        row = QHBoxLayout()
        self.recommended_button = QPushButton(self._t("curve_browser.recommended"))
        self.recommended_button.clicked.connect(self.select_recommended)
        row.addWidget(self.recommended_button)
        self.clear_button = QPushButton(self._t("curve_browser.clear"))
        self.clear_button.clicked.connect(self.clear_selection)
        row.addWidget(self.clear_button)
        root.addLayout(row)

        self.build_button = QPushButton(self._t("curve_browser.build"))
        self.build_button.clicked.connect(
            lambda: self.build_requested.emit(self.selected_mnemonics())
        )
        root.addWidget(self.build_button)

        actions = QHBoxLayout()
        self.add_button = QPushButton(self._t("curve_browser.add"))
        self.add_button.clicked.connect(lambda: self.add_requested.emit(self.selected_mnemonics()))
        actions.addWidget(self.add_button)
        self.replace_button = QPushButton(self._t("curve_browser.replace"))
        self.replace_button.clicked.connect(
            lambda: self.replace_requested.emit(self.selected_mnemonics())
        )
        actions.addWidget(self.replace_button)
        root.addLayout(actions)

        self.set_dataset(None)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def set_dataset(self, dataset: Dataset | None) -> None:
        self._dataset = dataset
        self._entries = {}
        self.tree.blockSignals(True)
        self.tree.clear()
        if dataset is not None:
            for entry in analyze_dataset_curves(dataset, self._sensor_catalog):
                self._entries[entry.mnemonic] = entry
                item = QTreeWidgetItem(
                    [
                        entry.mnemonic,
                        entry.canonical_mnemonic or "—",
                        entry.unit or "—",
                        self._category_label(entry.category),
                        f"{entry.coverage_percent:.1f}%",
                        entry.range_text,
                        entry.reference_range_text,
                        entry.description or "—",
                    ]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, entry.mnemonic)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, entry.matched_catalog_id)
                if entry.is_catalog_matched:
                    tooltip = self._t(
                        "curve_browser.catalog_tooltip",
                        canonical=entry.canonical_mnemonic,
                        name=entry.reference_name or entry.description,
                        source=entry.reference_source or "Sensors",
                    )
                    for column in range(self.tree.columnCount()):
                        item.setToolTip(column, tooltip)
                else:
                    item.setToolTip(1, self._t("curve_browser.catalog_unmatched"))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                if entry.valid_count == 0:
                    item.setDisabled(True)
                    item.setToolTip(0, self._t("curve_browser.no_numeric"))
                self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        self.search_input.clear()
        self._update_enabled_state()
        self._selection_changed()


    @property
    def sensor_catalog(self) -> SensorCatalog:
        return self._sensor_catalog

    def set_sensor_catalog(self, catalog: SensorCatalog) -> None:
        self._sensor_catalog = catalog
        self.set_dataset(self._dataset)

    def selected_mnemonics(self) -> list[str]:
        result: list[str] = []
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None:
                continue
            if item.checkState(0) == Qt.CheckState.Checked and not item.isDisabled():
                mnemonic = item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(mnemonic, str):
                    result.append(mnemonic)
        return result

    def select_recommended(self) -> None:
        if self._dataset is None:
            return
        selected = set(
            recommended_curve_mnemonics(self._dataset, catalog=self._sensor_catalog)
        )
        self.tree.blockSignals(True)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None:
                continue
            mnemonic = item.data(0, Qt.ItemDataRole.UserRole)
            state = Qt.CheckState.Checked if mnemonic in selected else Qt.CheckState.Unchecked
            item.setCheckState(0, state)
        self.tree.blockSignals(False)
        self._selection_changed()

    def clear_selection(self) -> None:
        self.tree.blockSignals(True)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is not None:
                item.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self._selection_changed()

    def set_replace_enabled(self, enabled: bool) -> None:
        self._can_replace = enabled
        self.replace_button.setEnabled(enabled and bool(self.selected_mnemonics()))

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None:
                continue
            haystack = " ".join(item.text(column) for column in range(self.tree.columnCount()))
            item.setHidden(bool(needle) and needle not in haystack.casefold())

    def _selection_changed(self, *_args: object) -> None:
        selected = self.selected_mnemonics()
        total = len(self._entries)
        if self._dataset is None:
            self.summary.setText(self._t("curve_browser.empty"))
        else:
            self.summary.setText(
                self._t(
                    "curve_browser.summary",
                    selected=len(selected),
                    total=total,
                )
            )
        enabled = bool(selected)
        self.build_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.replace_button.setEnabled(enabled and self._can_replace)
        self.preview_requested.emit(selected)

    def _update_enabled_state(self) -> None:
        has_dataset = self._dataset is not None
        self.search_input.setEnabled(has_dataset)
        self.tree.setEnabled(has_dataset)
        self.recommended_button.setEnabled(has_dataset)
        self.clear_button.setEnabled(has_dataset)
        self.build_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.replace_button.setEnabled(False)

    def _item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.isDisabled():
            return
        checked = item.checkState(0) is Qt.CheckState.Checked
        item.setCheckState(0, Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked)

    def _category_label(self, category: CurveCategory) -> str:
        return self._t(f"curve_browser.category.{category.value}")
