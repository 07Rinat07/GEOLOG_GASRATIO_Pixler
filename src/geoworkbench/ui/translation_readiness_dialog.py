from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.translation_readiness import (
    TranslationReadinessItem,
    TranslationReadinessSummary,
)
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.translation_status_controller import TranslationStatusController
from geoworkbench.project.well_translation_readiness_controller import (
    WellTranslationReadinessController,
)
from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES
from geoworkbench.ui.window_geometry import fit_window_to_screen


_TEXTS: dict[AppLanguage, dict[str, str]] = {
    AppLanguage.RU: {
        "title": "Готовность переводов",
        "target_language": "Язык перевода",
        "depth_filter": "Ограничить по диапазону MD",
        "top_depth": "От, м",
        "bottom_depth": "До, м",
        "include_reviewed": "Показывать проверенные",
        "refresh": "Обновить",
        "review_selected": "Подтвердить выбранный перевод",
        "close": "Закрыть",
        "status": "Статус",
        "language": "Язык",
        "field": "Поле",
        "interval": "Интервал MD",
        "global": "Вся скважина",
        "ready": "Готово к выпуску",
        "not_ready": "Требуется доработка",
        "summary": (
            "Всего: {total} · Проверено: {reviewed} · Нет перевода: {missing} · "
            "Черновики: {draft} · Устарело: {stale}"
        ),
        "invalid_range": "Конец диапазона MD должен быть больше начала.",
        "no_well": "Сначала выберите скважину.",
        "unknown_error": "Не удалось рассчитать готовность переводов.",
        "state_missing": "Нет перевода",
        "state_draft": "Черновик",
        "state_stale": "Требует обновления",
        "state_reviewed": "Проверено",
        "lithology.description": "Литология — описание",
        "cuttings.description": "Шлам — описание",
        "cuttings.lba_description": "Шлам — ЛБА",
        "cuttings.analysis_interpretation": "Шлам — интерпретация анализа",
        "stratigraphy.name": "Стратиграфия — название",
        "stratigraphy.description": "Стратиграфия — описание",
        "interpretation.name": "Интерпретация — название",
        "interpretation.description": "Интерпретация — описание",
        "interpretation.interval_label": "Интервал интерпретации — название",
        "interpretation.interval_comment": "Интервал интерпретации — комментарий",
    },
    AppLanguage.KK: {
        "title": "Аудармалардың дайындығы",
        "target_language": "Аударма тілі",
        "depth_filter": "MD аралығымен шектеу",
        "top_depth": "Бастап, м",
        "bottom_depth": "Дейін, м",
        "include_reviewed": "Тексерілгендерді көрсету",
        "refresh": "Жаңарту",
        "review_selected": "Таңдалған аударманы тексерілген деп белгілеу",
        "close": "Жабу",
        "status": "Күй",
        "language": "Тіл",
        "field": "Өріс",
        "interval": "MD аралығы",
        "global": "Бүкіл ұңғыма",
        "ready": "Шығаруға дайын",
        "not_ready": "Толықтыру қажет",
        "summary": (
            "Барлығы: {total} · Тексерілді: {reviewed} · Аударма жоқ: {missing} · "
            "Жобалар: {draft} · Ескірген: {stale}"
        ),
        "invalid_range": "MD аралығының соңы басынан үлкен болуы керек.",
        "no_well": "Алдымен ұңғыманы таңдаңыз.",
        "unknown_error": "Аударма дайындығын есептеу мүмкін болмады.",
        "state_missing": "Аударма жоқ",
        "state_draft": "Жоба",
        "state_stale": "Жаңарту қажет",
        "state_reviewed": "Тексерілген",
        "lithology.description": "Литология — сипаттама",
        "cuttings.description": "Шлам — сипаттама",
        "cuttings.lba_description": "Шлам — ЛБА",
        "cuttings.analysis_interpretation": "Шлам — талдауды интерпретациялау",
        "stratigraphy.name": "Стратиграфия — атауы",
        "stratigraphy.description": "Стратиграфия — сипаттама",
        "interpretation.name": "Интерпретация — атауы",
        "interpretation.description": "Интерпретация — сипаттама",
        "interpretation.interval_label": "Интерпретация аралығы — атауы",
        "interpretation.interval_comment": "Интерпретация аралығы — түсініктеме",
    },
    AppLanguage.EN: {
        "title": "Translation readiness",
        "target_language": "Translation language",
        "depth_filter": "Limit to MD range",
        "top_depth": "From, m",
        "bottom_depth": "To, m",
        "include_reviewed": "Show reviewed",
        "refresh": "Refresh",
        "review_selected": "Mark selected translation reviewed",
        "close": "Close",
        "status": "Status",
        "language": "Language",
        "field": "Field",
        "interval": "MD interval",
        "global": "Whole well",
        "ready": "Ready for release",
        "not_ready": "Needs work",
        "summary": (
            "Total: {total} · Reviewed: {reviewed} · Missing: {missing} · "
            "Draft: {draft} · Stale: {stale}"
        ),
        "invalid_range": "The end of the MD range must be greater than the start.",
        "no_well": "Select a well first.",
        "unknown_error": "Translation readiness could not be calculated.",
        "state_missing": "Missing",
        "state_draft": "Draft",
        "state_stale": "Stale",
        "state_reviewed": "Reviewed",
        "lithology.description": "Lithology — description",
        "cuttings.description": "Cuttings — description",
        "cuttings.lba_description": "Cuttings — LBA",
        "cuttings.analysis_interpretation": "Cuttings — analysis interpretation",
        "stratigraphy.name": "Stratigraphy — name",
        "stratigraphy.description": "Stratigraphy — description",
        "interpretation.name": "Interpretation — name",
        "interpretation.description": "Interpretation — description",
        "interpretation.interval_label": "Interpretation interval — label",
        "interpretation.interval_comment": "Interpretation interval — comment",
    },
}

