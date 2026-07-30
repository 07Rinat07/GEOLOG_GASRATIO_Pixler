from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from geoworkbench.files.document_service import DocumentError, DocumentKind
from geoworkbench.ui.file_workspace_geometry import eraser_stroke_rectangles
from geoworkbench.ui.file_workspace_v3 import FileWorkspaceWidget as _LocalizedWorkspace


_STANDARD_UNIT_LABELS: dict[str, str] = {
    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "km": "km",
    "in": "in",
    "ft": "ft",
    "yd": "yd",
    "pa": "Pa",
    "kpa": "kPa",
    "mpa": "MPa",
    "bar": "bar",
    "atm": "atm",
    "psi": "psi",
    "mmhg": "mmHg",
    "kgf_cm2": "kgf/cm²",
    "c": "°C",
    "f": "°F",
    "k": "K",
    "mm2": "mm²",
    "cm2": "cm²",
    "m2": "m²",
    "ha": "ha",
    "in2": "in²",
    "ft2": "ft²",
    "ml": "mL",
    "l": "L",
    "m3": "m³",
    "cm3": "cm³",
    "in3": "in³",
    "ft3": "ft³",
    "bbl": "bbl",
    "mg": "mg",
    "g": "g",
    "kg": "kg",
    "t": "t",
    "lb": "lb",
    "n": "N",
    "kn": "kN",
    "kgf": "kgf",
    "lbf": "lbf",
    "nm": "N·m",
    "knm": "kN·m",
    "kgfm": "kgf·m",
    "lbfft": "lbf·ft",
    "kg_m3": "kg/m³",
    "g_cm3": "g/cm³",
    "lb_ft3": "lb/ft³",
    "ppg": "ppg",
    "m3_s": "m³/s",
    "m3_h": "m³/h",
    "l_s": "L/s",
    "l_min": "L/min",
    "bbl_d": "bbl/d",
    "gpm": "US gal/min",
    "m_s": "m/s",
    "km_h": "km/h",
    "ft_s": "ft/s",
    "mph": "mph",
    "j": "J",
    "kj": "kJ",
    "mj": "MJ",
    "kwh": "kWh",
    "btu": "BTU",
    "rad": "rad",
    "deg": "°",
}

_CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "kk": {
        "length": "Ұзындық",
        "pressure": "Қысым",
        "temperature": "Температура",
        "area": "Аудан",
        "volume": "Көлем",
        "mass": "Масса",
        "force": "Күш",
        "torque": "Айналу моменті",
        "density": "Тығыздық",
        "flow": "Шығын",
        "speed": "Жылдамдық",
        "energy": "Энергия",
        "angle": "Бұрыш",
    },
    "en": {
        "length": "Length",
        "pressure": "Pressure",
        "temperature": "Temperature",
        "area": "Area",
        "volume": "Volume",
        "mass": "Mass",
        "force": "Force",
        "torque": "Torque",
        "density": "Density",
        "flow": "Flow rate",
        "speed": "Speed",
        "energy": "Energy",
        "angle": "Angle",
    },
}

