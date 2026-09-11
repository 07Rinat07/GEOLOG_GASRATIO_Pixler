from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.analysis_update import AnalysisCellChange, AnalysisField
from geoworkbench.project.well_analysis_update_controller import WellAnalysisUpdateController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.well_analysis_update import (
    AnalysisConflict,
    AnalysisSourceSample,
    AnalysisUpdateError,
    WellAnalysisUpdatePlan,
)


_FIELD_LABELS: dict[AnalysisField, tuple[str, str, str]] = {
    AnalysisField.CALCITE_PERCENT: ("Кальцит, %", "Кальцит, %", "Calcite, %"),
    AnalysisField.DOLOMITE_PERCENT: ("Доломит, %", "Доломит, %", "Dolomite, %"),
    AnalysisField.LBA_GROUP: ("Группа ЛБА", "ЛБА тобы", "LBA group"),
    AnalysisField.LBA_TYPE_ID: ("Тип ЛБА", "ЛБА түрі", "LBA type"),
    AnalysisField.LBA_INTENSITY: (
        "Интенсивность ЛБА",
        "ЛБА қарқындылығы",
        "LBA intensity",
    ),
    AnalysisField.LBA_COLOR: ("Цвет ЛБА", "ЛБА түсі", "LBA color"),
    AnalysisField.LBA_DISTRIBUTION: (
        "Распределение ЛБА",
        "ЛБА таралуы",
        "LBA distribution",
    ),
    AnalysisField.LBA_CUT: ("Экстракция ЛБА", "ЛБА экстракциясы", "LBA cut"),
    AnalysisField.LBA_CUT_SPEED: (
        "Скорость экстракции",
        "Экстракция жылдамдығы",
        "Cut speed",
    ),
    AnalysisField.LBA_CUT_COLOR: (
        "Цвет экстракта",
        "Экстракт түсі",
        "Cut color",
    ),
    AnalysisField.LBA_RESIDUE_TYPE: (
        "Тип остатка",
        "Қалдық түрі",
        "Residue type",
    ),
    AnalysisField.LBA_RESIDUE_COLOR: (
        "Цвет остатка",
        "Қалдық түсі",
        "Residue color",
    ),
    AnalysisField.LBA_ODOUR: ("Запах", "Иіс", "Odour"),
    AnalysisField.LBA_STAIN: ("Пятно", "Дақ", "Stain"),
    AnalysisField.LBA_DESCRIPTION: (
        "Описание ЛБА",
        "ЛБА сипаттамасы",
        "LBA description",
    ),
    AnalysisField.ANALYSIS_INTERPRETATION: (
        "Интерпретация анализа",
        "Талдау интерпретациясы",
        "Analysis interpretation",
    ),
}


