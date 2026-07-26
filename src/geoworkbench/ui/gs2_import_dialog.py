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
from geoworkbench.importers.gs2.metadata import (
    Gs2Metadata,
    Gs2MetadataState,
    read_gs2_container_metadata,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class Gs2ImportDialog(QDialog):
    """Inspect a GS2 container, Access metadata, and selectable Paradox series."""

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
        self.metadata: Gs2Metadata | None = None
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
        multipart_groups = manifest.multipart_groups
        grouped_members = {
            member_name.casefold()
            for group in multipart_groups
            for member_name in group.member_names
        }
        preferred_index = -1
        preferred_score: tuple[bool, int, int] | None = None
        for table in manifest.tables:
            if table.member_name.casefold() in grouped_members:
                continue
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
                (table.member_name,),
            )
            score = (table.has_depth, table.field_count, table.record_count)
            if preferred_score is None or score > preferred_score:
                preferred_score = score
                preferred_index = self.table_combo.count() - 1
        for group in multipart_groups:
            roles = "/".join(
                role
                for role, enabled in (
                    ("DEPTH", group.has_depth),
                    ("TIME", group.has_time),
                )
                if enabled
            )
            self.table_combo.addItem(
                self._t(
                    "gs2.group_item",
                    file=group.base_name,
                    parts=len(group.member_names),
                    rows=group.record_count,
                    fields=group.field_count,
                    roles=roles or "—",
                ),
                group.member_names,
            )
            score = (group.has_depth, group.field_count, group.record_count)
            if preferred_score is None or score > preferred_score:
                preferred_score = score
                preferred_index = self.table_combo.count() - 1
        if preferred_index >= 0:
            self.table_combo.setCurrentIndex(preferred_index)
        self.table_combo.setVisible(self.table_combo.count() > 0)
        self.ok_button.setEnabled(self.table_combo.count() > 0)
        self.metadata = read_gs2_container_metadata(self.source)
        member_lines = "\n".join(
            f"• {member.name} — {member.size:,} bytes"
            for member in manifest.data_members
        )
        container_text = self._t(
            "gs2.valid",
            metadata=manifest.metadata_member.name,
            count=len(manifest.data_members),
            tables=len(manifest.tables),
            unpacked=f"{manifest.uncompressed_size:,}",
            members=member_lines,
        )
        details.setPlainText(
            f"{container_text}\n\n{self._metadata_summary(self.metadata)}"
        )

    def _metadata_summary(self, metadata: Gs2Metadata) -> str:
        diagnostic = metadata.diagnostics[0] if metadata.diagnostics else None
        values = {
            "adapter": metadata.adapter or "—",
            "tables": len(metadata.database_tables),
            "channels": len(metadata.channels),
            "formulas": len(metadata.formulas),
            "reason": diagnostic.message if diagnostic is not None else "—",
            "action": diagnostic.action if diagnostic is not None else "—",
        }
        key = {
            Gs2MetadataState.LOADED: "gs2.metadata_loaded",
            Gs2MetadataState.PARTIAL: "gs2.metadata_partial",
            Gs2MetadataState.UNAVAILABLE: "gs2.metadata_unavailable",
            Gs2MetadataState.FAILED: "gs2.metadata_failed",
        }[metadata.state]
        return self._t(key, **values)

    @property
    def selected_table_member(self) -> str | None:
        members = self.selected_table_members
        return members[0] if len(members) == 1 else None

    @property
    def selected_table_members(self) -> tuple[str, ...]:
        value = self.table_combo.currentData()
        if isinstance(value, tuple) and all(
            isinstance(item, str) for item in value
        ):
            return value
        if isinstance(value, list) and all(
            isinstance(item, str) for item in value
        ):
            return tuple(value)
        return (str(value),) if value else ()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