_DATUM_TEXT: dict[str, dict[str, object]] = {
    "ru": {
        "hint": (
            "Цепочка: GL = datum + смещение GL; Wellhead = GL + высота устья; "
            "DF = GL + высота пола; RT = DF + превышение RT; "
            "KB/RKB = RT + превышение втулки.\n"
            "Укажите RT над DF = 0, если эти отметки в документации приняты одинаковыми."
        ),
        "tips": (
            "Известная абсолютная высота исходного datum относительно принятой системы высот.",
            "GL (Ground Level) — уровень земли. Положительное значение означает, что GL выше datum.",
            "Wellhead — устье скважины. Введите вертикальную высоту устья над уровнем земли.",
            "DF (Drill Floor) — рабочая площадка буровой, а не роторный стол.",
            "RT (Rotary Table) — отдельное оборудование. Введите 0, если отметки DF и RT совпадают.",
            "KB/RKB — верх ведущей втулки над RT; эта точка часто является datum глубины.",
        ),
    },
    "kk": {
        "hint": (
            "Тізбек: GL = datum + GL ығысуы; Wellhead = GL + саға биіктігі; "
            "DF = GL + бұрғылау еденінің биіктігі; RT = DF + RT артуы; "
            "KB/RKB = RT + төлке биіктігі.\n"
            "Құжатта DF және RT белгілері бірдей болса, RT над DF = 0 енгізіңіз."
        ),
        "tips": (
            "Қабылданған биіктік жүйесіндегі бастапқы datum абсолюттік белгісі.",
            "GL (Ground Level) — жер деңгейі. Оң мән GL datum-нан жоғары екенін білдіреді.",
            "Wellhead — ұңғыма сағасы. GL үстіндегі тік биіктікті енгізіңіз.",
            "DF (Drill Floor) — бұрғылау қондырғысының жұмыс алаңы, ротор үстелі емес.",
            "RT (Rotary Table) — жеке жабдық. Құжатта DF және RT бірдей болса, 0 енгізіңіз.",
            "KB/RKB — RT үстіндегі жетекші төлкенің жоғарғы белгісі; ол тереңдік datum-ы болуы мүмкін.",
        ),
    },
    "en": {
        "hint": (
            "Chain: GL = datum + GL offset; Wellhead = GL + wellhead height; "
            "DF = GL + drill-floor height; RT = DF + RT offset; "
            "KB/RKB = RT + bushing height.\n"
            "Enter RT above DF = 0 when the documentation defines the DF and RT elevations as equal."
        ),
        "tips": (
            "Known absolute elevation of the source datum in the selected vertical reference system.",
            "GL (Ground Level) is the ground elevation. A positive offset places GL above the datum.",
            "Wellhead is the wellhead elevation. Enter its vertical height above GL.",
            "DF (Drill Floor) is the working platform of the rig, not the rotary table.",
            "RT (Rotary Table) is separate equipment. Enter 0 when the documented DF and RT elevations are equal.",
            "KB/RKB is the top of the kelly bushing above RT and is often used as a depth datum.",
        ),
    },
}

_PAGE_TEXT: dict[str, tuple[str, str, str, str]] = {
    "ru": (
        "Страница —",
        "Страница {current} / {count}",
        "изменён",
        "Откройте PDF или изображение",
    ),
    "kk": (
        "Бет —",
        "{current} / {count} бет",
        "өзгертілді",
        "PDF немесе кескінді ашыңыз",
    ),
    "en": (
        "Page —",
        "Page {current} / {count}",
        "modified",
        "Open a PDF or image",
    ),
}