_STATE_KEYS = {
    TranslationState.MISSING: "state_missing",
    TranslationState.DRAFT: "state_draft",
    TranslationState.STALE: "state_stale",
    TranslationState.REVIEWED: "state_reviewed",
}


class TranslationReadinessDialog(QDialog):
    """WELL-04 readiness projection with an explicit review command."""

    def __init__(
        self,
        controller: WellTranslationReadinessController,
        parent: QWidget | None = None,
        *,
        status_controller: TranslationStatusController | None = None,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.status_controller = status_controller or TranslationStatusController(
            controller.session
        )
        if self.status_controller.session is not controller.session:
            raise ValueError("Контроллеры готовности и статусов должны использовать одну сессию")
        self.language = language
        self._last_summary: TranslationReadinessSummary | None = None

        self.setObjectName("translationReadinessDialog")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        fit_window_to_screen(
            self,
            preferred=QSize(940, 620),
            minimum=QSize(620, 420),
        )

        self.target_language_label = QLabel(self)
        self.target_language_combo = QComboBox(self)
        for target_language in AppLanguage:
            self.target_language_combo.addItem(
                LANGUAGE_NAMES[target_language],
                target_language.value,
            )

        self.depth_filter_checkbox = QCheckBox(self)
        self.top_depth_label = QLabel(self)
        self.bottom_depth_label = QLabel(self)
        self.top_depth_spin = self._depth_spin()
        self.bottom_depth_spin = self._depth_spin()
        self.bottom_depth_spin.setValue(5_000.0)

        self.include_reviewed_checkbox = QCheckBox(self)
        self.refresh_button = QPushButton(self)
        self.review_button = QPushButton(self)
        self.review_button.setEnabled(False)
        self.readiness_label = QLabel(self)
        self.summary_label = QLabel(self)
        self.message_label = QLabel(self)
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(False)

        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("translationReadinessTable")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        filters = QFormLayout()
        filters.addRow(self.target_language_label, self.target_language_combo)
        depth_row = QHBoxLayout()
        depth_row.addWidget(self.top_depth_label)
        depth_row.addWidget(self.top_depth_spin)
        depth_row.addWidget(self.bottom_depth_label)
        depth_row.addWidget(self.bottom_depth_spin)
        depth_container = QWidget(self)
        depth_container.setLayout(depth_row)
        filters.addRow(self.depth_filter_checkbox, depth_container)
        filters.addRow(self.include_reviewed_checkbox)

        header = QHBoxLayout()
        header.addLayout(filters, 1)
        header.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignBottom)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.readiness_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.message_label)
        layout.addWidget(self.table, 1)
        footer = QHBoxLayout()
        footer.addWidget(self.review_button)
        footer.addStretch(1)
        footer.addWidget(buttons)
        layout.addLayout(footer)

        self.depth_filter_checkbox.toggled.connect(self._sync_depth_controls)
        self.target_language_combo.currentIndexChanged.connect(self.refresh)
        self.include_reviewed_checkbox.toggled.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.review_button.clicked.connect(self.review_selected)
        self.table.itemSelectionChanged.connect(self._sync_review_action)
        self.top_depth_spin.editingFinished.connect(self._refresh_if_depth_enabled)
        self.bottom_depth_spin.editingFinished.connect(self._refresh_if_depth_enabled)

        self._sync_depth_controls(False)
        self.set_language(language)
        self.refresh()

    @staticmethod
    def _depth_spin() -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(-1_000_000.0, 1_000_000.0)
        widget.setDecimals(2)
        widget.setSingleStep(10.0)
        widget.setSuffix(" m")
        return widget

    @property
    def last_summary(self) -> TranslationReadinessSummary | None:
        return self._last_summary

    def set_language(self, language: AppLanguage) -> None:
        self.language = language
        texts = _TEXTS[language]
        self.setWindowTitle(texts["title"])
        self.target_language_label.setText(texts["target_language"])
        self.depth_filter_checkbox.setText(texts["depth_filter"])
        self.top_depth_label.setText(texts["top_depth"])
        self.bottom_depth_label.setText(texts["bottom_depth"])
        self.include_reviewed_checkbox.setText(texts["include_reviewed"])
        self.refresh_button.setText(texts["refresh"])
        self.review_button.setText(texts["review_selected"])
        self.close_button.setText(texts["close"])
        self.table.setHorizontalHeaderLabels(
            [
                texts["status"],
                texts["language"],
                texts["field"],
                texts["interval"],
            ]
        )
        self.target_language_combo.setAccessibleName(texts["target_language"])
        self.top_depth_spin.setAccessibleName(texts["top_depth"])
        self.bottom_depth_spin.setAccessibleName(texts["bottom_depth"])
        self.refresh()

    def selected_target_language(self) -> str:
        value = self.target_language_combo.currentData()
        return str(value)

    def selected_depth_range(self) -> tuple[float, float] | None:
        if not self.depth_filter_checkbox.isChecked():
            return None
        top = float(self.top_depth_spin.value())
        bottom = float(self.bottom_depth_spin.value())
        if bottom <= top:
            raise ValueError(_TEXTS[self.language]["invalid_range"])
        return top, bottom

    def refresh(self, *_args: object) -> None:
        self._clear_message()
        try:
            depth_range = self.selected_depth_range()
            summary = self.controller.summarize(
                target_languages=[self.selected_target_language()],
                depth_range=depth_range,
                include_reviewed=self.include_reviewed_checkbox.isChecked(),
            )
        except ValueError as exc:
            self._show_error(str(exc))
            return
        except RuntimeError:
            self._show_error(_TEXTS[self.language]["no_well"])
            return
        self._last_summary = summary
        self._populate(summary)
        self._sync_review_action()

    def _populate(self, summary: TranslationReadinessSummary) -> None:
        texts = _TEXTS[self.language]
        self.readiness_label.setText(
            texts["ready"] if summary.is_ready else texts["not_ready"]
        )
        self.summary_label.setText(
            texts["summary"].format(
                total=summary.total_required,
                reviewed=summary.reviewed_count,
                missing=summary.missing_count,
                draft=summary.draft_count,
                stale=summary.stale_count,
            )
        )

        self.table.setRowCount(len(summary.items))
        for row, item in enumerate(summary.items):
            state_item = QTableWidgetItem(texts[_STATE_KEYS[item.state]])
            language_item = QTableWidgetItem(
                LANGUAGE_NAMES[AppLanguage(item.language)]
            )
            field_item = QTableWidgetItem(texts.get(item.field.label, item.field.label))
            field_item.setToolTip(item.field.field_id)
            interval_item = QTableWidgetItem(self._interval_text(item.field, texts))

            self.table.setItem(row, 0, state_item)
            self.table.setItem(row, 1, language_item)
            self.table.setItem(row, 2, field_item)
            self.table.setItem(row, 3, interval_item)

        self.table.resizeColumnsToContents()
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.clearSelection()

    def review_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.state is not TranslationState.DRAFT:
            self._sync_review_action()
            return
        self._clear_message()
        try:
            self.status_controller.review_current(
                field_id=item.field.field_id,
                language=item.language,
            )
        except (RuntimeError, ValueError) as exc:
            self.message_label.setText(str(exc))
            self.message_label.setVisible(True)
            self._sync_review_action()
            return
        self.refresh()

    def _selected_item(self) -> TranslationReadinessItem | None:
        summary = self._last_summary
        row = self.table.currentRow()
        if summary is None or row < 0 or row >= len(summary.items):
            return None
        return summary.items[row]

    def _sync_review_action(self) -> None:
        item = self._selected_item()
        self.review_button.setEnabled(
            item is not None and item.state is TranslationState.DRAFT
        )

    @staticmethod
    def _interval_text(field: object, texts: dict[str, str]) -> str:
        top = getattr(field, "top_depth", None)
        bottom = getattr(field, "bottom_depth", None)
        if top is None or bottom is None:
            return texts["global"]
        return f"{float(top):.2f}–{float(bottom):.2f} m"

    def _sync_depth_controls(self, enabled: bool) -> None:
        self.top_depth_spin.setEnabled(enabled)
        self.bottom_depth_spin.setEnabled(enabled)
        if self.isVisible():
            self.refresh()

    def _refresh_if_depth_enabled(self) -> None:
        if self.depth_filter_checkbox.isChecked():
            self.refresh()

    def _show_error(self, text: str) -> None:
        self._last_summary = None
        self.table.setRowCount(0)
        self.review_button.setEnabled(False)
        self.readiness_label.clear()
        self.summary_label.clear()
        self.message_label.setText(text)
        self.message_label.setVisible(True)

    def _clear_message(self) -> None:
        self.message_label.clear()
        self.message_label.setVisible(False)
