from __future__ import annotations

from typing import TypedDict

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.gas_context_events import (
    GasContextEventType,
    InterpretationImpact,
)
from geoworkbench.services.gas_context_event_editor import (
    GasContextEventEditorController,
    GasContextEventEditorError,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.window_geometry import fit_window_to_screen


_EVENT_LABELS: dict[GasContextEventType, tuple[str, str, str]] = {
    GasContextEventType.BACKGROUND: ("Фоновый газ", "Фондық газ", "Background gas"),
    GasContextEventType.FORMATION_SHOW: (
        "Пластовый газ / проявление",
        "Қабат газы / белгісі",
        "Formation gas / show",
    ),
    GasContextEventType.CONNECTION_GAS: (
        "Газ на соединении",
        "Қосылу кезіндегі газ",
        "Connection gas",
    ),
    GasContextEventType.TRIP_GAS: ("Газ при СПО", "СПО кезіндегі газ", "Trip gas"),
    GasContextEventType.SWAB_GAS: ("Сваб-газ", "Сваб-газы", "Swab gas"),
    GasContextEventType.CIRCULATED_GAS: (
        "Циркулировавший газ",
        "Айналымдағы газ",
        "Circulated gas",
    ),
    GasContextEventType.RECYCLED_GAS: (
        "Рециркулированный газ",
        "Қайта айналымдағы газ",
        "Recycled gas",
    ),
    GasContextEventType.CHROMATOGRAPH_TEST_GAS: (
        "Тест хроматографа",
        "Хроматограф сынағы",
        "Chromatograph test gas",
    ),
    GasContextEventType.GAS_LINE_TEST_GAS: (
        "Тест газовой линии",
        "Газ желісінің сынағы",
        "Gas-line test gas",
    ),
    GasContextEventType.LAG_TRACER_GAS: (
        "Газ-трассер лага",
        "Лаг трассер газы",
        "Lag tracer gas",
    ),
    GasContextEventType.CALIBRATION_GAS: (
        "Калибровочный газ",
        "Калибрлеу газы",
        "Calibration gas",
    ),
    GasContextEventType.ELEVATED_UNCLASSIFIED: (
        "Повышенный, не классифицирован",
        "Жоғары, жіктелмеген",
        "Elevated, unclassified",
    ),
    GasContextEventType.OTHER_TECHNOLOGICAL: (
        "Прочий технологический газ",
        "Басқа технологиялық газ",
        "Other technological gas",
    ),
}

class GasContextEventValues(TypedDict):
    event_type: GasContextEventType
    top_depth: float
    bottom_depth: float
    impact: InterpretationImpact | None
    confirmed: bool
    reported_total_gas: float | None
    reported_unit: str | None
    comment: str


_IMPACT_LABELS: dict[InterpretationImpact, tuple[str, str, str]] = {
    InterpretationImpact.EXCLUDE_GEOLOGICAL: (
        "Исключить из геологической интерпретации",
        "Геологиялық интерпретациядан алып тастау",
        "Exclude from geological interpretation",
    ),
    InterpretationImpact.TECHNOLOGICAL_GAS: (
        "Технологический газ",
        "Технологиялық газ",
        "Technological gas",
    ),
    InterpretationImpact.FORMATION_GAS: (
        "Пластовый газ",
        "Қабат газы",
        "Formation gas",
    ),
    InterpretationImpact.REVIEW_REQUIRED: (
        "Требуется проверка",
        "Тексеру қажет",
        "Review required",
    ),
}


class GasContextEventDialog(QDialog):
    """Repeated-row editor for the report-first gas-context registry."""

    def __init__(
        self,
        controller: GasContextEventEditorController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language
        self.setObjectName("gas-context-event-dialog")
        self.setWindowTitle(
            self._text(
                "Газовые события перед интерпретацией",
                "Интерпретация алдындағы газ оқиғалары",
                "Gas events before interpretation",
            )
        )

        root = QVBoxLayout(self)
        intro = QLabel(
            self._text(
                "Подтверждённые строки влияют на классификацию Gas Ratio / Pixler / OPUS. "
                "TG здесь — только операторская/QC-ссылка и не изменяет исходные кривые.",
                "Расталған жолдар Gas Ratio / Pixler / OPUS жіктеуіне әсер етеді. "
                "Мұндағы TG — тек оператор/QC анықтамасы және бастапқы қисықтарды өзгертпейді.",
                "Confirmed rows affect Gas Ratio / Pixler / OPUS classification. "
                "TG here is an operator/QC reference only and never changes source curves.",
            )
        )
        intro.setWordWrap(True)
        intro.setObjectName("gas-context-event-intro")
        root.addWidget(intro)

        self.table = QTableWidget(0, 9)
        self.table.setObjectName("gas-context-event-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._text("Тип газа", "Газ түрі", "Gas type"),
                self._text("Верх", "Жоғарғы", "Top"),
                self._text("Низ", "Төменгі", "Bottom"),
                "TG / QC",
                self._text("Ед.", "Бірл.", "Unit"),
                self._text("Статус", "Күй", "Status"),
                self._text("Влияние", "Әсер", "Impact"),
                self._text("Комментарий", "Түсініктеме", "Comment"),
                self._text("Источник", "Дереккөз", "Source"),
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._load_selected)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        form = QFormLayout()
        self.type_input = QComboBox()
        self.type_input.setObjectName("gas-context-event-type")
        for event_type in GasContextEventType:
            self.type_input.addItem(self._event_label(event_type), event_type)

        self.top_input = self._depth_input("gas-context-event-top")
        self.bottom_input = self._depth_input("gas-context-event-bottom")

        self.reported_total_input = QLineEdit()
        self.reported_total_input.setObjectName("gas-context-event-tg")
        validator = QDoubleValidator(0.0, 1_000_000_000.0, 8, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.reported_total_input.setValidator(validator)
        self.reported_total_input.setPlaceholderText(
            self._text("необязательно", "міндетті емес", "optional")
        )

        self.reported_unit_input = QLineEdit()
        self.reported_unit_input.setObjectName("gas-context-event-unit")
        self.reported_unit_input.setMaxLength(32)
        self.reported_unit_input.setPlaceholderText("% / ppm / units")

        self.confirmed_input = QCheckBox(
            self._text(
                "Подтверждено — влияет на интерпретацию",
                "Расталған — интерпретацияға әсер етеді",
                "Confirmed — affects interpretation",
            )
        )
        self.confirmed_input.setObjectName("gas-context-event-confirmed")
        self.confirmed_input.setChecked(True)

        self.impact_input = QComboBox()
        self.impact_input.setObjectName("gas-context-event-impact")
        self.impact_input.addItem(
            self._text(
                "По умолчанию для типа газа",
                "Газ түрі бойынша әдепкі",
                "Default for gas type",
            ),
            None,
        )
        for impact in InterpretationImpact:
            self.impact_input.addItem(self._impact_label(impact), impact)

        self.comment_input = QLineEdit()
        self.comment_input.setObjectName("gas-context-event-comment")
        self.comment_input.setMaxLength(4000)

        form.addRow(self._text("Тип газа", "Газ түрі", "Gas type"), self.type_input)
        form.addRow(self._text("Глубина сверху", "Жоғарғы тереңдік", "Top depth"), self.top_input)
        form.addRow(self._text("Глубина снизу", "Төменгі тереңдік", "Bottom depth"), self.bottom_input)
        form.addRow("TG / QC", self.reported_total_input)
        form.addRow(self._text("Единица TG", "TG бірлігі", "TG unit"), self.reported_unit_input)
        form.addRow(self._text("Статус", "Күй", "Status"), self.confirmed_input)
        form.addRow(self._text("Влияние", "Әсер", "Impact"), self.impact_input)
        form.addRow(self._text("Комментарий", "Түсініктеме", "Comment"), self.comment_input)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.add_button = QPushButton(self._text("Добавить", "Қосу", "Add"))
        self.add_button.setObjectName("gas-context-event-add")
        self.add_button.clicked.connect(self._add)
        self.update_button = QPushButton(self._text("Обновить", "Жаңарту", "Update"))
        self.update_button.setObjectName("gas-context-event-update")
        self.update_button.clicked.connect(self._update)
        self.duplicate_button = QPushButton(self._text("Дублировать", "Көшіру", "Duplicate"))
        self.duplicate_button.setObjectName("gas-context-event-duplicate")
        self.duplicate_button.clicked.connect(self._duplicate)
        self.delete_button = QPushButton(self._text("Удалить", "Жою", "Delete"))
        self.delete_button.setObjectName("gas-context-event-delete")
        self.delete_button.clicked.connect(self._delete)
        for button in (
            self.add_button,
            self.update_button,
            self.duplicate_button,
            self.delete_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("gas-context-event-buttons")
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            self._text("Сохранить", "Сақтау", "Save")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._text("Отмена", "Бас тарту", "Cancel")
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh()
        self._update_action_state()
        fit_window_to_screen(
            self,
            preferred=QSize(1180, 720),
            minimum=QSize(760, 520),
        )

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {
            AppLanguage.RU: ru,
            AppLanguage.KK: kk,
            AppLanguage.EN: en,
        }[self.language]

    def _event_label(self, event_type: GasContextEventType) -> str:
        labels = _EVENT_LABELS[event_type]
        return self._text(*labels)

    def _impact_label(self, impact: InterpretationImpact) -> str:
        labels = _IMPACT_LABELS[impact]
        return self._text(*labels)

    @staticmethod
    def _depth_input(object_name: str) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setObjectName(object_name)
        control.setRange(0.0, 1.7976931348623157e308)
        control.setDecimals(15)
        control.setSingleStep(0.1)
        return control

    def _refresh(self, *, select_event_id: str | None = None) -> None:
        events = self.controller.list_events()
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(events))
            selected_row = -1
            for row, event in enumerate(events):
                impact = event.effective_impact
                values = (
                    self._event_label(event.event_type),
                    f"{event.top_depth:g}",
                    f"{event.bottom_depth:g}",
                    "" if event.reported_total_gas is None else f"{event.reported_total_gas:g}",
                    event.reported_unit or "",
                    self._text("подтверждено", "расталған", "confirmed")
                    if event.confirmed
                    else self._text("черновик", "жоба", "draft"),
                    self._impact_label(impact),
                    event.comment,
                    event.source,
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, event.event_id)
                    self.table.setItem(row, column, item)
                if event.event_id == select_event_id:
                    selected_row = row
            if selected_row >= 0:
                self.table.selectRow(selected_row)
            elif events:
                self.table.selectRow(0)
            else:
                self.table.clearSelection()
        finally:
            self.table.blockSignals(False)
        self._load_selected()
        self._update_action_state()

    def _selected_event_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def _load_selected(self) -> None:
        event_id = self._selected_event_id()
        if event_id is None:
            self._update_action_state()
            return
        event = self.controller.get(event_id)
        self._select_combo_data(self.type_input, event.event_type)
        self.top_input.setValue(event.top_depth)
        self.bottom_input.setValue(event.bottom_depth)
        self.reported_total_input.setText(self._format_total_gas(event.reported_total_gas))
        self.reported_unit_input.setText(event.reported_unit or "")
        self.confirmed_input.setChecked(event.confirmed)
        self._select_combo_data(self.impact_input, event.impact)
        self.comment_input.setText(event.comment)
        self._update_action_state()

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _format_total_gas(self, value: float | None) -> str:
        if value is None:
            return ""
        validator = self.reported_total_input.validator()
        if isinstance(validator, QDoubleValidator):
            return validator.locale().toString(value, "g", 15)
        return f"{value:g}"

    def _values(self) -> GasContextEventValues:
        event_type = self.type_input.currentData()
        if not isinstance(event_type, GasContextEventType):
            raise ValueError("Не выбран тип газового события")
        impact = self.impact_input.currentData()
        if impact is not None and not isinstance(impact, InterpretationImpact):
            raise ValueError("Некорректный режим влияния на интерпретацию")
        tg_text = self.reported_total_input.text().strip()
        total_gas: float | None = None
        if tg_text:
            validator = self.reported_total_input.validator()
            if not isinstance(validator, QDoubleValidator):
                raise ValueError("Некорректный валидатор TG/QC")
            total_gas, ok = validator.locale().toDouble(tg_text)
            if not ok:
                raise ValueError(
                    self._text(
                        "Некорректное значение TG/QC",
                        "TG/QC мәні дұрыс емес",
                        "Invalid TG/QC value",
                    )
                )
        unit_text = self.reported_unit_input.text().strip()
        return {
            "event_type": event_type,
            "top_depth": self.top_input.value(),
            "bottom_depth": self.bottom_input.value(),
            "impact": impact,
            "confirmed": self.confirmed_input.isChecked(),
            "reported_total_gas": total_gas,
            "reported_unit": unit_text or None,
            "comment": self.comment_input.text(),
        }

    def _add(self) -> None:
        try:
            event = self.controller.add(**self._values())
        except (TypeError, ValueError) as exc:
            self._show_error(exc)
            return
        self._refresh(select_event_id=event.event_id)

    def _update(self) -> None:
        event_id = self._selected_event_id()
        if event_id is None:
            return
        try:
            event = self.controller.update(event_id, **self._values())
        except (KeyError, TypeError, ValueError) as exc:
            self._show_error(exc)
            return
        self._refresh(select_event_id=event.event_id)

    def _duplicate(self) -> None:
        event_id = self._selected_event_id()
        if event_id is None:
            return
        try:
            event = self.controller.duplicate(event_id)
        except (KeyError, ValueError) as exc:
            self._show_error(exc)
            return
        self._refresh(select_event_id=event.event_id)

    def _delete(self) -> None:
        event_id = self._selected_event_id()
        if event_id is None:
            return
        try:
            self.controller.remove(event_id)
        except KeyError as exc:
            self._show_error(exc)
            return
        self._refresh()

    def _save(self) -> None:
        try:
            self.controller.commit()
        except (GasContextEventEditorError, ValueError) as exc:
            self._show_error(exc)
            return
        self.accept()

    def _update_action_state(self) -> None:
        selected = self._selected_event_id() is not None
        self.update_button.setEnabled(selected)
        self.duplicate_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)

    def _show_error(self, error: Exception) -> None:
        QMessageBox.warning(self, self.windowTitle(), str(error))


__all__ = ["GasContextEventDialog"]
