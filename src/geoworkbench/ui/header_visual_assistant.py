from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.printing.header_fields import SUPPORTED_HEADER_FIELDS, header_field_label
from geoworkbench.services.localization import AppLanguage


class HeaderVisualAssistant(QGroupBox):
    """Contextual help and quick editing for the selected print-header block."""

    text_requested = Signal(str)
    field_requested = Signal(str)
    line_orientation_requested = Signal(str)
    properties_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        titles = {
            AppLanguage.RU: "Визуальный помощник",
            AppLanguage.KK: "Көрнекі көмекші",
            AppLanguage.EN: "Visual assistant",
        }
        super().__init__(titles[language], parent)
        self.language = language

        self.block_title = QLabel()
        self.block_title.setWordWrap(True)
        self.block_title.setStyleSheet("font-weight:700;")
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.source = QLabel()
        self.source.setWordWrap(True)
        self.source.setStyleSheet("color:#64748b;")
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color:#b91c1c; font-weight:600;")

        self.quick_text = QLineEdit()
        self.quick_text.setPlaceholderText(
            {
                AppLanguage.RU: "Введите текст блока",
                AppLanguage.KK: "Блок мәтінін енгізіңіз",
                AppLanguage.EN: "Enter block text",
            }[language]
        )
        self.apply_text_button = QPushButton(
            {
                AppLanguage.RU: "Вставить текст",
                AppLanguage.KK: "Мәтінді енгізу",
                AppLanguage.EN: "Insert text",
            }[language]
        )
        self.apply_text_button.clicked.connect(
            lambda: self.text_requested.emit(self.quick_text.text())
        )
        self.text_row = QWidget()
        text_layout = QHBoxLayout(self.text_row)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.addWidget(self.quick_text, 1)
        text_layout.addWidget(self.apply_text_button)

        self.field_combo = QComboBox()
        for field_name in SUPPORTED_HEADER_FIELDS:
            self.field_combo.addItem(
                f"{header_field_label(field_name, language)} — {field_name}",
                field_name,
            )
        self.apply_field_button = QPushButton(
            {
                AppLanguage.RU: "Вставить поле",
                AppLanguage.KK: "Өрісті енгізу",
                AppLanguage.EN: "Insert field",
            }[language]
        )
        self.apply_field_button.clicked.connect(
            lambda: self.field_requested.emit(str(self.field_combo.currentData() or ""))
        )
        self.field_row = QWidget()
        field_layout = QHBoxLayout(self.field_row)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.addWidget(self.field_combo, 1)
        field_layout.addWidget(self.apply_field_button)

        self.horizontal_button = QPushButton(
            {
                AppLanguage.RU: "Сделать горизонтальной",
                AppLanguage.KK: "Көлденең ету",
                AppLanguage.EN: "Make horizontal",
            }[language]
        )
        self.horizontal_button.clicked.connect(
            lambda: self.line_orientation_requested.emit("horizontal")
        )
        self.vertical_button = QPushButton(
            {
                AppLanguage.RU: "Сделать вертикальной",
                AppLanguage.KK: "Тік ету",
                AppLanguage.EN: "Make vertical",
            }[language]
        )
        self.vertical_button.clicked.connect(
            lambda: self.line_orientation_requested.emit("vertical")
        )
        self.line_row = QWidget()
        line_layout = QHBoxLayout(self.line_row)
        line_layout.setContentsMargins(0, 0, 0, 0)
        line_layout.addWidget(self.horizontal_button)
        line_layout.addWidget(self.vertical_button)

        self.properties_button = QPushButton(
            {
                AppLanguage.RU: "Открыть все свойства блока…",
                AppLanguage.KK: "Блоктың барлық қасиеттерін ашу…",
                AppLanguage.EN: "Open all block properties…",
            }[language]
        )
        self.properties_button.clicked.connect(self.properties_requested.emit)

        layout = QVBoxLayout(self)
        layout.addWidget(self.block_title)
        layout.addWidget(self.description)
        layout.addWidget(self.source)
        layout.addWidget(self.warning)
        layout.addWidget(self.text_row)
        layout.addWidget(self.field_row)
        layout.addWidget(self.line_row)
        layout.addWidget(self.properties_button)

        self.set_element(None, page_width_mm=0.0, header_height_mm=0.0)

    def set_element(
        self,
        element: MasterlogHeaderElement | None,
        *,
        page_width_mm: float,
        header_height_mm: float,
    ) -> None:
        self.text_row.setVisible(False)
        self.field_row.setVisible(False)
        self.line_row.setVisible(False)
        self.warning.clear()
        self.source.clear()
        self.properties_button.setEnabled(element is not None)

        if element is None:
            self.block_title.setText(
                {
                    AppLanguage.RU: "Выберите блок на листе или в списке слева",
                    AppLanguage.KK: "Беттен немесе сол жақ тізімнен блокты таңдаңыз",
                    AppLanguage.EN: "Select a block on the sheet or in the list",
                }[self.language]
            )
            self.description.setText(
                {
                    AppLanguage.RU: (
                        "После выбора здесь появятся назначение блока, предупреждения и быстрые "
                        "команды вставки. Двойной щелчок по блоку открывает полный набор свойств."
                    ),
                    AppLanguage.KK: (
                        "Таңдаудан кейін блоктың мақсаты, ескертулер және жылдам енгізу командалары "
                        "көрсетіледі. Қос шерту барлық қасиеттерді ашады."
                    ),
                    AppLanguage.EN: (
                        "After selection this panel shows the block purpose, warnings and quick "
                        "insert commands. Double-click opens all properties."
                    ),
                }[self.language]
            )
            return

        type_names = {
            AppLanguage.RU: {
                "text": "Текстовый блок",
                "field": "Автоматическое поле",
                "image": "Изображение или логотип",
                "line": "Линия-разделитель",
                "lithotype_swatch": "Образец литотипа",
                "lithology_legend": "Литологическая легенда",
                "lba_legend": "Легенда ЛБА",
            },
            AppLanguage.KK: {
                "text": "Мәтіндік блок",
                "field": "Автоматты өріс",
                "image": "Сурет немесе логотип",
                "line": "Бөлу сызығы",
                "lithotype_swatch": "Литотип үлгісі",
                "lithology_legend": "Литологиялық аңыз",
                "lba_legend": "ЛБА аңызы",
            },
            AppLanguage.EN: {
                "text": "Text block",
                "field": "Automatic field",
                "image": "Image or logo",
                "line": "Divider line",
                "lithotype_swatch": "Lithotype swatch",
                "lithology_legend": "Lithology legend",
                "lba_legend": "LBA legend",
            },
        }
        descriptions = {
            AppLanguage.RU: {
                "text": "Печатный текст. Его можно быстро заменить ниже или подробно оформить через свойства.",
                "field": "Значение автоматически берётся из проекта, скважины, набора данных или данных шапки.",
                "image": "Логотип или рисунок из каталога изображений. В свойствах доступны режим вписывания, поворот и прозрачность.",
                "line": "Разделитель таблицы. Для обычной шапки используйте горизонтальную или вертикальную линию.",
                "lithotype_swatch": "Образец породы с кодом и названием либо только рисунок.",
                "lithology_legend": "Автоматическая или ручная легенда литологии.",
                "lba_legend": "Условные обозначения люминесцентно-битуминологического анализа.",
            },
            AppLanguage.KK: {
                "text": "Баспа мәтіні. Оны төменде жылдам ауыстыруға немесе қасиеттер арқылы толық баптауға болады.",
                "field": "Мән жобадан, ұңғымадан, деректер жиынынан немесе тақырып деректерінен автоматты түрде алынады.",
                "image": "Кескіндер каталогындағы логотип немесе сурет. Қасиеттерде орналастыру, бұру және мөлдірлік бар.",
                "line": "Кесте бөлгіші. Қалыпты тақырып үшін көлденең немесе тік сызықты пайдаланыңыз.",
                "lithotype_swatch": "Коды және атауы бар жыныс үлгісі немесе тек сурет.",
                "lithology_legend": "Автоматты немесе қолмен жасалатын литология аңызы.",
                "lba_legend": "Люминесцентті-битуминологиялық талдау шартты белгілері.",
            },
            AppLanguage.EN: {
                "text": "Printable text. Replace it quickly below or use properties for complete styling.",
                "field": "The value is resolved automatically from the project, well, dataset or header data.",
                "image": "A logo or image from the image catalog. Properties control fit mode, rotation and opacity.",
                "line": "A table divider. Normal headers should use horizontal or vertical lines.",
                "lithotype_swatch": "A rock swatch with code/name or pattern only.",
                "lithology_legend": "Automatic or manually selected lithology legend.",
                "lba_legend": "Luminescent-bituminological analysis symbols.",
            },
        }
        element_type = element.element_type
        self.block_title.setText(type_names[self.language].get(element_type, element_type))
        self.description.setText(descriptions[self.language].get(element_type, ""))

        source_component = element.properties.get("source_component")
        if isinstance(source_component, str) and source_component:
            self.source.setText(
                {
                    AppLanguage.RU: f"Источник SKF: {source_component}",
                    AppLanguage.KK: f"SKF көзі: {source_component}",
                    AppLanguage.EN: f"SKF source: {source_component}",
                }[self.language]
            )

        right = element.x_mm + element.width_mm
        bottom = element.y_mm + element.height_mm
        warnings: list[str] = []
        if page_width_mm > 0.0 and right > page_width_mm + 1e-6:
            warnings.append(
                {
                    AppLanguage.RU: "Блок выходит за правую границу печатного листа.",
                    AppLanguage.KK: "Блок баспа бетінің оң жақ шекарасынан шығады.",
                    AppLanguage.EN: "The block extends beyond the right edge of the printed page.",
                }[self.language]
            )
        if header_height_mm > 0.0 and bottom > header_height_mm + 1e-6:
            warnings.append(
                {
                    AppLanguage.RU: "Блок выходит ниже установленной высоты шапки.",
                    AppLanguage.KK: "Блок тақырыптың белгіленген биіктігінен төмен шығады.",
                    AppLanguage.EN: "The block extends below the configured header height.",
                }[self.language]
            )

        if element_type == "text":
            value = element.properties.get("text", "")
            self.quick_text.setText(str(value) if isinstance(value, (str, int, float)) else "")
            self.text_row.setVisible(True)
            if not self.quick_text.text().strip():
                warnings.append(
                    {
                        AppLanguage.RU: "Текстовый блок пуст — в печати будет только рамка или пустое место.",
                        AppLanguage.KK: "Мәтіндік блок бос — баспада тек жақтау немесе бос орын болады.",
                        AppLanguage.EN: "The text block is empty; printing will show only its frame or blank space.",
                    }[self.language]
                )
        elif element_type == "field":
            field_name = element.properties.get("field")
            if isinstance(field_name, str):
                index = self.field_combo.findData(field_name)
                if index >= 0:
                    self.field_combo.setCurrentIndex(index)
            self.field_row.setVisible(True)
        elif element_type == "line":
            self.line_row.setVisible(True)
            if abs(element.width_mm) > 0.5 and abs(element.height_mm) > 0.5:
                warnings.append(
                    {
                        AppLanguage.RU: (
                            "Линия диагональная и будет напечатана по диагонали. Используйте одну "
                            "из кнопок ниже, если это разделитель таблицы."
                        ),
                        AppLanguage.KK: (
                            "Сызық қиғаш және баспада да қиғаш болады. Егер бұл кесте бөлгіші болса, "
                            "төмендегі батырмалардың бірін пайдаланыңыз."
                        ),
                        AppLanguage.EN: (
                            "This line is diagonal and will print diagonally. Use one of the buttons "
                            "below when it is intended as a table divider."
                        ),
                    }[self.language]
                )

        self.warning.setText("\n".join(warnings))
