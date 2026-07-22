from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSize, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from geoworkbench import __version__
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.branding import logo_pixmap
from geoworkbench.ui.drilling_animation import DrillingAnimation


class StartupSplash(QWidget):
    """Frameless branded startup surface with a live drilling rig."""

    def __init__(self, language: AppLanguage) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.localizer = Localizer.create(language)
        self.setObjectName("startupSplash")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self._adaptive_size())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        card = QFrame(self)
        card.setObjectName("splashCard")
        outer.addWidget(card)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(38, 34, 30, 28)
        layout.setSpacing(28)

        information = QVBoxLayout()
        information.setSpacing(8)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(14)
        logo = QLabel(card)
        logo.setObjectName("splashLogo")
        logo.setPixmap(logo_pixmap(82))
        logo.setFixedSize(88, 88)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(1)
        product = QLabel("GEOLOG", card)
        product.setObjectName("splashProduct")
        suite = QLabel("GASRATIO@Pixler", card)
        suite.setObjectName("splashSuite")
        names.addStretch(1)
        names.addWidget(product)
        names.addWidget(suite)
        names.addStretch(1)
        brand_row.addLayout(names, 1)
        information.addLayout(brand_row)

        tagline = QLabel(self.localizer.text("startup.tagline"), card)
        tagline.setObjectName("splashTagline")
        tagline.setWordWrap(True)
        information.addWidget(tagline)
        specialization = QLabel(self.localizer.text("startup.specialization"), card)
        specialization.setObjectName("splashSpecialization")
        specialization.setWordWrap(True)
        information.addWidget(specialization)
        information.addStretch(1)

        self.stage_label = QLabel(card)
        self.stage_label.setObjectName("splashStage")
        information.addWidget(self.stage_label)
        self.progress = QProgressBar(card)
        self.progress.setObjectName("splashProgress")
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        information.addWidget(self.progress)
        version = QLabel(
            self.localizer.text("startup.version", version=__version__), card
        )
        version.setObjectName("splashVersion")
        information.addWidget(version)
        layout.addLayout(information, 3)

        self.rig = DrillingAnimation(dark=True, parent=card)
        self.rig.setObjectName("splashRig")
        self.rig.setFixedSize(280, 280)
        self.rig.setVisible(self.width() >= 650 and self.height() >= 370)
        layout.addWidget(self.rig, 2, Qt.AlignmentFlag.AlignCenter)

        self.setStyleSheet(
            "QFrame#splashCard { background: #071a2d; border: 1px solid #17456a; "
            "border-radius: 18px; }"
            "QLabel#splashLogo { background: white; border: 2px solid #d99a24; "
            "border-radius: 12px; padding: 2px; }"
            "QLabel#splashProduct { color: white; font-size: 30px; font-weight: 900; "
            "letter-spacing: 2px; }"
            "QLabel#splashSuite { color: #f5b942; font-size: 16px; font-weight: 800; }"
            "QLabel#splashTagline { color: #dcecff; font-size: 16px; font-weight: 650; "
            "margin-top: 12px; }"
            "QLabel#splashSpecialization { color: #80bce8; font-size: 12px; }"
            "QLabel#splashStage { color: #dbeafe; font-size: 11px; }"
            "QLabel#splashVersion { color: #7396b3; font-size: 10px; margin-top: 3px; }"
            "QProgressBar#splashProgress { background: #17364f; border: 0; "
            "border-radius: 3px; }"
            "QProgressBar#splashProgress::chunk { background: #f5b942; border-radius: 3px; }"
        )
        self.set_stage(self.localizer.text("startup.stage.prepare"), 12)
        self._centre_on_active_screen()
        self._fade: QPropertyAnimation | None = None

    def _adaptive_size(self) -> QSize:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return QSize(760, 410)
        available = screen.availableGeometry()
        return QSize(
            max(320, min(760, available.width() - 48)),
            max(280, min(410, available.height() - 48)),
        )

    def _centre_on_active_screen(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        target = QRect(0, 0, self.width(), self.height())
        target.moveCenter(available.center())
        self.move(target.topLeft())

    def set_stage(self, text: str, progress: int) -> None:
        self.stage_label.setText(text)
        self.progress.setValue(max(0, min(100, progress)))
        self.repaint()

    def finish(self) -> None:
        self.set_stage(self.localizer.text("startup.stage.ready"), 100)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self.close)
        self._fade.start()
