from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.masterlog_columns_dialog import MasterlogColumnsDialog
from geoworkbench.ui.masterlog_header_dialog import MasterlogHeaderDialog
from geoworkbench.ui.masterlog_assets_dialog import MasterlogAssetsDialog
from geoworkbench.ui.masterlog_preview_dialog import MasterlogPreviewDialog
from geoworkbench.printing.masterlog_renderer import (
    MasterlogRenderError,
    configure_masterlog_printer,
    export_masterlog_pdf,
    render_masterlog_to_printer,
    masterlog_depth_range,
)
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.ui.masterlog_output_dialog import MasterlogOutputDialog
from geoworkbench.ui.masterlog_page_dialog import MasterlogPageDialog


class MasterlogTemplatesDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogTemplateController,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("masterlog_templates.title"))
        self.resize(560, 380)
        self.list = QListWidget()
        self.list.setObjectName("masterlog-template-list")
        self.create_button = QPushButton(self._t("common.create"))
        self.copy_button = QPushButton(self._t("common.copy"))
        self.rename_button = QPushButton(self._t("common.rename"))
        self.columns_button = QPushButton(self._t("masterlog_columns.action"))
        self.header_button = QPushButton(self._t("masterlog_header.action"))
        self.assets_button = QPushButton(self._t("masterlog_assets.action"))
        self.page_button = QPushButton(self._t("masterlog_page.action"))
        self.preview_button = QPushButton(self._t("masterlog_preview.action"))
        self.export_button = QPushButton(self._t("masterlog_preview.export_pdf"))
        self.print_preview_button = QPushButton(
            self._t("masterlog_preview.system_action")
        )
        self.delete_button = QPushButton(self._t("common.delete"))
        close_button = QPushButton(self._t("common.close"))
        self.create_button.clicked.connect(self._create)
        self.copy_button.clicked.connect(self._copy)
        self.rename_button.clicked.connect(self._rename)
        self.columns_button.clicked.connect(self._edit_columns)
        self.header_button.clicked.connect(self._edit_header)
        self.assets_button.clicked.connect(self._edit_assets)
        self.page_button.clicked.connect(self._edit_page)
        self.preview_button.clicked.connect(self._preview)
        self.export_button.clicked.connect(self._export_pdf)
        self.print_preview_button.clicked.connect(self._system_preview)
        self.delete_button.clicked.connect(self._delete)
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        for button in (
            self.create_button,
            self.copy_button,
            self.rename_button,
            self.columns_button,
            self.header_button,
            self.assets_button,
            self.page_button,
            self.preview_button,
            self.export_button,
            self.print_preview_button,
            self.delete_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.refresh()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def refresh(self) -> None:
        self.list.clear()
        templates = sorted(
            self.controller.session.project.masterlog_templates.values(),
            key=lambda template: template.name.casefold(),
        )
        for template in templates:
            item = QListWidgetItem(
                self._t(
                    "masterlog_templates.item",
                    name=template.name,
                    version=template.version,
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            self.list.addItem(item)

    def _selected_id(self) -> str | None:
        item = self.list.currentItem()
        if item is None:
            QMessageBox.information(
                self, self.windowTitle(), self._t("masterlog_templates.select")
            )
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _ask_name(self, title: str, initial: str = "") -> str | None:
        name, accepted = QInputDialog.getText(
            self, title, self._t("masterlog_templates.name"), text=initial
        )
        return name if accepted else None

    def _create(self) -> None:
        name = self._ask_name(self._t("masterlog_templates.create"))
        if name is not None:
            self._run(lambda: self.controller.create(name))

    def _copy(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        source = self.controller.session.project.masterlog_templates[template_id]
        name = self._ask_name(
            self._t("masterlog_templates.copy"),
            self._t("masterlog_templates.copy_name", name=source.name),
        )
        if name is not None:
            self._run(lambda: self.controller.copy(template_id, name))

    def _rename(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        source = self.controller.session.project.masterlog_templates[template_id]
        name = self._ask_name(self._t("masterlog_templates.rename"), source.name)
        if name is not None:
            self._run(lambda: self.controller.rename(template_id, name))

    def _delete(self) -> None:
        template_id = self._selected_id()
        if template_id is not None:
            self._run(lambda: self.controller.delete(template_id))

    def _edit_columns(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        MasterlogColumnsDialog(
            self.controller,
            template_id,
            self,
            language=self.localizer.language,
        ).exec()
        self.refresh()

    def _edit_header(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        MasterlogHeaderDialog(
            self.controller,
            template_id,
            self,
            language=self.localizer.language,
        ).exec()
        self.refresh()

    def _edit_assets(self) -> None:
        MasterlogAssetsDialog(
            self.controller,
            self,
            language=self.localizer.language,
        ).exec()

    def _edit_page(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        template = self.controller.session.project.masterlog_templates[template_id]
        dialog = MasterlogPageDialog(
            template,
            self,
            language=self.localizer.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        page_format, orientation, scale, header, width, height = dialog.values()
        self._run(
            lambda: self.controller.configure_page(
                template_id,
                page_format=page_format,
                depth_scale=scale,
                header_height_mm=header,
                custom_width_mm=width,
                custom_height_mm=height,
                orientation=orientation,
            )
        )

    def _preview(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        settings = self._ask_output_settings()
        if settings is None:
            return
        MasterlogPreviewDialog(
            self.controller.session.project.masterlog_templates[template_id],
            self.controller.session,
            self,
            language=self.localizer.language,
            settings=settings,
        ).exec()

    def _export_pdf(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        template = self.controller.session.project.masterlog_templates[template_id]
        settings = self._ask_output_settings()
        if settings is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("masterlog_preview.export_pdf"),
            str(Path.cwd() / f"{template.name}.pdf"),
            "PDF (*.pdf)",
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.casefold() != ".pdf":
            target = target.with_suffix(".pdf")
        if target.exists():
            answer = QMessageBox.question(
                self,
                self.windowTitle(),
                self._t("masterlog_preview.overwrite", name=target.name),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            export_masterlog_pdf(
                template,
                self.controller.session,
                target,
                overwrite=True,
                settings=settings,
            )
        except (OSError, MasterlogRenderError) as exc:
            QMessageBox.critical(self, self.windowTitle(), str(exc))
            return
        QMessageBox.information(
            self,
            self.windowTitle(),
            self._t("masterlog_preview.exported", name=target.name),
        )

    def _system_preview(self) -> None:
        template_id = self._selected_id()
        if template_id is None:
            return
        template = self.controller.session.project.masterlog_templates[template_id]
        settings = self._ask_output_settings()
        if settings is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        configure_masterlog_printer(
            printer, template, self.controller.session, settings
        )
        dialog = QPrintPreviewDialog(printer, self)
        dialog.setWindowTitle(
            self._t("masterlog_preview.system_title", name=template.name)
        )

        def paint(requested_printer: QPrinter) -> None:
            try:
                render_masterlog_to_printer(
                    requested_printer, template, self.controller.session, settings
                )
            except MasterlogRenderError as exc:
                QMessageBox.critical(self, self.windowTitle(), str(exc))

        dialog.paintRequested.connect(paint)
        dialog.exec()

    def _ask_output_settings(self) -> MasterlogOutputSettings | None:
        depth_range = masterlog_depth_range(self.controller.session)
        if depth_range is None:
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._t("masterlog_output.no_depth"),
            )
            return None
        dialog = MasterlogOutputDialog(
            depth_range,
            self,
            language=self.localizer.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        try:
            return dialog.settings()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return None

    def _run(self, operation: Callable[[], object]) -> None:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()
