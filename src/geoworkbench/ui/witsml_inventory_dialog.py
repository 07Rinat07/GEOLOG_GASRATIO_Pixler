from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.importers.witsml import (
    WitsmlInventory,
    WitsmlInventoryError,
    inspect_witsml,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class WitsmlInventoryDialog(QDialog):
    """Read-only inventory for WITSML 2.x XML objects and channels."""

    def __init__(
        self,
        source: str | Path,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.source = Path(source)
        self.localizer = Localizer.create(language)
        self.inventory: WitsmlInventory | None = None
        self.error: str | None = None

        self.setWindowTitle(self._t("witsml.title"))
        self.resize(1180, 720)
        root = QVBoxLayout(self)

        self.summary = QLabel(self._t("witsml.inspecting", file=self.source.name))
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.tabs = QTabWidget(self)
        self.objects_tree = self._create_objects_tree()
        self.channels_tree = self._create_channels_tree()
        self.diagnostics_text = QPlainTextEdit(self)
        self.diagnostics_text.setReadOnly(True)
        self.tabs.addTab(self.objects_tree, self._t("witsml.objects_tab"))
        self.tabs.addTab(self.channels_tree, self._t("witsml.channels_tab"))
        self.tabs.addTab(self.diagnostics_text, self._t("witsml.diagnostics_tab"))
        root.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_inventory()

    def _create_objects_tree(self) -> QTreeWidget:
        tree = QTreeWidget(self)
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setColumnCount(7)
        tree.setHeaderLabels(
            [
                self._t("witsml.column_file"),
                self._t("witsml.column_type"),
                self._t("witsml.column_version"),
                self._t("witsml.column_title"),
                self._t("witsml.column_uuid"),
                self._t("witsml.column_status"),
                self._t("witsml.column_references"),
            ]
        )
        header = tree.header()
        for column in (0, 1, 2, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        return tree

    def _create_channels_tree(self) -> QTreeWidget:
        tree = QTreeWidget(self)
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setColumnCount(10)
        tree.setHeaderLabels(
            [
                self._t("witsml.column_file"),
                self._t("witsml.column_mnemonic"),
                self._t("witsml.column_title"),
                self._t("witsml.column_data_type"),
                self._t("witsml.column_uom"),
                self._t("witsml.column_indexes"),
                self._t("witsml.column_range"),
                self._t("witsml.column_source"),
                self._t("witsml.column_class"),
                self._t("witsml.column_uuid"),
            ]
        )
        header = tree.header()
        for column in (0, 1, 3, 4, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 5, 7, 8, 9):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        return tree

    def _load_inventory(self) -> None:
        try:
            inventory = inspect_witsml(self.source)
        except WitsmlInventoryError as exc:
            self.error = str(exc)
            self.summary.setText(self._t("witsml.invalid", error=self.error))
            self.diagnostics_text.setPlainText(self.error)
            self.tabs.setCurrentWidget(self.diagnostics_text)
            return

        self.inventory = inventory
        versions = ", ".join(inventory.schema_versions) or self._t("witsml.unknown")
        type_counts = ", ".join(
            f"{name}: {count}" for name, count in sorted(inventory.type_counts.items())
        )
        self.summary.setText(
            self._t(
                "witsml.summary",
                file=self.source.name,
                objects=len(inventory.objects),
                channels=len(inventory.channels),
                versions=versions,
                types=type_counts or "—",
                diagnostics=len(inventory.diagnostics),
            )
        )

        for item in inventory.objects:
            self.objects_tree.addTopLevelItem(
                QTreeWidgetItem(
                    [
                        item.source_name,
                        item.object_type,
                        item.schema_version or "—",
                        item.title or "—",
                        item.uuid or item.uid or "—",
                        item.growing_status or "—",
                        str(len(item.references)),
                    ]
                )
            )

        for item in inventory.channels:
            channel = item.channel
            assert channel is not None
            indexes = "; ".join(index.display_text for index in channel.indexes) or "—"
            range_text = " → ".join(
                value
                for value in (channel.start_index, channel.end_index)
                if value is not None
            ) or "—"
            self.channels_tree.addTopLevelItem(
                QTreeWidgetItem(
                    [
                        item.source_name,
                        channel.mnemonic or "—",
                        item.title or "—",
                        channel.data_type or "—",
                        channel.uom or "—",
                        indexes,
                        range_text,
                        channel.source or channel.logging_method or "—",
                        channel.channel_class or "—",
                        item.uuid or "—",
                    ]
                )
            )

        if inventory.diagnostics:
            lines = [
                self._t(
                    "witsml.diagnostic_line",
                    severity=self._t(f"witsml.severity_{item.severity}"),
                    file=item.source_name,
                    message=item.message,
                )
                for item in inventory.diagnostics
            ]
            self.diagnostics_text.setPlainText("\n".join(lines))
        else:
            self.diagnostics_text.setPlainText(self._t("witsml.no_diagnostics"))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