class LateAnalysisReviewDialog(QDialog):
    """Preview normalized late analyses and apply only explicit fill-only choices."""

    def __init__(
        self,
        controller: WellAnalysisUpdateController,
        source_samples: tuple[AnalysisSourceSample, ...],
        *,
        source_name: str,
        source_sha256: str,
        language: AppLanguage = AppLanguage.RU,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.source_samples = source_samples
        self.source_name = source_name
        self.source_sha256 = source_sha256
        self.language = language
        self.plan: WellAnalysisUpdatePlan | None = None

        self.setWindowTitle(
            self._text("Поздние анализы", "Кейінгі талдаулар", "Late analyses")
        )
        self.resize(980, 680)
        root = QVBoxLayout(self)

        summary = QLabel(
            self._text(
                "Предварительный просмотр ничего не записывает. Можно заполнить только "
                "явно выбранные пустые поля; существующие и ручные значения защищены.",
                "Алдын ала қарау ештеңе жазбайды. Тек нақты таңдалған бос өрістер "
                "толтырылады; бар және қолмен енгізілген мәндер қорғалған.",
                "Preview does not write anything. Only explicitly selected empty fields "
                "may be filled; existing and authored values are protected.",
            )
        )
        summary.setWordWrap(True)
        summary.setObjectName("late-analysis-safety-summary")
        root.addWidget(summary)

        fields_group = QGroupBox(
            self._text("Поля для проверки", "Тексерілетін өрістер", "Fields to review")
        )
        fields_layout = QGridLayout(fields_group)
        self.field_checks: dict[AnalysisField, QCheckBox] = {}
        available = {
            value.field
            for sample in source_samples
            for value in sample.values
            if value.value is not None
        }
        for index, field in enumerate(AnalysisField):
            check = QCheckBox(self._field_label(field))
            check.setChecked(field in available)
            check.setEnabled(field in available)
            check.toggled.connect(self._invalidate)
            self.field_checks[field] = check
            fields_layout.addWidget(check, index // 3, index % 3)
        root.addWidget(fields_group)

        action_row = QHBoxLayout()
        self.analyze_button = QPushButton(
            self._text("Показать изменения", "Өзгерістерді көрсету", "Preview changes")
        )
        self.analyze_button.clicked.connect(self._analyze)
        action_row.addWidget(self.analyze_button)
        self.counts_label = QLabel()
        self.counts_label.setObjectName("late-analysis-counts")
        action_row.addWidget(self.counts_label, 1)
        root.addLayout(action_row)

        self.table = QTableWidget(0, 7)
        self.table.setObjectName("late-analysis-review-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._text("Выбрать", "Таңдау", "Select"),
                self._text("Интервал", "Аралық", "Interval"),
                self._text("Поле", "Өріс", "Field"),
                self._text("Было", "Бұрын", "Before"),
                self._text("Стало", "Кейін", "After"),
                self._text("Статус", "Күй", "Status"),
                self._text("Образец", "Үлгі", "Sample"),
            ]
        )
        root.addWidget(self.table, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._text(
                "Применить выбранное",
                "Таңдалғанын қолдану",
                "Apply selected",
            )
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def selected_changes(self) -> tuple[AnalysisCellChange, ...]:
        selected: list[AnalysisCellChange] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None or item.checkState() is not Qt.CheckState.Checked:
                continue
            change = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(change, AnalysisCellChange):
                selected.append(change)
        return tuple(selected)

    def _analyze(self) -> None:
        self._invalidate(reset_controller=True)
        fields = tuple(
            field for field, check in self.field_checks.items() if check.isChecked()
        )
        try:
            plan = self.controller.analyze(
                self.source_samples,
                selected_fields=fields,
                source_name=self.source_name,
                source_sha256=self.source_sha256,
            )
        except AnalysisUpdateError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.plan = plan
        self._render_plan(plan)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _render_plan(self, plan: WellAnalysisUpdatePlan) -> None:
        rows: list[tuple[AnalysisCellChange | None, AnalysisConflict | None]] = [
            (change, None) for change in plan.changes
        ]
        rows.extend((None, conflict) for conflict in plan.conflicts)
        self.table.setRowCount(len(rows))
        for row, (change, conflict) in enumerate(rows):
            if change is not None:
                choice = QTableWidgetItem()
                choice.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                choice.setCheckState(Qt.CheckState.Unchecked)
                choice.setData(Qt.ItemDataRole.UserRole, change)
                self.table.setItem(row, 0, choice)
                values = (
                    f"{change.top_depth:g} … {change.bottom_depth:g}",
                    self._field_label(change.field),
                    self._value_text(change.old_value),
                    self._value_text(change.new_value),
                    self._text("Пустое поле", "Бос өріс", "Empty field"),
                    change.sample_id,
                )
            else:
                assert conflict is not None
                choice = QTableWidgetItem()
                choice.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, 0, choice)
                values = (
                    "—",
                    self._field_label(conflict.field),
                    self._value_text(conflict.existing_value),
                    self._value_text(conflict.incoming_value),
                    self._text(
                        "Конфликт — не перезаписывается",
                        "Қақтығыс — қайта жазылмайды",
                        "Conflict — preserved",
                    ),
                    conflict.sample_id,
                )
            for column, value in enumerate(values, 1):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.counts_label.setText(
            self._text(
                f"Заполнений: {plan.fill_count}; конфликтов: {plan.conflict_count}; "
                f"без интервала: {plan.missing_source_intervals}",
                f"Толтыру: {plan.fill_count}; қақтығыс: {plan.conflict_count}; "
                f"аралықсыз: {plan.missing_source_intervals}",
                f"Fills: {plan.fill_count}; conflicts: {plan.conflict_count}; "
                f"unmatched intervals: {plan.missing_source_intervals}",
            )
        )

    def _accept(self) -> None:
        if self.plan is None:
            return
        try:
            self.controller.apply(self.plan, selected_changes=self.selected_changes())
        except AnalysisUpdateError as exc:
            self.plan = None
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.accept()

    def reject(self) -> None:
        self.controller.reset_state()
        super().reject()

    def _invalidate(self, _checked: bool = False, *, reset_controller: bool = True) -> None:
        self.plan = None
        self.table.setRowCount(0)
        self.counts_label.clear()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        if reset_controller:
            self.controller.reset_state()

    def _field_label(self, field: AnalysisField) -> str:
        return self._text(*_FIELD_LABELS[field])

    @staticmethod
    def _value_text(value: object) -> str:
        if value is None or value == "":
            return "—"
        return str(value)

    def _text(self, ru: str, kk: str, en: str) -> str:
        if self.language is AppLanguage.KK:
            return kk
        if self.language is AppLanguage.EN:
            return en
        return ru
