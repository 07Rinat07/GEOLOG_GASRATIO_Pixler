from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lithotype_visuals import configure_lithotype_combo, lithotype_icon
from geoworkbench.ui.rich_interval_text_editor import RichIntervalTextEditor


_TEXT = {
    AppLanguage.RU: {
        "create": "Новая проба шлама",
        "edit": "Редактирование пробы шлама",
        "interval": "Интервал отбора",
        "top": "От, м",
        "bottom": "До, м",
        "composition": "Шламограмма",
        "composition_hint": "Укажите до четырёх пород. Суммарное содержание пробы должно быть ровно 100%.",
        "composition_steps": "1. Выберите породу. 2. Укажите её содержание. 3. Добейтесь итога 100%. 4. Нажмите ОК — проба появится одновременно в шламограмме, ЛБА, кальциметрии и описании.",
        "rock": "Порода",
        "percent": "Содержание",
        "remainder": "Остаток",
        "total": "Итого",
        "total_ready": "готово к сохранению",
        "total_missing": "осталось {value:g}%",
        "total_excess": "превышение {value:g}%",
        "composition_error": "Укажите до четырёх разных пород; сумма должна быть ровно 100%.",
        "duplicate_error": "Одна порода не должна повторяться в нескольких строках.",
        "analysis": "ЛБА и кальциметрия",
        "calcimetry": "Кальциметрия",
        "calcimetry_hint": "Если анализа нет, оставьте поля пустыми. Нерастворимый остаток рассчитывается автоматически.",
        "calcite": "Кальцит CaCO₃, %",
        "dolomite": "Доломит CaMg(CO₃)₂, %",
        "residue": "Нерастворимый остаток, %",
        "calc_error": "Сумма кальцита и доломита не должна превышать 100%.",
        "no_value": "Нет результата",
        "lba": "Люминесцентно-битуминологический анализ",
        "lba_hint": "Выберите один тип битумоида и один балл интенсивности. Если показаний нет, оставьте «Нет результата».",
        "lba_type": "Тип битумоида",
        "intensity": "Интенсивность / остаточное кольцо",
        "lba_color": "Цвет свечения",
        "lba_details": "Дополнительное описание ЛБА",
        "description": "Описание шлама",
        "interpretation": "Заключение",
        "delete": "Удалить пробу",
        "interval_error": "Начальная глубина должна быть меньше конечной.",
        "intensity_1": "1 — единичные точки",
        "intensity_2": "2 — фрагментарное кольцо",
        "intensity_3": "3 — тонкое сплошное кольцо",
        "intensity_4": "4 — толстое кольцо",
        "intensity_5": "5 — сплошное пятно",
        "type_lb": "ЛБ — лёгкий битумоид",
        "type_mb": "МБ — маслянистый битумоид",
        "type_msb": "МСБ — маслянисто-смолистый",
        "type_sb": "СБ — смолистый",
        "type_sab": "САБ — смолисто-асфальтеновый",
    },
    AppLanguage.KK: {
        "create": "Жаңа шлам үлгісі",
        "edit": "Шлам үлгісін өңдеу",
        "interval": "Үлгі алу аралығы",
        "top": "Басталуы, м",
        "bottom": "Аяқталуы, м",
        "composition": "Шламограмма",
        "composition_hint": "Төрт жынысқа дейін көрсетіңіз. Үлгінің жалпы құрамы дәл 100% болуы керек.",
        "composition_steps": "1. Жынысты таңдаңыз. 2. Мөлшерін енгізіңіз. 3. Қорытындыны 100%-ға жеткізіңіз. 4. ОК басыңыз — үлгі шламограмма, ЛБА, кальциметрия және сипаттама бағандарында бірден көрінеді.",
        "rock": "Тау жынысы",
        "percent": "Мөлшері",
        "remainder": "Қалдық",
        "total": "Барлығы",
        "total_ready": "сақтауға дайын",
        "total_missing": "{value:g}% қалды",
        "total_excess": "{value:g}% артық",
        "composition_error": "Төрт түрлі жынысқа дейін көрсетіңіз; қосындысы дәл 100% болуы керек.",
        "duplicate_error": "Бір жынысты бірнеше жолда қайталауға болмайды.",
        "analysis": "ЛБА және кальциметрия",
        "calcimetry": "Кальциметрия",
        "calcimetry_hint": "Талдау жоқ болса, өрістерді бос қалдырыңыз. Ерімейтін қалдық автоматты есептеледі.",
        "calcite": "Кальцит CaCO₃, %",
        "dolomite": "Доломит CaMg(CO₃)₂, %",
        "residue": "Ерімейтін қалдық, %",
        "calc_error": "Кальцит пен доломит қосындысы 100%-дан аспауы керек.",
        "no_value": "Нәтиже жоқ",
        "lba": "Люминесцентті-битуминологиялық талдау",
        "lba_hint": "Битумоидтың бір түрін және қарқындылықтың бір балын таңдаңыз. Көрсеткіш жоқ болса, «Нәтиже жоқ» күйінде қалдырыңыз.",
        "lba_type": "Битумоид түрі",
        "intensity": "Қарқындылық / қалдық сақина",
        "lba_color": "Жарқырау түсі",
        "lba_details": "ЛБА қосымша сипаттамасы",
        "description": "Шлам сипаттамасы",
        "interpretation": "Қорытынды",
        "delete": "Үлгіні жою",
        "interval_error": "Бастапқы тереңдік соңғы тереңдіктен кіші болуы керек.",
        "intensity_1": "1 — жеке нүктелер",
        "intensity_2": "2 — үзік сақина",
        "intensity_3": "3 — жұқа тұтас сақина",
        "intensity_4": "4 — қалың сақина",
        "intensity_5": "5 — тұтас дақ",
        "type_lb": "ЛБ — жеңіл битумоид",
        "type_mb": "МБ — майлы битумоид",
        "type_msb": "МСБ — майлы-шайырлы",
        "type_sb": "СБ — шайырлы",
        "type_sab": "САБ — шайырлы-асфальтенді",
    },
    AppLanguage.EN: {
        "create": "New cuttings sample",
        "edit": "Edit cuttings sample",
        "interval": "Sampling interval",
        "top": "From, m",
        "bottom": "To, m",
        "composition": "Cuttings log",
        "composition_hint": "Select up to four rocks. The total sample composition must equal exactly 100%.",
        "composition_steps": "1. Select a rock. 2. Enter its content. 3. Make the total exactly 100%. 4. Press OK — the same sample appears in the cuttings, LBA, calcimetry and description tracks.",
        "rock": "Rock",
        "percent": "Content",
        "remainder": "Remainder",
        "total": "Total",
        "total_ready": "ready to save",
        "total_missing": "{value:g}% remaining",
        "total_excess": "{value:g}% over",
        "composition_error": "Select up to four different rocks; the total must be exactly 100%.",
        "duplicate_error": "The same rock cannot be repeated in multiple rows.",
        "analysis": "LBA and calcimetry",
        "calcimetry": "Calcimetry",
        "calcimetry_hint": "Leave fields empty when no analysis is available. Insoluble residue is calculated automatically.",
        "calcite": "Calcite CaCO₃, %",
        "dolomite": "Dolomite CaMg(CO₃)₂, %",
        "residue": "Insoluble residue, %",
        "calc_error": "Calcite plus dolomite must not exceed 100%.",
        "no_value": "No result",
        "lba": "Luminescent-bituminological analysis",
        "lba_hint": "Select one bitumoid type and one intensity score. Leave “No result” selected when there is no indication.",
        "lba_type": "Bitumoid type",
        "intensity": "Intensity / residual ring",
        "lba_color": "Fluorescence color",
        "lba_details": "Additional LBA description",
        "description": "Cuttings description",
        "interpretation": "Conclusion",
        "delete": "Delete sample",
        "interval_error": "The start depth must be less than the end depth.",
        "intensity_1": "1 — isolated points",
        "intensity_2": "2 — fragmented ring",
        "intensity_3": "3 — thin continuous ring",
        "intensity_4": "4 — thick ring",
        "intensity_5": "5 — solid spot",
        "type_lb": "LB — light bitumoid",
        "type_mb": "MB — oily bitumoid",
        "type_msb": "MSB — oily-resinous",
        "type_sb": "SB — resinous",
        "type_sab": "SAB — resinous-asphaltenic",
    },
}

