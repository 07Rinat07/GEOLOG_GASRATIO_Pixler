from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.ui.interpretation_report_workspace_responsive import (
    InterpretationReportWorkspace as _ResponsiveInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_ResponsiveInterpretationReportWorkspace):
    """Final responsive layout implementation used by the application."""

    _REPORT_SIDE_BY_SIDE_BREAKPOINT = 1_180

    def _build_responsive_workspace(self) -> None:
        super()._build_responsive_workspace()
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Не найден основной layout отчётов интерпретации")

        root.removeWidget(self.main_splitter)
        self.workspace_body = QWidget()
        self.workspace_body.setObjectName("interpretation-workspace-body")
        body_layout = QHBoxLayout(self.workspace_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        self.preview_sidebar = QFrame()
        self.preview_sidebar.setObjectName("interpretation-preview-sidebar")
        self.preview_sidebar.setFixedWidth(196)
        sidebar_layout = QVBoxLayout(self.preview_sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(8)

        self.preview_toggle = QToolButton()
        self.preview_toggle.setObjectName("interpretation-preview-toggle")
        self.preview_toggle.setCheckable(True)
        self.preview_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.preview_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.preview_toggle.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.preview_toggle.setMinimumHeight(42)
        self.preview_toggle.toggled.connect(self._set_report_preview_visible)
        sidebar_layout.addWidget(self.preview_toggle)
        sidebar_layout.addStretch(1)

        self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setCollapsible(0, True)
        self.main_splitter.setCollapsible(1, True)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setHandleWidth(6)

        body_layout.addWidget(self.preview_sidebar)
        body_layout.addWidget(self.main_splitter, 1)
        root.addWidget(self.workspace_body, 1)
        self._set_report_preview_visible(False)

    def _apply_responsive_theme(self) -> None:
        super()._apply_responsive_theme()
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        sidebar_background = "#111923" if dark else "#f3f6fa"
        sidebar_border = "#334155" if dark else "#cbd5e1"
        button_background = "#1e293b" if dark else "#ffffff"
        button_hover = "#26364b" if dark else "#eaf3ff"
        button_checked = "#164e63" if dark else "#dbeafe"
        text = "#e5edf7" if dark else "#172033"
        accent = "#38bdf8" if dark else "#2563eb"
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QFrame#interpretation-preview-sidebar {{
                background: {sidebar_background};
                border: 1px solid {sidebar_border};
                border-radius: 8px;
            }}
            QToolButton#interpretation-preview-toggle {{
                background: {button_background};
                color: {text};
                border: 1px solid {sidebar_border};
                border-left: 4px solid {accent};
                border-radius: 6px;
                padding: 8px 10px;
                font-weight: 600;
                text-align: left;
            }}
            QToolButton#interpretation-preview-toggle:hover {{
                background: {button_hover};
                border-color: {accent};
            }}
            QToolButton#interpretation-preview-toggle:checked {{
                background: {button_checked};
                border-color: {accent};
            }}
            """
        )

    def _set_report_preview_visible(self, visible: bool) -> None:
        self.preview_toggle.setArrowType(
            Qt.ArrowType.LeftArrow if visible else Qt.ArrowType.RightArrow
        )
        self._apply_report_preview_layout(visible)
        if hasattr(self, "page_title"):
            self._retranslate_responsive_controls()

    def _apply_report_preview_layout(self, visible: bool | None = None) -> None:
        if visible is None:
            visible = self.preview_toggle.isChecked()

        if not visible:
            self.configuration_scroll.setVisible(True)
            self.report_panel.setVisible(False)
            self.main_splitter.setSizes([1, 0])
            return

        self.report_panel.setVisible(True)
        if self.width() < self._REPORT_SIDE_BY_SIDE_BREAKPOINT:
            # On narrow windows the preview replaces the settings area instead
            # of squeezing both panes into unreadable columns.
            self.configuration_scroll.setVisible(False)
            self.main_splitter.setSizes([0, max(1, self.width())])
            return

        self.configuration_scroll.setVisible(True)
        available = max(900, self.main_splitter.width())
        controls_width = max(520, int(available * 0.56))
        preview_width = max(420, available - controls_width)
        self.main_splitter.setSizes([controls_width, preview_width])

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if hasattr(self, "preview_toggle"):
            self._apply_report_preview_layout()

    def _rebuild_dexp_panel(self) -> None:
        panel = self.dexp_quality_panel.layout()
        if not isinstance(panel, QHBoxLayout):
            raise RuntimeError("Не найден layout блока качества DEXP")
        while panel.count():
            panel.takeAt(0)
        panel.setContentsMargins(0, 0, 0, 0)
        panel.setSpacing(0)
        self.dexp_quality_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        content = QWidget()
        content.setObjectName("dexp-quality-content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 13, 16, 13)
        content_layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(self.dexp_quality_title)
        header.addStretch(1)
        header.addWidget(self.dexp_details_button)
        content_layout.addLayout(header)
        content_layout.addWidget(self.dexp_quality_summary)
        content_layout.addWidget(self.dexp_quality_progress)
        content_layout.addWidget(self.dexp_quality_reasons)
        panel.addWidget(content)

    def _update_dexp_diagnostics(self) -> None:
        super()._update_dexp_diagnostics()
        diagnostic = self._last_dexp_diagnostic
        if diagnostic is None or diagnostic.total_points <= 0:
            return

        bit_rpm = diagnostic.bit_rpm_mnemonic or self._text(
            "не найден",
            "табылмады",
            "not found",
        )
        mode_line = self._text(
            (
                f"Режимы: ROTARY — {diagnostic.rotary_points}; "
                f"SLIDE — {diagnostic.slide_points}, из них с забойным RPM — "
                f"{diagnostic.slide_points_with_bit_rpm}, без забойного RPM — "
                f"{diagnostic.slide_points_without_bit_rpm}; не бурение — "
                f"{diagnostic.not_drilling_points}; не определён — "
                f"{diagnostic.unknown_mode_points}. Источник RPM долота: {bit_rpm}."
            ),
            (
                f"Режимдер: ROTARY — {diagnostic.rotary_points}; "
                f"SLIDE — {diagnostic.slide_points}, оның ішінде түптік RPM бар — "
                f"{diagnostic.slide_points_with_bit_rpm}, түптік RPM жоқ — "
                f"{diagnostic.slide_points_without_bit_rpm}; бұрғылау жоқ — "
                f"{diagnostic.not_drilling_points}; анықталмаған — "
                f"{diagnostic.unknown_mode_points}. Қашау RPM көзі: {bit_rpm}."
            ),
            (
                f"Modes: ROTARY — {diagnostic.rotary_points}; "
                f"SLIDE — {diagnostic.slide_points}, with downhole RPM — "
                f"{diagnostic.slide_points_with_bit_rpm}, without downhole RPM — "
                f"{diagnostic.slide_points_without_bit_rpm}; not drilling — "
                f"{diagnostic.not_drilling_points}; unknown — "
                f"{diagnostic.unknown_mode_points}. Bit RPM source: {bit_rpm}."
            ),
        )
        self.dexp_quality_summary.setText(
            f"{self.dexp_quality_summary.text()}\n{mode_line}"
        )

    def _reason_text(self, code: str) -> str:
        mode_reasons = {
            "slide_bit_rpm_missing": self._text(
                "слайдирование без забойного RPM",
                "түптік RPM жоқ слайдтау",
                "slide drilling without downhole RPM",
            ),
            "not_drilling": self._text(
                "бурение не выполняется",
                "бұрғылау орындалмайды",
                "not drilling",
            ),
            "drilling_mode_unknown": self._text(
                "режим бурения не определён",
                "бұрғылау режимі анықталмаған",
                "drilling mode is unknown",
            ),
        }
        return mode_reasons.get(code, super()._reason_text(code))

    def _retranslate_responsive_controls(self) -> None:
        super()._retranslate_responsive_controls()
        self.recalculate_all_button.setText(
            self._text(
                "Пересчитать все доступные кривые и открыть планшет",
                "Барлық қолжетімді қисықтарды қайта есептеп, планшетті ашу",
                "Recalculate all available curves and open tablet",
            )
        )
        self.refresh_chart_report_button.setText(
            self._text(
                "Обновить отчёт с графиками",
                "Графиктері бар есепті жаңарту",
                "Refresh report with charts",
            )
        )
        self.dexp_details_button.setToolTip(
            self._text(
                "Показывает интервалы разрывов DEXP, режим ROTARY/SLIDE и сообщает, "
                "где при слайдировании отсутствуют реальные обороты долота.",
                "DEXP үзіліс аралықтарын, ROTARY/SLIDE режимін және слайдтау кезінде "
                "нақты қашау айналымдары жоқ жерлерді көрсетеді.",
                "Shows DEXP gap intervals, ROTARY/SLIDE mode, and slide intervals "
                "where real bit RPM is unavailable.",
            )
        )
        if not hasattr(self, "preview_toggle"):
            return
        self.preview_toggle.setText(
            self._text(
                "Предпросмотр отчёта",
                "Есепті алдын ала қарау",
                "Report preview",
            )
        )
        tooltip = self._text(
            "Показывает или скрывает предварительный просмотр сформированного отчёта. "
            "Скрытие освобождает больше места для настройки и проверки расчётов.",
            "Қалыптастырылған есептің алдын ала көрінісін көрсетеді немесе жасырады. "
            "Жасыру есептеулерді баптау және тексеру үшін көбірек орын босатады.",
            "Shows or hides the generated report preview. Hiding it leaves more room "
            "for calculation setup and quality control.",
        )
        self.preview_toggle.setToolTip(tooltip)
        self.preview_toggle.setStatusTip(tooltip)
        self.preview_toggle.setAccessibleName(self.preview_toggle.text())
        self.preview_toggle.setAccessibleDescription(tooltip)


__all__ = ["InterpretationReportWorkspace"]
