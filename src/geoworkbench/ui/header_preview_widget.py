from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.printing.masterlog_renderer import (
    masterlog_header_size_mm,
    paint_masterlog_header,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


def _page_size_mm(template: MasterlogTemplate) -> tuple[float, float]:
    dimensions = {
        "A0": (841.0, 1189.0),
        "A1": (594.0, 841.0),
        "A2": (420.0, 594.0),
        "A3": (297.0, 420.0),
        "A4": (210.0, 297.0),
        "letter": (215.9, 279.4),
        "legal": (215.9, 355.6),
    }
    if template.page_format == "custom":
        raw_width = template.properties.get("custom_width_mm", 210.0)
        raw_height = template.properties.get("custom_height_mm", 297.0)
        width = float(raw_width) if isinstance(raw_width, (int, float)) else 210.0
        height = float(raw_height) if isinstance(raw_height, (int, float)) else 297.0
    elif template.page_format == "roll":
        raw_width = template.properties.get("custom_width_mm", 210.0)
        width = float(raw_width) if isinstance(raw_width, (int, float)) else 210.0
        height = max(297.0, template.header_height_mm + 180.0)
    else:
        width, height = dimensions.get(template.page_format, (210.0, 297.0))
    if template.page_format != "roll" and template.properties.get("orientation") == "landscape":
        width, height = height, width
    return max(25.0, width), max(25.0, height)


def _expanded_template(template: MasterlogTemplate) -> tuple[MasterlogTemplate, bool]:
    clone = deepcopy(template)
    element_bottom = max(
        (element.y_mm + element.height_mm for element in clone.header_elements),
        default=0.0,
    )
    expanded = element_bottom > clone.header_height_mm + 1e-6
    if expanded:
        clone.header_height_mm = min(500.0, max(clone.header_height_mm, element_bottom + 2.0))
    return clone, expanded


def render_header_preview_pixmap(
    template: MasterlogTemplate,
    session: ProjectSession,
    target_size: QSize = QSize(1200, 360),
    *,
    language: AppLanguage = AppLanguage.RU,
    mode: str = "header",
) -> QPixmap:
    """Render a WYSIWYG preview using the same painter as PDF/printing."""

    safe_width = max(320, int(target_size.width()))
    safe_height = max(180, int(target_size.height()))
    image = QImage(safe_width, safe_height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#e5e7eb"))
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        margin = 16.0
        canvas = QRectF(margin, margin, safe_width - margin * 2.0, safe_height - margin * 2.0)
        effective, expanded = _expanded_template(template)
        if mode == "page":
            page_width_mm, page_height_mm = _page_size_mm(effective)
            scale = min(canvas.width() / page_width_mm, canvas.height() / page_height_mm)
            page = QRectF(
                canvas.center().x() - page_width_mm * scale / 2.0,
                canvas.center().y() - page_height_mm * scale / 2.0,
                page_width_mm * scale,
                page_height_mm * scale,
            )
            painter.fillRect(page, Qt.GlobalColor.white)
            painter.setPen(QPen(QColor("#64748b"), 1.0))
            painter.drawRect(page)
            header_fraction = min(0.72, effective.header_height_mm / page_height_mm)
            header_target = QRectF(
                page.left(),
                page.top(),
                page.width(),
                max(8.0, page.height() * header_fraction),
            )
            paint_masterlog_header(
                painter,
                header_target,
                effective,
                session,
                language=language,
            )
            body = QRectF(
                page.left(),
                header_target.bottom(),
                page.width(),
                max(0.0, page.bottom() - header_target.bottom()),
            )
            if body.height() > 8.0:
                painter.fillRect(body, QColor("#f8fafc"))
                painter.setPen(QPen(QColor("#cbd5e1"), 1.0, Qt.PenStyle.DashLine))
                painter.drawRect(body.adjusted(5.0, 5.0, -5.0, -5.0))
        else:
            size_mm = masterlog_header_size_mm(effective)
            ratio = size_mm.width() / max(1.0, size_mm.height())
            render_width = canvas.width()
            render_height = min(canvas.height(), render_width / max(1.0, ratio))
            if render_height < canvas.height() * 0.55:
                render_height = canvas.height() * 0.55
                render_width = min(canvas.width(), render_height * ratio)
            header_target = QRectF(
                canvas.center().x() - render_width / 2.0,
                canvas.center().y() - render_height / 2.0,
                render_width,
                render_height,
            )
            paint_masterlog_header(
                painter,
                header_target,
                effective,
                session,
                language=language,
            )
        if expanded:
            painter.setPen(QColor("#b91c1c"))
            painter.drawText(
                QRectF(margin, safe_height - 28.0, safe_width - margin * 2.0, 18.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                {
                    AppLanguage.RU: "Предпросмотр раскрыт до фактической нижней границы элементов",
                    AppLanguage.KK: "Алдын ала қарау элементтердің нақты төменгі шекарасына дейін ашылды",
                    AppLanguage.EN: "Preview expanded to the actual lower element boundary",
                }[language],
            )
    finally:
        painter.end()
    return QPixmap.fromImage(image)


class _PreviewView(QGraphicsView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._fit_on_resize = True

    def set_pixmap(self, pixmap: QPixmap) -> None:
        assert self.scene() is not None
        self.scene().clear()
        self._pixmap_item = self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        self.fit_all()

    def fit_all(self) -> None:
        scene = self.scene()
        if scene is None or scene.sceneRect().isEmpty():
            return
        self.resetTransform()
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._fit_on_resize = True

    def actual_size(self) -> None:
        self.resetTransform()
        self._fit_on_resize = False

    def zoom(self, factor: float) -> None:
        self.scale(factor, factor)
        self._fit_on_resize = False

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._fit_on_resize:
            self.fit_all()


class HeaderPreviewWidget(QWidget):
    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.language = language
        self.template: MasterlogTemplate | None = None
        self.mode = QComboBox()
        self.mode.addItem(
            {AppLanguage.RU: "Шапка крупно", AppLanguage.KK: "Тақырып ірі", AppLanguage.EN: "Header close-up"}[language],
            "header",
        )
        self.mode.addItem(
            {AppLanguage.RU: "Лист целиком", AppLanguage.KK: "Толық бет", AppLanguage.EN: "Whole page"}[language],
            "page",
        )
        self.mode.currentIndexChanged.connect(self.refresh)
        self.view = _PreviewView(self)
        self.view.setObjectName("print-header-expanded-preview")
        fit_button = QPushButton(
            {AppLanguage.RU: "Вместить", AppLanguage.KK: "Сыйғызу", AppLanguage.EN: "Fit"}[language]
        )
        fit_button.clicked.connect(self.view.fit_all)
        actual_button = QPushButton("100 %")
        actual_button.clicked.connect(self.view.actual_size)
        minus_button = QPushButton("−")
        minus_button.clicked.connect(lambda: self.view.zoom(1.0 / 1.2))
        plus_button = QPushButton("+")
        plus_button.clicked.connect(lambda: self.view.zoom(1.2))
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel(
            {AppLanguage.RU: "Режим", AppLanguage.KK: "Режим", AppLanguage.EN: "Mode"}[language]
        ))
        toolbar.addWidget(self.mode)
        toolbar.addStretch(1)
        toolbar.addWidget(minus_button)
        toolbar.addWidget(actual_button)
        toolbar.addWidget(plus_button)
        toolbar.addWidget(fit_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)

    def set_template(self, template: MasterlogTemplate | None) -> None:
        self.template = template
        self.refresh()

    def refresh(self, _index: int | None = None) -> None:
        if self.template is None:
            blank = QPixmap(900, 260)
            blank.fill(QColor("#f1f5f9"))
            self.view.set_pixmap(blank)
            return
        size = QSize(max(900, self.width() * 2), max(260, self.height() * 2))
        pixmap = render_header_preview_pixmap(
            self.template,
            self.session,
            size,
            language=self.language,
            mode=str(self.mode.currentData() or "header"),
        )
        self.view.set_pixmap(pixmap)


class HeaderPreviewDialog(QDialog):
    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        edit_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._edit_callback = edit_callback
        self.setWindowTitle(
            {
                AppLanguage.RU: f"Предпросмотр и проверка шапки — {template.name}",
                AppLanguage.KK: f"Тақырыпты алдын ала қарау және тексеру — {template.name}",
                AppLanguage.EN: f"Header preview and inspection — {template.name}",
            }[language]
        )
        self.setMinimumSize(1100, 680)
        self.resize(1700, 980)

        hint = QLabel(
            {
                AppLanguage.RU: (
                    "Слева шапка показана крупно для проверки текста и блоков; справа — её реальный "
                    "размер на печатном листе. Масштаб каждого вида настраивается независимо."
                ),
                AppLanguage.KK: (
                    "Сол жақта мәтін мен блоктарды тексеру үшін тақырып ірі көрсетіледі; оң жақта "
                    "баспа бетіндегі нақты орналасуы көрсетіледі."
                ),
                AppLanguage.EN: (
                    "The left pane shows a close-up for checking text and blocks; the right pane "
                    "shows the real placement on the printed page. Each view has independent zoom."
                ),
            }[language]
        )
        hint.setWordWrap(True)

        close_up_group = QGroupBox(
            {AppLanguage.RU: "Шапка крупно", AppLanguage.KK: "Тақырып ірі", AppLanguage.EN: "Header close-up"}[language]
        )
        close_up_layout = QVBoxLayout(close_up_group)
        self.close_up_preview = HeaderPreviewWidget(session, close_up_group, language=language)
        self.close_up_preview.mode.setCurrentIndex(
            max(0, self.close_up_preview.mode.findData("header"))
        )
        self.close_up_preview.set_template(template)
        close_up_layout.addWidget(self.close_up_preview)

        page_group = QGroupBox(
            {AppLanguage.RU: "Лист целиком", AppLanguage.KK: "Толық бет", AppLanguage.EN: "Whole page"}[language]
        )
        page_layout = QVBoxLayout(page_group)
        self.page_preview = HeaderPreviewWidget(session, page_group, language=language)
        self.page_preview.mode.setCurrentIndex(
            max(0, self.page_preview.mode.findData("page"))
        )
        self.page_preview.set_template(template)
        page_layout.addWidget(self.page_preview)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(close_up_group)
        splitter.addWidget(page_group)
        splitter.setSizes([1050, 650])

        fullscreen_button = QPushButton(
            {AppLanguage.RU: "Полный экран", AppLanguage.KK: "Толық экран", AppLanguage.EN: "Full screen"}[language]
        )
        fullscreen_button.clicked.connect(self._toggle_fullscreen)
        edit_button = QPushButton(
            {AppLanguage.RU: "Редактировать шапку…", AppLanguage.KK: "Тақырыпты өңдеу…", AppLanguage.EN: "Edit header…"}[language]
        )
        edit_button.setEnabled(edit_callback is not None)
        edit_button.clicked.connect(self._open_editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addWidget(fullscreen_button)
        footer.addWidget(edit_button)
        footer.addStretch(1)
        footer.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(splitter, 1)
        layout.addLayout(footer)

    def _toggle_fullscreen(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _open_editor(self) -> None:
        callback = self._edit_callback
        if callback is None:
            return
        self.accept()
        callback()