_LBA_TYPES = (
    ("ЛБ", "#22d3ee", "type_lb"),
    ("МБ", "#facc15", "type_mb"),
    ("МСБ", "#fb923c", "type_msb"),
    ("СБ", "#be123c", "type_sb"),
    ("САБ", "#92400e", "type_sab"),
)


class UnifiedCuttingsSampleDialog(QDialog):
    """Edit one shared sample displayed in cuttings, LBA and calcimetry tracks.

    The workflow follows the supplied GeoData reference while keeping the user's
    stricter rule of at most four rock components. One sample ID owns interval,
    composition, LBA, calcimetry and rich description, so repeated editing never
    creates drifting duplicate intervals.
    """

    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        catalog: tuple[CatalogLithotype, ...],
        *,
        language: AppLanguage,
        sample: CuttingsSample | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = _TEXT[language]
        self._language = language
        self._sample = sample
        self._catalog = tuple(catalog)
        self.delete_requested = False
        self.setWindowTitle(self._text["edit"] if sample is not None else self._text["create"])
        self.setMinimumSize(560, 460)

        content = QWidget()
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.addWidget(self._interval_group(top_depth, bottom_depth))

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumWidth(0)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.tabs.addTab(self._composition_widget(sample), self._text["composition"])
        self.tabs.addTab(self._analysis_widget(sample), self._text["analysis"])
        self.rich_description = RichIntervalTextEditor(language=language)
        self.rich_description.set_html(sample.description if sample is not None else None)
        self.tabs.addTab(self.rich_description, self._text["description"])
        self.interpretation_input = QPlainTextEdit()
        self.interpretation_input.setObjectName("cuttings-analysis-interpretation")
        if sample is not None:
            self.interpretation_input.setPlainText(sample.analysis_interpretation or "")
        self.tabs.addTab(self.interpretation_input, self._text["interpretation"])
        content_layout.addWidget(self.tabs, 1)

        self.validation_label = QLabel()
        self.validation_label.setObjectName("cuttings-validation")
        self.validation_label.setStyleSheet("color:#dc2626; font-weight:600;")
        self.validation_label.setWordWrap(True)
        content_layout.addWidget(self.validation_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # The rich-text toolbar can be wider than a notebook display.  It must
        # not force the whole dialog into a horizontally scrolling canvas where
        # the percentage controls disappear off-screen.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("cuttings-dialog-buttons")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        if sample is not None:
            delete_button = buttons.addButton(
                self._text["delete"], QDialogButtonBox.ButtonRole.DestructiveRole
            )
            delete_button.setObjectName("cuttings-delete-button")
            delete_button.clicked.connect(self._delete)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)
        self._apply_adaptive_size()

    def _interval_group(self, top_depth: float, bottom_depth: float) -> QGroupBox:
        group = QGroupBox(self._text["interval"])
        interval = QFormLayout(group)
        self.top_input = self._depth_input(top_depth)
        self.top_input.setObjectName("cuttings-top")
        self.bottom_input = self._depth_input(bottom_depth)
        self.bottom_input.setObjectName("cuttings-bottom")
        interval.addRow(self._text["top"], self.top_input)
        interval.addRow(self._text["bottom"], self.bottom_input)
        return group

    def _apply_adaptive_size(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(860, 720)
            return
        available = screen.availableGeometry()
        width = min(920, max(560, int(available.width() * 0.76)))
        height = min(800, max(460, int(available.height() * 0.84)))
        self.resize(width, height)

    @staticmethod
    def _depth_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        control.setSuffix(" m")
        control.setValue(float(value))
        return control

    def _composition_widget(self, sample: CuttingsSample | None) -> QWidget:
        widget = QWidget()
        root = QVBoxLayout(widget)
        hint = QLabel(self._text["composition_hint"])
        hint.setWordWrap(True)
        hint.setObjectName("cuttings-composition-hint")
        root.addWidget(hint)

        steps = QLabel(self._text["composition_steps"])
        steps.setWordWrap(True)
        steps.setObjectName("cuttings-composition-steps")
        steps.setStyleSheet(
            "QLabel {background:#e0f2fe; color:#0c4a6e; border:1px solid #7dd3fc; "
            "border-radius:4px; padding:7px;}"
        )
        root.addWidget(steps)

        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        grid.setHorizontalSpacing(8)
        grid.addWidget(QLabel(self._text["rock"]), 0, 0)
        grid.addWidget(QLabel(self._text["percent"]), 0, 1)
        grid.addWidget(QLabel(""), 0, 2)
        existing = list(sample.components if sample is not None else ())
        self.rock_inputs: list[QComboBox] = []
        self.percent_inputs: list[QDoubleSpinBox] = []
        self.remainder_buttons: list[QPushButton] = []
        for row in range(4):
            rock = QComboBox()
            rock.setObjectName(f"cuttings-rock-{row + 1}")
            rock.setMinimumWidth(0)
            rock.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            configure_lithotype_combo(rock)
            rock.addItem("—", "")
            for item in self._catalog:
                rock.addItem(
                    lithotype_icon(item),
                    f"{item.code} — {item.localized_name(self._language.value)}",
                    item.lithotype_id,
                )
            percent = QDoubleSpinBox()
            percent.setObjectName(f"cuttings-percent-{row + 1}")
            percent.setRange(0.0, 100.0)
            percent.setDecimals(1)
            percent.setSuffix(" %")
            percent.setFixedWidth(112)
            percent.valueChanged.connect(self._update_total)
            rock.currentIndexChanged.connect(
                lambda _index, selected_row=row: self._rock_changed(selected_row)
            )
            remainder = QPushButton(self._text["remainder"])
            remainder.setObjectName(f"cuttings-remainder-{row + 1}")
            remainder.setToolTip(self._text["composition_hint"])
            remainder.setFixedWidth(92)
            remainder.clicked.connect(
                lambda _checked=False, selected_row=row: self._fill_remainder(selected_row)
            )
            if row < len(existing):
                found = rock.findData(existing[row].lithotype_id)
                rock.setCurrentIndex(max(0, found))
                percent.setValue(existing[row].percentage)
            self.rock_inputs.append(rock)
            self.percent_inputs.append(percent)
            self.remainder_buttons.append(remainder)
            grid.addWidget(rock, row + 1, 0)
            grid.addWidget(percent, row + 1, 1)
            grid.addWidget(remainder, row + 1, 2)

        self.total_label = QLabel()
        self.total_label.setObjectName("cuttings-total")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(QLabel(self._text["total"]), 5, 0)
        grid.addWidget(self.total_label, 5, 1, 1, 2)
        root.addLayout(grid)

        self.composition_status_label = QLabel()
        self.composition_status_label.setObjectName("cuttings-composition-status")
        self.composition_status_label.setWordWrap(True)
        root.addWidget(self.composition_status_label)
        root.addStretch(1)
        self._update_total()
        return widget

    def _analysis_widget(self, sample: CuttingsSample | None) -> QWidget:
        outer = QWidget()
        layout = QVBoxLayout(outer)

        calc_group = QGroupBox(self._text["calcimetry"])
        calc_root = QVBoxLayout(calc_group)
        calc_hint = QLabel(self._text["calcimetry_hint"])
        calc_hint.setWordWrap(True)
        calc_root.addWidget(calc_hint)
        calc_form = QFormLayout()
        self.calcite_input = self._optional_percent("cuttings-calcite")
        self.dolomite_input = self._optional_percent("cuttings-dolomite")
        self.calcite_input.valueChanged.connect(self._update_residue)
        self.dolomite_input.valueChanged.connect(self._update_residue)
        self.residue_label = QLabel("—")
        self.residue_label.setObjectName("cuttings-residue")
        self.residue_label.setStyleSheet("font-weight:700;")
        calc_form.addRow(self._text["calcite"], self.calcite_input)
        calc_form.addRow(self._text["dolomite"], self.dolomite_input)
        calc_form.addRow(self._text["residue"], self.residue_label)
        calc_root.addLayout(calc_form)
        layout.addWidget(calc_group)

        lba_group = QGroupBox(self._text["lba"])
        lba_layout = QVBoxLayout(lba_group)
        lba_hint = QLabel(self._text["lba_hint"])
        lba_hint.setWordWrap(True)
        lba_layout.addWidget(lba_hint)

        self.type_group = QButtonGroup(self)
        self.type_group.setExclusive(True)
        type_grid = QGridLayout()
        no_type = QRadioButton(self._text["no_value"])
        no_type.setObjectName("lba-type-none")
        self.type_group.addButton(no_type, -1)
        type_grid.addWidget(no_type, 0, 0, 1, 2)
        for index, (code, color, label_key) in enumerate(_LBA_TYPES, start=1):
            button = QRadioButton(self._text[label_key])
            button.setObjectName(f"lba-type-{code}")
            foreground = (
                "#111827" if color.lower() in {"#22d3ee", "#facc15", "#fb923c"} else "#ffffff"
            )
            button.setStyleSheet(
                "QRadioButton {padding:6px 10px; border:1px solid #94a3b8; "
                f"border-radius:4px; background:{color}; color:{foreground}; font-weight:700;}}"
                "QRadioButton::indicator {width:16px; height:16px;}"
                "QRadioButton:checked {border:3px solid #2563eb;}"
            )
            self.type_group.addButton(button, index)
            type_grid.addWidget(button, (index - 1) // 2 + 1, (index - 1) % 2)
        no_type.setChecked(True)
        lba_layout.addWidget(QLabel(self._text["lba_type"]))
        lba_layout.addLayout(type_grid)

        self.intensity_group = QButtonGroup(self)
        self.intensity_group.setExclusive(True)
        intensity_grid = QGridLayout()
        no_intensity = QRadioButton(self._text["no_value"])
        no_intensity.setObjectName("lba-intensity-none")
        self.intensity_group.addButton(no_intensity, -1)
        intensity_grid.addWidget(no_intensity, 0, 0)
        for value in range(1, 6):
            button = QRadioButton(self._text[f"intensity_{value}"])
            button.setObjectName(f"lba-intensity-{value}")
            self.intensity_group.addButton(button, value)
            intensity_grid.addWidget(button, value, 0)
        no_intensity.setChecked(True)
        lba_layout.addWidget(QLabel(self._text["intensity"]))
        lba_layout.addLayout(intensity_grid)

        details = QFormLayout()
        self.lba_color_input = QComboBox()
        self.lba_color_input.setObjectName("lba-fluorescence-color")
        self.lba_color_input.setEditable(True)
        self.lba_color_input.addItems(["", "БГ", "БЖ", "СЖ", "ГЖ", "Ж", "ОЖ", "О", "К", "ТК", "Ч"])
        self.lba_details_input = QLineEdit()
        self.lba_details_input.setObjectName("lba-description")
        details.addRow(self._text["lba_color"], self.lba_color_input)
        details.addRow(self._text["lba_details"], self.lba_details_input)
        lba_layout.addLayout(details)
        layout.addWidget(lba_group)
        layout.addStretch(1)

        if sample is not None:
            if sample.calcite_percent is not None:
                self.calcite_input.setValue(sample.calcite_percent)
            if sample.dolomite_percent is not None:
                self.dolomite_input.setValue(sample.dolomite_percent)
            type_codes = {
                code: index for index, (code, _color, _label) in enumerate(_LBA_TYPES, start=1)
            }
            type_button = self.type_group.button(type_codes.get(sample.lba_type_id or "", -1))
            if type_button is not None:
                type_button.setChecked(True)
            intensity = (
                sample.lba_intensity
                if isinstance(sample.lba_intensity, int)
                and sample.lba_intensity in range(1, 6)
                else -1
            )
            intensity_button = self.intensity_group.button(intensity)
            if intensity_button is not None:
                intensity_button.setChecked(True)
            self.lba_color_input.setCurrentText(sample.lba_color or "")
            self.lba_details_input.setText(sample.lba_description or "")
        self._update_residue()
        return outer

    @staticmethod
    def _optional_percent(object_name: str) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setObjectName(object_name)
        control.setRange(-1.0, 100.0)
        control.setDecimals(1)
        control.setSpecialValueText("—")
        control.setSuffix(" %")
        control.setValue(-1.0)
        return control

    @property
    def top_depth(self) -> float:
        return float(self.top_input.value())

    @property
    def bottom_depth(self) -> float:
        return float(self.bottom_input.value())

    def components(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for rock, percent in zip(self.rock_inputs, self.percent_inputs, strict=True):
            lithotype_id = str(rock.currentData() or "")
            numeric = float(percent.value())
            if not lithotype_id and numeric == 0.0:
                continue
            if not lithotype_id:
                return {}
            if lithotype_id in values:
                return {"__duplicate__": -1.0}
            values[lithotype_id] = numeric
        return {key: value for key, value in values.items() if value > 0.0}

    def values(self) -> dict[str, Any]:
        type_button = self.type_group.checkedButton()
        type_id = self.type_group.id(type_button) if type_button is not None else -1
        lba_type = _LBA_TYPES[type_id - 1][0] if type_id > 0 else None
        intensity_button = self.intensity_group.checkedButton()
        intensity = (
            self.intensity_group.id(intensity_button) if intensity_button is not None else -1
        )
        normalized_intensity = intensity if intensity > 0 else None
        return {
            "description": self.rich_description.html(),
            "calcite_percent": self.calcite_input.value()
            if self.calcite_input.value() >= 0
            else None,
            "dolomite_percent": self.dolomite_input.value()
            if self.dolomite_input.value() >= 0
            else None,
            "lba_type_id": lba_type,
            "lba_intensity": normalized_intensity,
            # Kept for compatibility with older projects where 1–5 was stored in lba_group.
            "lba_group": normalized_intensity,
            "lba_color": self.lba_color_input.currentText().strip() or None,
            "lba_description": self.lba_details_input.text().strip() or None,
            "analysis_interpretation": self.interpretation_input.toPlainText().strip() or None,
        }

    def _rock_changed(self, row: int) -> None:
        """Keep an empty row empty and make the first selected rock immediately usable."""

        rock = self.rock_inputs[row]
        percent = self.percent_inputs[row]
        if not rock.currentData():
            if percent.value() != 0.0:
                percent.setValue(0.0)
            self._update_total()
            return
        if percent.value() <= 0.0:
            remaining = max(
                0.0,
                100.0
                - sum(
                    float(control.value())
                    for index, control in enumerate(self.percent_inputs)
                    if index != row
                ),
            )
            # Selecting the first rock should produce a valid 100% sample, as
            # in the GeoData reference editor. Additional rocks receive the
            # currently unallocated remainder and can then be adjusted.
            if remaining > 0.0:
                percent.setValue(remaining)
        self._update_total()

    def _fill_remainder(self, row: int) -> None:
        if not self.rock_inputs[row].currentData():
            self.rock_inputs[row].setFocus()
            return
        remainder = max(
            0.0,
            100.0
            - sum(
                float(control.value())
                for index, control in enumerate(self.percent_inputs)
                if index != row
            ),
        )
        self.percent_inputs[row].setValue(remainder)
        self._update_total()

    def _update_total(self) -> None:
        if not hasattr(self, "percent_inputs") or not hasattr(self, "total_label"):
            return
        total = sum(float(control.value()) for control in self.percent_inputs)
        if abs(total - 100.0) <= 0.01:
            suffix = self._text["total_ready"]
            color = "#15803d"
        elif total < 100.0:
            suffix = self._text["total_missing"].format(value=100.0 - total)
            color = "#b45309"
        else:
            suffix = self._text["total_excess"].format(value=total - 100.0)
            color = "#dc2626"
        self.total_label.setText(f"{total:g} % — {suffix}")
        self.total_label.setStyleSheet(f"font-weight:700; color:{color};")
        if hasattr(self, "composition_status_label"):
            selected = [
                str(rock.currentData())
                for rock in self.rock_inputs
                if rock.currentData()
            ]
            duplicates = len(selected) != len(set(selected))
            if duplicates:
                self.composition_status_label.setText(self._text["duplicate_error"])
                self.composition_status_label.setStyleSheet("color:#dc2626; font-weight:700;")
            elif abs(total - 100.0) <= 0.01 and selected:
                self.composition_status_label.setText(self._text["total_ready"])
                self.composition_status_label.setStyleSheet("color:#15803d; font-weight:700;")
            else:
                self.composition_status_label.setText(self._text["composition_error"])
                self.composition_status_label.setStyleSheet("color:#b45309; font-weight:600;")

    def _update_residue(self) -> None:
        if not hasattr(self, "residue_label"):
            return
        calcite = self.calcite_input.value()
        dolomite = self.dolomite_input.value()
        if calcite < 0 and dolomite < 0:
            self.residue_label.setText("—")
            self.residue_label.setStyleSheet("font-weight:700; color:#64748b;")
            return
        total = max(0.0, calcite) + max(0.0, dolomite)
        residue = 100.0 - total
        self.residue_label.setText(f"{max(0.0, residue):g} %")
        color = "#15803d" if total <= 100.01 else "#dc2626"
        self.residue_label.setStyleSheet(f"font-weight:700; color:{color};")

    def _accept_if_valid(self) -> None:
        self.validation_label.clear()
        if self.top_depth >= self.bottom_depth:
            self.validation_label.setText(self._text["interval_error"])
            self.top_input.setFocus()
            return
        components = self.components()
        if "__duplicate__" in components:
            self.validation_label.setText(self._text["duplicate_error"])
            self.tabs.setCurrentIndex(0)
            return
        if not components or len(components) > 4 or abs(sum(components.values()) - 100.0) > 0.01:
            self.validation_label.setText(self._text["composition_error"])
            self.tabs.setCurrentIndex(0)
            first = next(
                (
                    control
                    for rock, control in zip(
                        self.rock_inputs, self.percent_inputs, strict=True
                    )
                    if rock.currentData()
                ),
                self.rock_inputs[0],
            )
            first.setFocus()
            return
        calcite = self.calcite_input.value() if self.calcite_input.value() >= 0 else 0.0
        dolomite = self.dolomite_input.value() if self.dolomite_input.value() >= 0 else 0.0
        if calcite + dolomite > 100.01:
            self.validation_label.setText(self._text["calc_error"])
            self.tabs.setCurrentIndex(1)
            self.calcite_input.setFocus()
            return
        self.accept()

    def _delete(self) -> None:
        self.delete_requested = True
        self.accept()
