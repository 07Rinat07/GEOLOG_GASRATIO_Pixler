"""Build deterministic REL-03/CUT-03 content for PDF and physical-print acceptance.

The sheet deliberately uses the production ``TabletAnnotationItem`` image painter
for its embedded cuttings-photo fixture. The raster itself is deterministic test
content; the embedding, scaling and QWidget/PDF/printer paint path are production
code.
"""

from __future__ import annotations

from typing import Any

PRODUCTION_IMAGE_RENDERER = (
    "geoworkbench.tablet.annotation_graphics.TabletAnnotationItem"
)
CUTTINGS_ASSET_REF = "acceptance://deterministic-cuttings-photo"


def build_physical_acceptance_widget(case: Any):
    """Return the operator sheet used by automated PDF and physical printer gates."""

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )

    widget = QWidget()
    widget.setObjectName("physicalAcceptanceSheet")
    widget.resize(int(case.widget_width), int(case.widget_height))
    widget.setStyleSheet(
        "QWidget#physicalAcceptanceSheet { background: white; color: black; }"
    )
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(28, 28, 28, 28)
    layout.setSpacing(12)

    heading = QLabel(
        "GEOLOG GASRATIO@Pixler — REL-03 / CUT-03\n"
        "Custom heading: Описание пород / Тау жыныстарының сипаттамасы\n"
        f"Case: {case.case_id}"
    )
    heading.setObjectName("physicalAcceptanceCustomHeading")
    heading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    heading.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    heading.setStyleSheet(
        "QLabel { padding: 10px; border: 2px solid #202020; background: white; color: black; }"
    )
    layout.addWidget(heading)

    interval = QLabel(
        "1703.28 m  |  INTERPRETATION / ИНТЕРПРЕТАЦИЯ  |  1753.28 m"
    )
    interval.setObjectName("physicalAcceptanceIntervalBounds")
    interval.setAlignment(Qt.AlignmentFlag.AlignCenter)
    interval.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    interval.setStyleSheet(
        "QLabel { padding: 7px; border: 2px solid #111827; background: #f8fafc; color: #111827; }"
    )
    layout.addWidget(interval)

    rich_text = QTextBrowser()
    rich_text.setObjectName("physicalAcceptanceRichText")
    rich_text.setOpenExternalLinks(False)
    rich_text.setFont(QFont("Segoe UI", 11))
    rich_text.setHtml(
        "<p><b>1703.28–1753.28 m.</b> Доломиты светло-серые с желтоватым оттенком, "
        "<i>скрытокристаллические</i>, массивные и микротрещиноватые. "
        "Тонкие прослои и признаки нефтенасыщенности должны переноситься без обрезания.</p>"
        "<p><b>Қазақша:</b> ұзын сипаттама жолдарға дұрыс бөлініп, интервал "
        "шекарасынан шықпауы тиіс. <b>English:</b> long rich text, emphasis and "
        "continuation must remain readable on every printed page.</p>"
        "<ul><li>bold / italic formatting survives;</li>"
        "<li>interval boundaries remain visible;</li>"
        "<li>no text is clipped by driver margins.</li></ul>"
    )
    rich_text.setStyleSheet(
        "QTextBrowser { border: 2px solid #202020; background: white; color: black; padding: 8px; }"
    )
    layout.addWidget(rich_text, 3)

    media_row = QHBoxLayout()
    media_row.setSpacing(12)
    photo = ProductionAnnotationImageWidget()
    photo.setObjectName("physicalAcceptanceProductionCuttingsImage")
    media_row.addWidget(photo, 3)

    lba = QLabel(
        "LBA\n"
        "Цвет: светло-коричневый\n"
        "Битум: 2\n"
        "Fluor.: слабая\n"
        "Score: 2/5"
    )
    lba.setObjectName("physicalAcceptanceSimpleLba")
    lba.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    lba.setFont(QFont("Segoe UI", 10))
    lba.setStyleSheet(
        "QLabel { padding: 10px; border: 2px solid #202020; background: #fff7ed; color: black; }"
    )
    media_row.addWidget(lba, 2)
    layout.addLayout(media_row, 3)

    colors = QHBoxLayout()
    for name, css_color in (
        ("RED", "#dc2626"),
        ("GREEN", "#16a34a"),
        ("BLUE", "#2563eb"),
        ("BLACK", "#111827"),
    ):
        swatch = QLabel(name)
        swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        swatch.setMinimumHeight(34)
        swatch.setStyleSheet(
            f"QLabel {{ background: {css_color}; color: white; border: 1px solid #000; "
            "font-weight: 700; }}"
        )
        colors.addWidget(swatch)
    layout.addLayout(colors)

    footer = QLabel(
        "Operator check: full content · color · driver margins · no paper/feed/scaling warning"
    )
    footer.setObjectName("physicalAcceptanceDriverChecks")
    footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
    footer.setStyleSheet(
        "QLabel { padding: 6px; border: 1px solid #475569; background: white; color: black; }"
    )
    layout.addWidget(footer)
    return widget


