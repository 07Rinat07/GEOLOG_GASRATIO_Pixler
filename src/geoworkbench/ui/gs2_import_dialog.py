from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from geoworkbench.importers.gs2 import Gs2ContainerError, Gs2ContainerManifest, inspect_gs2
from geoworkbench.services.localization import AppLanguage, Localizer


class Gs2ImportDialog(QDialog):
    """Container inspection UI used until the binary channel decoder is available."""

    def __init__(
        self,
        source: str | Path,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.source = Path(source)
        self.localizer = Localizer.create(language)
        self.manifest: Gs2ContainerManifest | None = None
        self.setWindowTitle(self._t("gs2.title"))
        self.resize(680, 480)

        layout = QVBoxLayout(self)
        heading = QLabel(self._t("gs2.inspecting", file=self.source.name))
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self.table_combo = QComboBox(self)
        self.table_combo.setVisible(False)
        layout.addWidget(self.table_combo)

        details = QPlainTextEdit(self)
        details.setReadOnly(True)
        layout.addWidget(details, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText(self._t("gs2.continue"))
        self.ok_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        try:
            self.manifest = inspect_gs2(self.source)
        except Gs2ContainerError as exc:
            details.setPlainText(self._t("gs2.invalid", error=str(exc)))
            return

        manifest = self.manifest
        for table in manifest.tables:
            roles = "/".join(
                role
                for role, enabled in (
                    ("DEPTH", table.has_depth),
                    ("TIME", table.has_time),
                )
                if enabled
            )
            self.table_combo.addItem(
                self._t(
                    "gs2.table_item",
                    file=table.member_name,
                    rows=table.record_count,
                    fields=table.field_count,
                    roles=roles or "—",
                ),
                table.member_name,
            )
        preferred = manifest.preferred_table
        if preferred is not None:
            index = self.table_combo.findData(preferred.member_name)
            if index >= 0:
                self.table_combo.setCurrentIndex(index)
        self.table_combo.setVisible(bool(manifest.tables))
        self.ok_button.setEnabled(bool(manifest.tables))
        member_lines = "\n".join(
            f"• {member.name} — {member.size:,} bytes"
            for member in manifest.data_members
        )
        details.setPlainText(
            self._t(
                "gs2.valid",
                metadata=manifest.metadata_member.name,
                count=len(manifest.data_members),
                tables=len(manifest.tables),
                unpacked=f"{manifest.uncompressed_size:,}",
                members=member_lines,
            )
        )

    @property
    def selected_table_member(self) -> str | None:
        value = self.table_combo.currentData()
        return str(value) if value else None

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
