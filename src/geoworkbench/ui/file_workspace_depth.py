from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QTabWidget,
    QWidget,
)

from geoworkbench.files.well_depth_reference import (
    DepthReferenceKind,
    calculate_well_depth_position,
)
from geoworkbench.ui.file_workspace_runtime import FileWorkspaceWidget as _RuntimeWorkspace


_TEXT: dict[str, dict[str, str]] = {
    "ru": {
        "tab": "Отметки и долото",
        "title": "Альтитуда точки отсчёта и положение долота",
        "help": (
            "Введите абсолютную отметку поверхности земли GL относительно среднего уровня моря и "
            "фактическую высоту выбранной точки отсчёта глубины над GL. Высота всей буровой вышки "
            "не используется. MD измеряется вдоль ствола от выбранного datum до долота. Для наклонной "
            "скважины TVD берите из инклинометрии или модели траектории — MD вместо TVD подставлять нельзя."
        ),
        "ground": "Отметка поверхности GL относительно MSL:",
        "reference": "Точка отсчёта глубины:",
        "height": "Высота выбранного datum над GL:",
        "md": "MD до долота от выбранного datum:",
        "vertical": "Вертикальная скважина: принять TVD = MD",
        "tvd": "TVD до долота от того же datum:",
        "result": "Результат:",
        "ground_tip": "Абсолютная высота поверхности земли в точке скважины относительно среднего уровня моря.",
        "reference_tip": "Выберите ровно ту точку, которая указана в буровом рапорте, инклинометрии или шапке каротажа.",
        "height_tip": "Вертикальное превышение выбранной точки RT, RKB/KB, DF или другого datum над GL. Используйте паспорт или схему высот буровой.",
        "md_tip": "Измеренная глубина по траектории ствола от выбранного datum до фактического положения долота.",
        "vertical_tip": "Допустимо только для вертикальной скважины или когда TVD официально принято равным MD.",
        "tvd_tip": "Истинная вертикальная глубина от того же datum до долота. Для наклонной скважины берётся из инклинометрии.",
        "ground_out": "GL относительно MSL",
        "datum_out": "Абсолютная отметка {datum}",
        "bit_out": "Абсолютная отметка долота",
        "tvdss_out": "TVDSS, положительно вниз от MSL",
        "below_ground_out": "Долото ниже GL по вертикали",
        "difference_out": "MD − TVD",
        "warning": "Не смешивайте datum: GL, RT, RKB/KB и DF могут иметь разные нулевые отметки.",
        "error": "Ошибка исходных данных: {error}",
        "rkb": "RKB/KB — верх ведущей втулки",
        "rt": "RT — отметка роторного стола",
        "df": "DF — пол буровой",
        "gl": "GL — поверхность земли",
        "custom": "Другая документированная точка",
    },
    "kk": {
        "tab": "Белгілер және қашау",
        "title": "Тереңдік datum-ының альтитудасы және қашаудың орны",
        "help": (
            "GL жер бетінің орташа теңіз деңгейіне қатысты абсолюттік белгісін және таңдалған тереңдік "
            "datum-ының GL үстіндегі нақты биіктігін енгізіңіз. Бұрғылау мұнарасының толық биіктігі есепке "
            "алынбайды. MD таңдалған datum-нан қашауға дейін ұңғыма траекториясы бойымен өлшенеді. Көлбеу "
            "ұңғыма үшін TVD инклинометриядан немесе траектория моделінен алынуы тиіс; MD-ны TVD орнына қолданбаңыз."
        ),
        "ground": "GL белгісі, MSL-ге қатысты:",
        "reference": "Тереңдік есептеу нүктесі:",
        "height": "Таңдалған datum-ның GL үстіндегі биіктігі:",
        "md": "Таңдалған datum-нан қашауға дейінгі MD:",
        "vertical": "Тік ұңғыма: TVD = MD деп қабылдау",
        "tvd": "Сол datum-нан қашауға дейінгі TVD:",
        "result": "Нәтиже:",
        "ground_tip": "Ұңғыма нүктесіндегі жер бетінің орташа теңіз деңгейіне қатысты абсолюттік биіктігі.",
        "reference_tip": "Бұрғылау рапортында, инклинометрияда немесе каротаж тақырыбында көрсетілген нүктені таңдаңыз.",
        "height_tip": "RT, RKB/KB, DF немесе басқа datum-ның GL үстіндегі тік артуы. Қондырғы паспорты немесе биіктік сызбасын пайдаланыңыз.",
        "md_tip": "Таңдалған datum-нан қашаудың нақты орнына дейін ұңғыма траекториясы бойымен өлшенген тереңдік.",
        "vertical_tip": "Тек тік ұңғымада немесе TVD ресми түрде MD-ға тең деп қабылданғанда қолданыңыз.",
        "tvd_tip": "Сол datum-нан қашауға дейінгі шынайы тік тереңдік. Көлбеу ұңғымада инклинометриядан алынады.",
        "ground_out": "GL-дің MSL-ге қатысты белгісі",
        "datum_out": "{datum} абсолюттік белгісі",
        "bit_out": "Қашаудың абсолюттік белгісі",
        "tvdss_out": "TVDSS, MSL-ден төмен оң мән",
        "below_ground_out": "Қашаудың GL-ден төмен тік тереңдігі",
        "difference_out": "MD − TVD",
        "warning": "Datum-дарды араластырмаңыз: GL, RT, RKB/KB және DF нөлдері әртүрлі болуы мүмкін.",
        "error": "Бастапқы деректер қатесі: {error}",
        "rkb": "RKB/KB — жетекші төлкенің жоғарғы жағы",
        "rt": "RT — ротор үстелінің белгісі",
        "df": "DF — бұрғылау едені",
        "gl": "GL — жер беті",
        "custom": "Басқа құжатталған нүкте",
    },
    "en": {
        "tab": "Elevations and bit",
        "title": "Depth-datum elevation and bit position",
        "help": (
            "Enter the ground-level elevation GL relative to mean sea level and the documented vertical "
            "height of the selected depth datum above GL. The full derrick or mast height is not used. "
            "MD is measured along the well path from the selected datum to the bit. For a deviated well, "
            "obtain TVD from the directional survey or trajectory model; do not substitute MD for TVD."
        ),
        "ground": "Ground elevation GL relative to MSL:",
        "reference": "Depth reference datum:",
        "height": "Selected datum height above GL:",
        "md": "MD from selected datum to bit:",
        "vertical": "Vertical well: use TVD = MD",
        "tvd": "TVD from the same datum to bit:",
        "result": "Result:",
        "ground_tip": "Absolute ground-level elevation at the well location relative to mean sea level.",
        "reference_tip": "Select exactly the datum stated in the drilling report, directional survey or log heading.",
        "height_tip": "Vertical offset of RT, RKB/KB, DF or another datum above GL. Use controlled rig documentation.",
        "md_tip": "Measured depth along the well path from the selected datum to the actual bit position.",
        "vertical_tip": "Use only for a vertical well or when TVD is formally defined as equal to MD.",
        "tvd_tip": "True vertical depth from the same datum to the bit. For a deviated well, use directional-survey data.",
        "ground_out": "GL elevation relative to MSL",
        "datum_out": "Absolute {datum} elevation",
        "bit_out": "Absolute bit elevation",
        "tvdss_out": "TVDSS, positive downward from MSL",
        "below_ground_out": "Bit vertically below GL",
        "difference_out": "MD − TVD",
        "warning": "Do not mix datums: GL, RT, RKB/KB and DF may define different zero points.",
        "error": "Input error: {error}",
        "rkb": "RKB/KB — top of kelly bushing",
        "rt": "RT — rotary-table elevation",
        "df": "DF — drill floor",
        "gl": "GL — ground level",
        "custom": "Other documented datum",
    },
}


