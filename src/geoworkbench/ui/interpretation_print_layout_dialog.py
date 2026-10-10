from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPageLayout
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ReportLegendMode,
    ReportLayoutProfile,
    ReportPageOrientation,
    ReportPrintOrder,
    ReportTrackVisibility,
    ReportChartPanel,
    ReportChartPanelSettings,
    DEFAULT_REPORT_CHART_PANELS,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.window_geometry import fit_window_to_screen


class InterpretationPrintOrder(str, Enum):
    FIRST_TO_LAST = "first-to-last"
    LAST_TO_FIRST = "last-to-first"


@dataclass(frozen=True, slots=True)
class InterpretationPrintLayout:
    orientation: QPageLayout.Orientation
    order: InterpretationPrintOrder
    geology_tracks: InterpretationGeologyTrackSettings = InterpretationGeologyTrackSettings()
    legend_mode: ReportLegendMode = ReportLegendMode.FULL
    layout_profile: ReportLayoutProfile = ReportLayoutProfile.MODERN_OILFIELD
    target_depth_per_page: float = 100.0


class InterpretationPrintLayoutDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        include_order: bool = True,
        initial: InterpretationReportComposition | None = None,
        report_profile: str = "standard",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.include_order = include_order
        self.initial = initial
        self.setModal(True)
        self.setWindowTitle(
            self._text(
                "Макет печати отчёта" if include_order else "Макет PDF-отчёта",
                "Есепті басып шығару макеті" if include_order else "PDF есеп макеті",
                "Report print layout" if include_order else "PDF report layout",
            )
        )

        root = QVBoxLayout(self)
        description = QLabel(
            self._description_text()
        )
        description.setWordWrap(True)
        root.addWidget(description)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem(
            self._text(
                "Книжная — формы и страницы адаптируются по ширине",
                "Кітапша — пішіндер мен беттер еніне бейімделеді",
                "Portrait — forms and pages adapt to the width",
            ),
            QPageLayout.Orientation.Portrait,
        )
        self.orientation_combo.addItem(
            self._text(
                "Альбомная — больше места для графиков и таблиц",
                "Альбомдық — графиктер мен кестелерге көбірек орын",
                "Landscape — more room for charts and tables",
            ),
            QPageLayout.Orientation.Landscape,
        )
        self.order_combo = QComboBox()
        self.order_combo.addItem(
            self._text(
                "С первой страницы к последней",
                "Бірінші беттен соңғы бетке дейін",
                "First page to last page",
            ),
            InterpretationPrintOrder.FIRST_TO_LAST,
        )
        self.order_combo.addItem(
            self._text(
                "С последней страницы к первой",
                "Соңғы беттен бірінші бетке дейін",
                "Last page to first page",
            ),
            InterpretationPrintOrder.LAST_TO_FIRST,
        )
        self.orientation_label = QLabel(
            self._text("Ориентация:", "Бағдар:", "Orientation:")
        )
        self.order_label = QLabel(
            self._text("Порядок:", "Реті:", "Order:")
        )
        form.addRow(self.orientation_label, self.orientation_combo)
        form.addRow(self.order_label, self.order_combo)

        self.cuttings_visibility_combo = self._geology_visibility_combo()
        self.lba_visibility_combo = self._geology_visibility_combo()
        form.addRow(
            QLabel(self._text("Шламограмма:", "Шламограмма:", "Cuttings:")),
            self.cuttings_visibility_combo,
        )
        form.addRow(
            QLabel(self._text("ЛБА:", "ЛБА:", "LBA:")),
            self.lba_visibility_combo,
        )
        self.legend_mode_combo = QComboBox()
        self.legend_mode_combo.addItem(
            self._text("Полная", "Толық", "Full"),
            ReportLegendMode.FULL,
        )
        self.legend_mode_combo.addItem(
            self._text("Компактная", "Ықшам", "Compact"),
            ReportLegendMode.COMPACT,
        )
        self.legend_mode_combo.addItem(
            self._text("Скрыть", "Жасыру", "Hide"),
            ReportLegendMode.HIDE,
        )
        form.addRow(
            QLabel(self._text("Легенды:", "Аңыздар:", "Legends:")),
            self.legend_mode_combo,
        )
        # Explicit overview choice: a wider depth interval per A4 chart page
        # reduces sheet count, but never drops source LAS samples or changes QC.
        self.chart_density_combo = QComboBox()
        self.chart_density_combo.setObjectName("report-chart-depth-per-page")
        for caption, depth in (
            (self._text("Детально — около 100 единиц глубины / лист",
                        "Толық — шамамен 100 тереңдік бірлігі / бет",
                        "Detailed — about 100 depth units / page"), 100.0),
            (self._text("Обзор — около 250 единиц глубины / лист",
                        "Шолу — шамамен 250 тереңдік бірлігі / бет",
                        "Overview — about 250 depth units / page"), 250.0),
            (self._text("Компактно — около 500 единиц глубины / лист",
                        "Ықшам — шамамен 500 тереңдік бірлігі / бет",
                        "Compact — about 500 depth units / page"), 500.0),
        ):
            self.chart_density_combo.addItem(caption, depth)
        form.addRow(
            QLabel(self._text("Глубинный масштаб графиков:",
                             "Графиктердің тереңдік масштабы:",
                             "Chart depth density:")),
            self.chart_density_combo,
        )
        self.layout_profile_combo = QComboBox()
        self.layout_profile_combo.addItem(
            self._text(
                "Modern Oilfield — стандартный профиль",
                "Modern Oilfield — стандартты профиль",
                "Modern Oilfield — standard profile",
            ),
            ReportLayoutProfile.MODERN_OILFIELD,
        )
        form.addRow(
            QLabel(self._text("Профиль макета:", "Макет профилі:", "Layout profile:")),
            self.layout_profile_combo,
        )
        self.summary_checkbox = QCheckBox(
            self._text("Включить", "Қосу", "Include")
        )
        self.conclusion_checkbox = QCheckBox(
            self._text("Включить", "Қосу", "Include")
        )
        self.summary_checkbox.setChecked(True)
        self.conclusion_checkbox.setChecked(True)
        form.addRow(
            QLabel(
                self._text(
                    "Краткое резюме:",
                    "Қысқаша түйін:",
                    "Executive summary:",
                )
            ),
            self.summary_checkbox,
        )
        form.addRow(
            QLabel(self._text("Заключение:", "Қорытынды:", "Conclusion:")),
            self.conclusion_checkbox,
        )
        self.order_label.setVisible(include_order)
        self.order_combo.setVisible(include_order)
        self.chart_panel_list = QListWidget()
        self.chart_panel_list.setObjectName("report-chart-panels")
        self.chart_panel_list.setMinimumHeight(110)
        self.chart_panel_list.setMaximumHeight(140)
        settings = initial.chart_panels if initial else DEFAULT_REPORT_CHART_PANELS
        captions = {
            ReportChartPanel.TOTAL: self._text("Общий газ", "Жалпы газ", "Total gas"),
            ReportChartPanel.RATIOS: self._text("Газовые отношения", "Газ қатынастары", "Gas ratios"),
            ReportChartPanel.DRILLING: self._text("Параметры бурения", "Бұрғылау параметрлері", "Drilling parameters"),
            ReportChartPanel.OPUS: self._text("Показатели OPUS", "OPUS көрсеткіштері", "OPUS indicators"),
        }
        for panel in settings.order:
            item = QListWidgetItem(captions[panel], self.chart_panel_list)
            item.setData(Qt.ItemDataRole.UserRole, panel.value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked if panel in settings.hidden else Qt.CheckState.Checked)
            if (panel is ReportChartPanel.OPUS and report_profile != "opus") or (
                panel is ReportChartPanel.DRILLING and report_profile == "opus"
            ):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        panel_box = QWidget()
        panel_layout = QVBoxLayout(panel_box)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(self.chart_panel_list)
        moves = QHBoxLayout()
        for offset, caption in (
            (-1, self._text("Выше", "Жоғары", "Move up")),
            (1, self._text("Ниже", "Төмен", "Move down")),
        ):
            button = QPushButton(caption)
            button.setObjectName("chart-panel-up" if offset < 0 else "chart-panel-down")
            button.clicked.connect(lambda _checked=False, step=offset: self._move_chart_panel(step))
            moves.addWidget(button)
        panel_layout.addLayout(moves)
        form.addRow(self._text("Графические колонки:", "Графикалық бағандар:", "Chart columns:"), panel_box)
        self._apply_initial(initial)
        form_widget = QWidget()
        form_widget.setLayout(form)
        for combo in form_widget.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(18)
        for label in form_widget.findChildren(QLabel):
            label.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form_widget)
        root.addWidget(scroll, 1)

        note = QLabel(self._note_text())
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        fit_window_to_screen(
            self,
            preferred=QSize(620, 620),
            minimum=QSize(340, 240),
        )

    def selected_layout(self) -> InterpretationPrintLayout:
        orientation = self.orientation_combo.currentData()
        order_data = self.order_combo.currentData()
        if not isinstance(orientation, QPageLayout.Orientation):
            orientation = QPageLayout.Orientation.Portrait
        if self.include_order:
            try:
                order = InterpretationPrintOrder(order_data)
            except (TypeError, ValueError):
                order = InterpretationPrintOrder.FIRST_TO_LAST
        else:
            order = InterpretationPrintOrder.FIRST_TO_LAST
        cuttings_data = self.cuttings_visibility_combo.currentData()
        lba_data = self.lba_visibility_combo.currentData()
        try:
            cuttings = GeologyTrackVisibility(cuttings_data)
        except (TypeError, ValueError):
            cuttings = GeologyTrackVisibility.AUTO
        try:
            lba = GeologyTrackVisibility(lba_data)
        except (TypeError, ValueError):
            lba = GeologyTrackVisibility.AUTO
        legend_data = self.legend_mode_combo.currentData()
        try:
            legend_mode = ReportLegendMode(legend_data)
        except (TypeError, ValueError):
            legend_mode = ReportLegendMode.FULL
        layout_profile_data = self.layout_profile_combo.currentData()
        try:
            layout_profile = ReportLayoutProfile(layout_profile_data)
        except (TypeError, ValueError):
            layout_profile = ReportLayoutProfile.MODERN_OILFIELD
        return InterpretationPrintLayout(
            orientation=orientation,
            order=order,
            geology_tracks=InterpretationGeologyTrackSettings(
                cuttings=cuttings,
                lba=lba,
            ),
            legend_mode=legend_mode,
            layout_profile=layout_profile,
            target_depth_per_page=float(self.chart_density_combo.currentData() or 100.0),
        )

    def selected_composition(self) -> InterpretationReportComposition:
        layout = self.selected_layout()
        orientation = (
            ReportPageOrientation.LANDSCAPE
            if layout.orientation == QPageLayout.Orientation.Landscape
            else ReportPageOrientation.PORTRAIT
        )
        if self.include_order:
            print_order = (
                ReportPrintOrder.LAST_TO_FIRST
                if layout.order is InterpretationPrintOrder.LAST_TO_FIRST
                else ReportPrintOrder.FIRST_TO_LAST
            )
        elif self.initial is not None:
            print_order = self.initial.print_order
        else:
            print_order = ReportPrintOrder.FIRST_TO_LAST
        base = self.initial or InterpretationReportComposition()
        return replace(
            base,
            orientation=orientation,
            print_order=print_order,
            cuttings=ReportTrackVisibility(layout.geology_tracks.cuttings.value),
            lba=ReportTrackVisibility(layout.geology_tracks.lba.value),
            legend_mode=layout.legend_mode,
            layout_profile=layout.layout_profile,
            show_summary=self.summary_checkbox.isChecked(),
            show_conclusion=self.conclusion_checkbox.isChecked(),
            chart_panels=self._selected_chart_panels(),
        )

    def _move_chart_panel(self, offset: int) -> None:
        row = self.chart_panel_list.currentRow()
        target = row + offset
        if row < 0 or not 0 <= target < self.chart_panel_list.count():
            return
        item = self.chart_panel_list.takeItem(row)
        self.chart_panel_list.insertItem(target, item)
        self.chart_panel_list.setCurrentRow(target)

    def _selected_chart_panels(self) -> ReportChartPanelSettings:
        order: list[ReportChartPanel] = []
        hidden: list[ReportChartPanel] = []
        for row in range(self.chart_panel_list.count()):
            item = self.chart_panel_list.item(row)
            panel = ReportChartPanel(item.data(Qt.ItemDataRole.UserRole))
            order.append(panel)
            if item.checkState() == Qt.CheckState.Unchecked:
                hidden.append(panel)
        return ReportChartPanelSettings(tuple(order), tuple(hidden))

    def _apply_initial(
        self,
        initial: InterpretationReportComposition | None,
    ) -> None:
        if initial is None:
            return
        orientation = (
            QPageLayout.Orientation.Landscape
            if initial.orientation is ReportPageOrientation.LANDSCAPE
            else QPageLayout.Orientation.Portrait
        )
        order = (
            InterpretationPrintOrder.LAST_TO_FIRST
            if initial.print_order is ReportPrintOrder.LAST_TO_FIRST
            else InterpretationPrintOrder.FIRST_TO_LAST
        )
        self._set_combo_data(self.orientation_combo, orientation)
        self._set_combo_data(self.order_combo, order)
        self._set_combo_data(
            self.cuttings_visibility_combo,
            GeologyTrackVisibility(initial.cuttings.value),
        )
        self._set_combo_data(
            self.lba_visibility_combo,
            GeologyTrackVisibility(initial.lba.value),
        )
        self._set_combo_data(self.legend_mode_combo, initial.legend_mode)
        self._set_combo_data(self.layout_profile_combo, initial.layout_profile)
        self._set_combo_data(self.chart_density_combo, 100.0)
        self.summary_checkbox.setChecked(initial.show_summary)
        self.conclusion_checkbox.setChecked(initial.show_conclusion)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _geology_visibility_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem(
            self._text(
                "Авто — показывать только при наличии данных",
                "Авто — дерек болса ғана көрсету",
                "Auto — show only when data are available",
            ),
            GeologyTrackVisibility.AUTO,
        )
        combo.addItem(
            self._text(
                "Показать — всегда резервировать колонку",
                "Көрсету — бағанды әрқашан қалдыру",
                "Show — always reserve the track",
            ),
            GeologyTrackVisibility.SHOW,
        )
        combo.addItem(
            self._text(
                "Скрыть — не печатать колонку",
                "Жасыру — бағанды баспау",
                "Hide — do not print the track",
            ),
            GeologyTrackVisibility.HIDE,
        )
        return combo

    def _description_text(self) -> str:
        if not self.include_order:
            return self._text(
                "Выберите ориентацию PDF. Титульный лист, графики, таблицы и "
                "страницы продолжения будут перестроены под выбранный формат.",
                "PDF бағдарын таңдаңыз. Титулдық бет, графиктер, кестелер және "
                "жалғастыру беттері таңдалған пішімге қайта құрылады.",
                "Choose the PDF orientation. The cover, charts, tables, and "
                "continuation pages will be rebuilt for the selected format.",
            )
        return self._text(
            "Сначала выберите макет отчёта. Диапазон страниц, принтер, "
            "число копий и свойства Epson будут доступны в следующем "
            "системном окне Windows.",
            "Алдымен есеп макетін таңдаңыз. Бет ауқымы, принтер, көшірме "
            "саны және Epson қасиеттері келесі Windows жүйелік терезесінде "
            "қолжетімді болады.",
            "Choose the report layout first. Page range, printer, copy count, "
            "and Epson properties remain available in the next Windows dialog.",
        )

    def _note_text(self) -> str:
        if not self.include_order:
            return self._text(
                "Книжная ориентация удобнее для последовательного чтения; "
                "альбомная оставляет больше ширины для графиков и таблиц.",
                "Кітапша бағдары ретімен оқуға ыңғайлы; альбомдық бағдар "
                "графиктер мен кестелерге көбірек ен қалдырады.",
                "Portrait is easier for sequential reading; landscape leaves "
                "more width for charts and tables.",
            )
        return self._text(
            "По умолчанию используется книжная ориентация и печать с "
            "первой страницы. Выбор диапазона 1–2 будет отправлять Epson "
            "только две выбранные страницы.",
            "Әдепкіде кітапша бағыты және бірінші беттен басып шығару "
            "қолданылады. 1–2 ауқымы Epson принтеріне тек екі бетті жібереді.",
            "Portrait and first-to-last are the defaults. Selecting pages "
            "1–2 sends only those two pages to Epson.",
        )

    def _text(self, ru: str, kk: str, en: str) -> str:
        if self.language is AppLanguage.KK:
            return kk
        if self.language is AppLanguage.EN:
            return en
        return ru


__all__ = [
    "InterpretationPrintLayout",
    "InterpretationPrintLayoutDialog",
    "InterpretationPrintOrder",
]