class FileWorkspaceWidget(_LocalizedWorkspace):
    """Release candidate workspace with verified layout and remaining localization fixes."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent, language=language)
        self._repair_logo_help_layout()
        self._localize_datum_details()
        self._localize_converter_labels()
        self._localize_field_units()
        self._refresh_localized_document_labels()

    def _repair_logo_help_layout(self) -> None:
        page = self.sections.widget(2)
        if page is None:
            return
        card = page.findChild(QFrame, "expertHelpCard")
        controls = self.logo_text.parentWidget()
        form = controls.layout() if controls is not None else None
        page_layout = page.layout()
        if card is None or not isinstance(form, QFormLayout) or page_layout is None:
            return
        page_layout.removeWidget(card)
        card.setParent(controls)
        form.insertRow(0, card)

    def _localize_datum_details(self) -> None:
        if not self.datum_inputs:
            return
        language = self.language if self.language in _DATUM_TEXT else "ru"
        values = _DATUM_TEXT[language]
        tips = values["tips"]
        if not isinstance(tips, tuple):
            return
        group = self.datum_inputs[0].parentWidget()
        for control, tip in zip(self.datum_inputs, tips, strict=True):
            control.setToolTip(str(tip))
        if group is None:
            return
        hints = [
            label
            for label in group.findChildren(QLabel)
            if label.objectName() == "hint"
        ]
        if hints:
            hints[-1].setText(str(values["hint"]))
        layout = group.layout()
        if isinstance(layout, QGridLayout):
            for index, tip in enumerate(tips):
                item = layout.itemAtPosition(index, 0)
                label = item.widget() if item is not None else None
                if isinstance(label, QLabel):
                    label.setToolTip(str(tip))

    def _localize_converter_labels(self) -> None:
        if self.language not in {"kk", "en"}:
            return
        labels = _CATEGORY_LABELS[self.language]
        for index in range(self.converter_category.count()):
            key = str(self.converter_category.itemData(index))
            if key in labels:
                self.converter_category.setItemText(index, labels[key])
        self._relabel_combo_units(self.converter_source)
        self._relabel_combo_units(self.converter_target)

    @staticmethod
    def _relabel_combo_units(combo: QComboBox) -> None:
        for index in range(combo.count()):
            key = str(combo.itemData(index))
            label = _STANDARD_UNIT_LABELS.get(key)
            if label is not None:
                combo.setItemText(index, label)

    def _localize_field_units(self) -> None:
        if self.language != "en":
            return
        suffixes: dict[str, str] = {
            "pipe_wall_mm": " mm",
            "pipe_length_m": " m",
            "pipe_density": " kg/m³",
            "drill_mud_density": " kg/m³",
            "drill_tvd": " m",
            "drill_hole_d": " mm",
            "drill_pipe_d": " mm",
            "drill_interval": " m",
            "drill_flow": " L/s",
            "mud_density": " kg/m³",
            "mud_annular_loss": " MPa",
            "mud_tvd": " m",
            "mix_v1": " m³",
            "mix_rho1": " kg/m³",
            "mix_v2": " m³",
            "mix_rho2": " kg/m³",
            "geo_reference": " m",
            "geo_top_tvd": " m",
            "geo_bottom_tvd": " m",
        }
        for name, suffix in suffixes.items():
            control: Any = getattr(self, name, None)
            if isinstance(control, (QDoubleSpinBox, QSpinBox)):
                control.setSuffix(suffix)

    def _update_converter_units(self) -> None:
        super()._update_converter_units()
        if self.language in {"kk", "en"}:
            self._relabel_combo_units(self.converter_source)
            self._relabel_combo_units(self.converter_target)

    def _apply_eraser_stroke(self, points: list[QPointF], brush_size: int) -> None:
        rects = eraser_stroke_rectangles(points, brush_size, self._render_zoom)
        try:
            self._enhanced_service().erase_pdf_rects(rects)
            self._refresh_document()
            self.document_status.setText(self._t("eraser_done"))
        except DocumentError as error:
            self._show_error(self._t("tool_eraser"), error)

    def _refresh_document(self) -> None:
        super()._refresh_document()
        self._refresh_localized_document_labels()

    def _refresh_localized_document_labels(self) -> None:
        empty_page, page_pattern, dirty_word, open_prompt = _PAGE_TEXT.get(
            self.language, _PAGE_TEXT["ru"]
        )
        if not self.document_service.is_open:
            self.page_label.setText(empty_page)
            if self.document_canvas.pixmap() is None:
                self.document_canvas.setText(open_prompt)
            return
        self.page_label.setText(
            page_pattern.format(
                current=self.document_service.page_index + 1,
                count=self.document_service.page_count,
            )
        )
        path = self.document_service.path
        dirty = f" • {dirty_word}" if self.document_service.dirty else ""
        fallback = self._t("document")
        self.document_status.setText(f"{path or fallback}{dirty}")
        kind = "PDF" if self.document_service.kind is DocumentKind.PDF else self._t("image")
        if path is not None:
            self._document_info.setText(
                self._t(
                    "document_summary",
                    name=f"<b>{path.name}</b>",
                    kind=kind,
                    count=self.document_service.page_count,
                )
            )