class FileWorkspaceWidget(_RuntimeWorkspace):
    """Files workspace with a controlled well-depth reference calculator."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent, language=language)
        self._replace_legacy_altitude_calculators()

    def _d(self, key: str, **values: object) -> str:
        language = self.language if self.language in _TEXT else "ru"
        return _TEXT[language][key].format(**values)

    def _replace_legacy_altitude_calculators(self) -> None:
        legacy_group = None
        datum_inputs: Any = getattr(self, "datum_inputs", None)
        if datum_inputs:
            legacy_group = datum_inputs[0].parentWidget()
        if isinstance(legacy_group, QGroupBox):
            legacy_group.hide()
            legacy_group.setToolTip(self._d("warning"))

        tabs = self.findChild(QTabWidget, "petroleumCalculatorTabs")
        if tabs is None:
            return
        old_page = tabs.widget(3) if tabs.count() > 3 else None
        if old_page is not None:
            tabs.removeTab(3)
            old_page.hide()
            old_page.setParent(None)
            old_page.deleteLater()
        tabs.insertTab(3, self._build_well_depth_calculator(tabs), self._d("tab"))

    def _build_well_depth_calculator(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        page.setObjectName("wellDepthCalculator")
        layout = QFormLayout(page)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        title = QLabel(f"<b>{self._d('title')}</b>", page)
        title.setWordWrap(True)
        layout.addRow(title)
        help_label = QLabel(self._d("help"), page)
        help_label.setObjectName("hint")
        help_label.setWordWrap(True)
        layout.addRow(help_label)

        self.depth_ground_elevation = self._depth_spin(120.0, -20_000.0, 20_000.0)
        self.depth_reference_kind = QComboBox(page)
        references = (
            ("rkb", DepthReferenceKind.RKB),
            ("rt", DepthReferenceKind.RT),
            ("df", DepthReferenceKind.DF),
            ("gl", DepthReferenceKind.GL),
            ("custom", DepthReferenceKind.CUSTOM),
        )
        for text_key, value in references:
            self.depth_reference_kind.addItem(self._d(text_key), value)
        self.depth_datum_height = self._depth_spin(8.0, -500.0, 500.0)
        self.depth_measured_depth = self._depth_spin(2_500.0, 0.0, 50_000.0)
        self.depth_vertical_well = QCheckBox(self._d("vertical"), page)
        self.depth_vertical_well.setChecked(True)
        self.depth_true_vertical_depth = self._depth_spin(2_500.0, 0.0, 50_000.0)
        self.depth_true_vertical_depth.setEnabled(False)
        self.depth_result = QLabel(page)
        self.depth_result.setObjectName("statusCard")
        self.depth_result.setWordWrap(True)
        self.depth_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.depth_result.setMinimumHeight(170)

        self.depth_ground_elevation.setToolTip(self._d("ground_tip"))
        self.depth_reference_kind.setToolTip(self._d("reference_tip"))
        self.depth_datum_height.setToolTip(self._d("height_tip"))
        self.depth_measured_depth.setToolTip(self._d("md_tip"))
        self.depth_vertical_well.setToolTip(self._d("vertical_tip"))
        self.depth_true_vertical_depth.setToolTip(self._d("tvd_tip"))

        layout.addRow(self._d("ground"), self.depth_ground_elevation)
        layout.addRow(self._d("reference"), self.depth_reference_kind)
        layout.addRow(self._d("height"), self.depth_datum_height)
        layout.addRow(self._d("md"), self.depth_measured_depth)
        layout.addRow("", self.depth_vertical_well)
        layout.addRow(self._d("tvd"), self.depth_true_vertical_depth)
        layout.addRow(self._d("result"), self.depth_result)

        self.depth_ground_elevation.valueChanged.connect(self._update_well_depth_calculator)
        self.depth_reference_kind.currentIndexChanged.connect(self._reference_kind_changed)
        self.depth_datum_height.valueChanged.connect(self._update_well_depth_calculator)
        self.depth_measured_depth.valueChanged.connect(self._measured_depth_changed)
        self.depth_vertical_well.toggled.connect(self._vertical_well_changed)
        self.depth_true_vertical_depth.valueChanged.connect(self._update_well_depth_calculator)
        self._reference_kind_changed()
        self._update_well_depth_calculator()
        return page

    @staticmethod
    def _depth_spin(value: float, minimum: float, maximum: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(minimum, maximum)
        control.setDecimals(3)
        control.setSingleStep(0.1)
        control.setValue(value)
        control.setSuffix(" m")
        control.setMinimumWidth(220)
        return control

    def _current_reference_kind(self) -> DepthReferenceKind:
        value = self.depth_reference_kind.currentData()
        if isinstance(value, DepthReferenceKind):
            return value
        try:
            return DepthReferenceKind(str(value))
        except ValueError:
            return DepthReferenceKind.CUSTOM

    def _reference_kind_changed(self, *_args: object) -> None:
        is_ground = self._current_reference_kind() == DepthReferenceKind.GL
        self.depth_datum_height.setEnabled(not is_ground)
        if is_ground and self.depth_datum_height.value() != 0.0:
            self.depth_datum_height.setValue(0.0)
        self._update_well_depth_calculator()

    def _measured_depth_changed(self, value: float) -> None:
        if self.depth_vertical_well.isChecked():
            self.depth_true_vertical_depth.blockSignals(True)
            self.depth_true_vertical_depth.setValue(value)
            self.depth_true_vertical_depth.blockSignals(False)
        self._update_well_depth_calculator()

    def _vertical_well_changed(self, checked: bool) -> None:
        self.depth_true_vertical_depth.setEnabled(not checked)
        if checked:
            self.depth_true_vertical_depth.setValue(self.depth_measured_depth.value())
        self._update_well_depth_calculator()

    def _update_well_depth_calculator(self, *_args: object) -> None:
        try:
            kind = self._current_reference_kind()
            result = calculate_well_depth_position(
                ground_elevation_msl_m=self.depth_ground_elevation.value(),
                datum_height_above_ground_m=(
                    0.0 if kind == DepthReferenceKind.GL else self.depth_datum_height.value()
                ),
                measured_depth_m=self.depth_measured_depth.value(),
                true_vertical_depth_m=self.depth_true_vertical_depth.value(),
            )
            datum_name = self.depth_reference_kind.currentText().split(" — ", 1)[0]
            self.depth_result.setText(
                f"{self._d('ground_out')}: <b>{result.ground_elevation_msl_m:.3f} m</b><br>"
                f"{self._d('datum_out', datum=datum_name)}: "
                f"<b>{result.datum_elevation_msl_m:.3f} m</b><br>"
                f"MD: {result.measured_depth_m:.3f} m; TVD: {result.true_vertical_depth_m:.3f} m<br>"
                f"{self._d('bit_out')}: <b>{result.bit_elevation_msl_m:.3f} m</b><br>"
                f"{self._d('tvdss_out')}: {result.true_vertical_depth_subsea_m:.3f} m<br>"
                f"{self._d('below_ground_out')}: {result.bit_below_ground_m:.3f} m<br>"
                f"{self._d('difference_out')}: {result.md_minus_tvd_m:.3f} m<br>"
                f"<i>{self._d('warning')}</i>"
            )
        except Exception as error:
            self.depth_result.setText(self._d("error", error=error))