class ProductionAnnotationImageWidget:
    """Factory proxy kept import-light until a Qt application exists."""

    def __new__(cls):
        from PySide6.QtWidgets import QWidget

        class _Widget(QWidget):
            def __init__(self) -> None:
                super().__init__()
                self.setMinimumSize(360, 170)
                self._annotation_item = _build_annotation_item()

            @property
            def annotation_item(self):
                return self._annotation_item

            def paintEvent(self, event) -> None:  # noqa: N802
                del event
                from PySide6.QtGui import QPainter
                from PySide6.QtWidgets import QStyleOptionGraphicsItem

                painter = QPainter(self)
                try:
                    painter.fillRect(self.rect(), Qt.GlobalColor.white)
                    box = self._annotation_item.box_rect()
                    dx = max(0.0, (self.width() - box.width()) / 2.0 - box.left())
                    dy = max(0.0, (self.height() - box.height()) / 2.0 - box.top())
                    painter.translate(dx, dy)
                    self._annotation_item.paint(
                        painter,
                        QStyleOptionGraphicsItem(),
                        self,
                    )
                finally:
                    painter.end()

        from PySide6.QtCore import Qt

        return _Widget()


def _build_annotation_item():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap

    from geoworkbench.project.annotation_schema import (
        AnnotationAnchor,
        AnnotationKind,
        AnnotationRecord,
        AnnotationStyle,
    )
    from geoworkbench.tablet.annotation_graphics import TabletAnnotationItem

    pixmap = QPixmap(480, 190)
    pixmap.fill(QColor("#d6c3a5"))
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fragments = (
            (54, 46, 34, "#8b6f47"),
            (118, 76, 26, "#b08d57"),
            (180, 45, 38, "#6f5b3e"),
            (248, 82, 31, "#c3a76d"),
            (326, 52, 36, "#725640"),
            (399, 89, 28, "#a58255"),
            (89, 138, 25, "#604b3b"),
            (211, 135, 29, "#94714e"),
            (355, 139, 32, "#b79a6a"),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        for x, y, radius, color in fragments:
            painter.setBrush(QColor(color))
            painter.drawEllipse(x - radius, y - radius // 2, radius * 2, radius)
        painter.setPen(QColor("#111827"))
        painter.drawText(12, 22, "Deterministic cuttings-photo fixture")
    finally:
        painter.end()

    record = AnnotationRecord(
        annotation_id="release-physical-cuttings-photo",
        kind=AnnotationKind.IMAGE,
        anchor=AnnotationAnchor.TRACK,
        text="Фото шлама / Cuttings photo",
        track_id="interpretation",
        depth=1728.28,
        axis_value=None,
        axis_id=None,
        parameter_mnemonic=None,
        parameter_value=None,
        unit="m",
        x_fraction=0.5,
        offset_x=4.0,
        offset_y=4.0,
        width=520.0,
        height=160.0,
        style=AnnotationStyle(
            font_family="Segoe UI",
            font_size=9.0,
            text_color="#111827",
            fill_color="#ffffff",
            border_color="#202020",
            border_width=2.0,
            corner_radius=2.0,
            padding=6.0,
            shadow=False,
        ),
        asset_ref=CUTTINGS_ASSET_REF,
        visible=True,
        locked=True,
        print_enabled=True,
    )
    return TabletAnnotationItem(record, pixmap=pixmap, print_mode=True)
