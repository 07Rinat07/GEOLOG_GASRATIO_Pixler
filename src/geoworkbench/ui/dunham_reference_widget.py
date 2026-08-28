from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.localization import AppLanguage


_REFERENCE_FILE = "dunham_classification_ru_kk_en.pdf"

_TEXT = {
    AppLanguage.RU: {
        "note": (
            "Исходные страницы 12-16 справочника показаны без изменения текста, "
            "описаний, фотографий и подписей."
        ),
        "pages": "5 исходных страниц",
        "zoom_out": "Уменьшить",
        "zoom_in": "Увеличить",
        "fit": "По ширине",
        "error": "Не удалось загрузить встроенный раздел классификации Данэма.",
    },
    AppLanguage.KK: {
        "note": (
            "Анықтамалықтың бастапқы 12-16 беттері мәтіні, сипаттамалары, "
            "фотосуреттері және жазулары өзгертілмей көрсетілген."
        ),
        "pages": "5 бастапқы бет",
        "zoom_out": "Кішірейту",
        "zoom_in": "Үлкейту",
        "fit": "Ені бойынша",
        "error": "Данэм жіктемесінің кірістірілген бөлімін жүктеу мүмкін болмады.",
    },
    AppLanguage.EN: {
        "note": (
            "Original reference pages 12-16 are shown without changing their text, "
            "descriptions, photographs, or captions."
        ),
        "pages": "5 original pages",
        "zoom_out": "Zoom out",
        "zoom_in": "Zoom in",
        "fit": "Fit width",
        "error": "The built-in Dunham classification section could not be loaded.",
    },
}


class DunhamClassificationReference(QWidget):
    """Read-only viewer for the unchanged Dunham pages supplied by the user."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.language = language
        text = _TEXT[language]
        self.setObjectName("dunham-classification-reference")

        root = QVBoxLayout(self)
        note = QLabel(text["note"], self)
        note.setObjectName("dunham-reference-note")
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:#ecfeff; color:#164e63; border:1px solid #67e8f9; "
            "border-radius:5px; padding:6px 8px;"
        )
        root.addWidget(note)

        toolbar = QHBoxLayout()
        page_count = QLabel(text["pages"], self)
        page_count.setObjectName("dunham-reference-page-count")
        toolbar.addWidget(page_count)
        toolbar.addStretch(1)
        self.zoom_out_button = QPushButton("-", self)
        self.zoom_out_button.setObjectName("dunham-reference-zoom-out")
        self.zoom_out_button.setToolTip(text["zoom_out"])
        self.zoom_out_button.clicked.connect(lambda: self._zoom_by(0.85))
        toolbar.addWidget(self.zoom_out_button)
        self.zoom_in_button = QPushButton("+", self)
        self.zoom_in_button.setObjectName("dunham-reference-zoom-in")
        self.zoom_in_button.setToolTip(text["zoom_in"])
        self.zoom_in_button.clicked.connect(lambda: self._zoom_by(1.15))
        toolbar.addWidget(self.zoom_in_button)
        self.fit_width_button = QPushButton(text["fit"], self)
        self.fit_width_button.setObjectName("dunham-reference-fit-width")
        self.fit_width_button.clicked.connect(self.fit_to_width)
        toolbar.addWidget(self.fit_width_button)
        root.addLayout(toolbar)

        self.error_label = QLabel(text["error"], self)
        self.error_label.setObjectName("dunham-reference-error")
        self.error_label.setStyleSheet("color:#b91c1c; font-weight:700;")
        self.error_label.hide()
        root.addWidget(self.error_label)

        self.document = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setObjectName("dunham-reference-pdf-view")
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setPageSpacing(12)
        self.view.setDocument(self.document)
        root.addWidget(self.view, 1)

        resource = (
            files("geoworkbench")
            .joinpath("resources")
            .joinpath("reference")
            .joinpath(_REFERENCE_FILE)
        )
        self._pdf_buffer = QBuffer(self)
        self._pdf_buffer.setData(QByteArray(resource.read_bytes()))
        self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.document.statusChanged.connect(self._update_load_state)
        self.document.load(self._pdf_buffer)
        self.fit_to_width()
        self._update_load_state(self.document.status())

    def fit_to_width(self) -> None:
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _zoom_by(self, factor: float) -> None:
        current = self.view.zoomFactor()
        if self.view.zoomMode() is not QPdfView.ZoomMode.Custom:
            current = 1.0
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.25, min(4.0, current * factor)))

    def _update_load_state(self, status: QPdfDocument.Status) -> None:
        failed = status is QPdfDocument.Status.Error
        self.error_label.setVisible(failed)
        self.view.setVisible(not failed)
        for button in (
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_width_button,
        ):
            button.setEnabled(not failed)
