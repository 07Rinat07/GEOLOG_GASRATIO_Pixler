from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.masterlog_inspection_controller import (
    MasterlogInspectionController,
)
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.printing.masterlog_renderer import paint_masterlog
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_inspection import (
    MasterlogInspection,
    inspect_masterlog_point,
    masterlog_column_header_at_point,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.masterlog_interval_fill_dialog import CuttingsCompositionDialog
from geoworkbench.ui.masterlog_columns_dialog import edit_masterlog_column
from geoworkbench.ui.masterlog_callouts_dialog import MasterlogCalloutsDialog
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog
from geoworkbench.ui.stratigraphy_dialog import StratigraphyIntervalDialog


class MasterlogPreviewWidget(QWidget):
    interval_selected = Signal(float, float, str)
    inspection_selected = Signal(object)
    column_edit_requested = Signal(str)

    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        settings: MasterlogOutputSettings | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.template = template
        self.session = session
        self.settings = settings
        self.last_inspection: MasterlogInspection | None = None
        self.selection_mode: str | None = None
        self._selection_origin: QPoint | None = None
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setMinimumSize(640, 480)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        paint_masterlog(
            painter,
            QRectF(10.0, 10.0, float(self.width() - 20), float(self.height() - 20)),
            self.template,
            self.session,
            depth_range=self.settings.depth_range if self.settings is not None else None,
            language=(self.settings.language if self.settings is not None else AppLanguage.RU),
        )
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.selection_mode is not None and event.button() == Qt.MouseButton.LeftButton:
            self._selection_origin = event.position().toPoint()
            self._rubber_band.setGeometry(QRect(self._selection_origin, self._selection_origin))
            self._rubber_band.show()
            event.accept()
            return
        language = self.settings.language if self.settings is not None else AppLanguage.RU
        self.last_inspection = inspect_masterlog_point(
            event.position(),
            QRectF(10.0, 10.0, float(self.width() - 20), float(self.height() - 20)),
            self.template,
            self.session,
            depth_range=self.settings.depth_range if self.settings is not None else None,
            language=language,
        )
        if self.last_inspection is not None:
            QToolTip.showText(
                event.globalPosition().toPoint(),
                self.last_inspection.display_text(language),
                self,
            )
            self.inspection_selected.emit(self.last_inspection)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._selection_origin is not None:
            self._rubber_band.setGeometry(
                QRect(self._selection_origin, event.position().toPoint()).normalized()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._selection_origin is None or self.selection_mode is None:
            super().mouseReleaseEvent(event)
            return
        start = self._depth_at_y(float(self._selection_origin.y()))
        end = self._depth_at_y(event.position().y())
        self._selection_origin = None
        self._rubber_band.hide()
        if start is not None and end is not None and abs(start - end) > 1e-9:
            self.interval_selected.emit(min(start, end), max(start, end), self.selection_mode)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.selection_mode is None and event.button() == Qt.MouseButton.LeftButton:
            column = masterlog_column_header_at_point(
                event.position(),
                QRectF(10.0, 10.0, float(self.width() - 20), float(self.height() - 20)),
                self.template,
                self.session,
                depth_range=self.settings.depth_range if self.settings is not None else None,
            )
            if column is not None:
                self.column_edit_requested.emit(column.column_id)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _depth_at_y(self, y: float) -> float | None:
        inspection = inspect_masterlog_point(
            QPointF(self.width() / 2.0, y),
            QRectF(10.0, 10.0, float(self.width() - 20), float(self.height() - 20)),
            self.template,
            self.session,
            depth_range=self.settings.depth_range if self.settings is not None else None,
        )
        return inspection.depth if inspection is not None else None


class MasterlogPreviewDialog(QDialog):
    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        settings: MasterlogOutputSettings | None = None,
    ) -> None:
        super().__init__(parent)
        localizer = Localizer.create(language)
        self.language = language
        self.session = session
        self.setWindowTitle(localizer.text("masterlog_preview.title", name=template.name))
        self.preview = MasterlogPreviewWidget(template, session, settings, self)
        self.preview.interval_selected.connect(self._fill_interval)
        self.preview.column_edit_requested.connect(self._edit_column)
        tools = QHBoxLayout()
        self.inspect_button = QPushButton(
            {AppLanguage.RU: "Просмотр", AppLanguage.KK: "Қарау", AppLanguage.EN: "Inspect"}[
                language
            ]
        )
        self.lithology_button = QPushButton(
            {
                AppLanguage.RU: "Заполнить литологию",
                AppLanguage.KK: "Литологияны толтыру",
                AppLanguage.EN: "Fill lithology",
            }[language]
        )
        self.cuttings_button = QPushButton(
            {
                AppLanguage.RU: "Заполнить шламограмму",
                AppLanguage.KK: "Шламограмманы толтыру",
                AppLanguage.EN: "Fill cuttings",
            }[language]
        )
        self.description_button = QPushButton(
            {
                AppLanguage.RU: "Описание шлама",
                AppLanguage.KK: "Шлам сипаттамасы",
                AppLanguage.EN: "Cuttings description",
            }[language]
        )
        self.analysis_button = QPushButton(
            {
                AppLanguage.RU: "Кальциметрия / ЛБА",
                AppLanguage.KK: "Кальциметрия / ЛБА",
                AppLanguage.EN: "Calcimetry / LBA",
            }[language]
        )
        self.stratigraphy_button = QPushButton(
            {
                AppLanguage.RU: "Стратиграфия",
                AppLanguage.KK: "Стратиграфия",
                AppLanguage.EN: "Stratigraphy",
            }[language]
        )
        self.pin_button = QPushButton(
            {
                AppLanguage.RU: "Закрепить для PDF",
                AppLanguage.KK: "PDF үшін бекіту",
                AppLanguage.EN: "Pin for PDF",
            }[language]
        )
        self.pin_button.setEnabled(False)
        self.pin_button.clicked.connect(self._pin_inspection)
        self.preview.inspection_selected.connect(
            lambda inspection: self.pin_button.setEnabled(inspection is not None)
        )
        self.callouts_button = QPushButton(
            {
                AppLanguage.RU: "Выноски...",
                AppLanguage.KK: "Белгілер...",
                AppLanguage.EN: "Callouts...",
            }[language]
        )
        self.callouts_button.clicked.connect(self._manage_callouts)
        for button, mode in (
            (self.inspect_button, None),
            (self.lithology_button, "lithology"),
            (self.cuttings_button, "cuttings"),
            (self.description_button, "cuttings_description"),
            (self.analysis_button, "analysis"),
            (self.stratigraphy_button, "stratigraphy"),
        ):
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=mode: self._set_mode(value))
            tools.addWidget(button)
        tools.addWidget(self.pin_button)
        tools.addWidget(self.callouts_button)
        self.inspect_button.setChecked(True)
        hint = QLabel(
            {
                AppLanguage.RU: "Дважды щёлкните по шапке колонки, чтобы изменить её параметры.",
                AppLanguage.KK: "Баған параметрлерін өзгерту үшін оның тақырыбын екі рет шертіңіз.",
                AppLanguage.EN: "Double-click a column header to edit its parameters.",
            }[language]
        )
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(tools)
        layout.addWidget(hint)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)
        self.resize(980, 650)

    def _set_mode(self, mode: str | None) -> None:
        self.preview.selection_mode = mode
        self.preview.setCursor(
            Qt.CursorShape.CrossCursor if mode is not None else Qt.CursorShape.ArrowCursor
        )
        self.inspect_button.setChecked(mode is None)
        self.lithology_button.setChecked(mode == "lithology")
        self.cuttings_button.setChecked(mode == "cuttings")
        self.description_button.setChecked(mode == "cuttings_description")
        self.analysis_button.setChecked(mode == "analysis")
        self.stratigraphy_button.setChecked(mode == "stratigraphy")

    def _fill_interval(self, top: float, bottom: float, mode: str) -> None:
        try:
            if mode == "lithology":
                self._fill_lithology(top, bottom)
            elif mode == "cuttings":
                self._fill_cuttings(top, bottom)
            elif mode == "cuttings_description":
                self._fill_cuttings_description(top, bottom)
            elif mode == "stratigraphy":
                self._fill_stratigraphy(top, bottom)
            else:
                self._fill_analysis(top, bottom)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
        else:
            self.preview.update()

    def _pin_inspection(self) -> None:
        inspection = self.preview.last_inspection
        if inspection is None:
            return
        try:
            MasterlogInspectionController(self.session).pin(
                self.preview.template, inspection, self.language
            )
        except RuntimeError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.preview.update()
        self.pin_button.setEnabled(False)
        QMessageBox.information(
            self,
            self.windowTitle(),
            {
                AppLanguage.RU: "Выноска закреплена и будет включена в PDF.",
                AppLanguage.KK: "Белгі бекітілді және PDF файлына қосылады.",
                AppLanguage.EN: "The callout is pinned and will be included in the PDF.",
            }[self.language],
        )

    def _manage_callouts(self) -> None:
        dialog = MasterlogCalloutsDialog(
            MasterlogInspectionController(self.session),
            self.preview.template.template_id,
            language=self.language,
            parent=self,
        )
        dialog.exec()
        self.preview.update()

    def _fill_lithology(self, top: float, bottom: float) -> None:
        catalog = LithotypeCatalogController(self.session).available()
        labels = [f"{item.code} — {item.localized_name(self.language.value)}" for item in catalog]
        selected, accepted = QInputDialog.getItem(
            self,
            self.lithology_button.text(),
            f"{top:g}–{bottom:g} м",
            labels,
            editable=False,
        )
        if accepted:
            LithologyController(self.session).add(
                top, bottom, catalog[labels.index(selected)].lithotype_id
            )

    def _fill_cuttings(self, top: float, bottom: float) -> None:
        catalog = LithotypeCatalogController(self.session).available()
        dialog = CuttingsCompositionDialog(
            top, bottom, catalog, language=self.language, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            CuttingsController(self.session).add(top, bottom, dialog.components())

    def _fill_cuttings_description(self, top: float, bottom: float) -> None:
        well = self.session.current_well
        sample = next(
            (
                item
                for item in (well.cuttings if well is not None else ())
                if abs(item.top_depth - top) <= 1e-6 and abs(item.bottom_depth - bottom) <= 1e-6
            ),
            None,
        )
        text, accepted = QInputDialog.getMultiLineText(
            self,
            self.description_button.text(),
            f"{top:g}–{bottom:g} м",
            sample.description if sample is not None and sample.description else "",
        )
        if accepted:
            CuttingsController(self.session).set_description(top, bottom, text)

    def _edit_column(self, column_id: str) -> None:
        template_id = self.preview.template.template_id
        if template_id not in self.session.project.masterlog_templates:
            return
        try:
            changed = edit_masterlog_column(
                self,
                MasterlogTemplateController(self.session),
                template_id,
                column_id,
                language=self.language,
            )
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        if changed:
            self.preview.update()

    def _fill_analysis(self, top: float, bottom: float) -> None:
        well = self.session.current_well
        sample = next(
            (
                item
                for item in (well.cuttings if well is not None else ())
                if abs(item.top_depth - top) <= 1e-6 and abs(item.bottom_depth - bottom) <= 1e-6
            ),
            None,
        )
        dialog = SampleAnalysisDialog(
            top, bottom, language=self.language, sample=sample, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            CuttingsController(self.session).set_analysis(top, bottom, **dialog.values())

    def _fill_stratigraphy(self, top: float, bottom: float) -> None:
        dialog = StratigraphyIntervalDialog(
            top,
            bottom,
            self,
            language=self.language,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            StratigraphyController(self.session).add(**dialog.values())
