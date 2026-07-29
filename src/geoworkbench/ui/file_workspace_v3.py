from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QWidget,
)

from geoworkbench.ui.file_workspace_v2 import FileWorkspaceWidget as _V2FileWorkspaceWidget


_TRANSLATIONS: dict[str, tuple[str, str]] = {
    "Выберите страницу и выделите область мышью. Затем примените контекстную команду и сохраните копию документа.": (
        "Өшіргіш үшін режимді қосып, сол жақ батырманы басып ұстап бетпен жүргізіңіз. Мәтін үшін тікбұрышты аймақты белгілеңіз. Нәтижені бөлек көшірме ретінде сақтаңыз.",
        "For the eraser, enable the mode and drag across the page while holding the left mouse button. For text, select a rectangular area. Save the result as a separate copy.",
    ),
    "Результаты обновляются сразу. После смены категории или единиц старое значение очищается и рассчитывается заново.": (
        "Нәтижелер бірден жаңартылады. Санат немесе өлшем бірлігі өзгергенде ескі мән тазартылып, қайта есептеледі.",
        "Results update immediately. When the category or units change, the old value is cleared and recalculated.",
    ),
    "Пакетные операции с PDF": ("PDF топтық операциялары", "Batch PDF operations"),
    "Объединение сохраняет порядок выбранных файлов. Разделение создаёт отдельный PDF для каждой страницы. Экспорт DOCX переносит доступный текст без OCR.": (
        "Біріктіру таңдалған файлдардың ретін сақтайды. Бөлу әр бетке жеке PDF жасайды. DOCX экспорты OCR қолданбай қолжетімді мәтінді тасымалдайды.",
        "Merge preserves the selected file order. Split creates a separate PDF for each page. DOCX export transfers available text without OCR.",
    ),
    "Здесь появится журнал: исходный файл, созданный результат и количество страниц.": (
        "Мұнда бастапқы файл, жасалған нәтиже және бет саны көрсетіледі.",
        "The source file, created result and page count will appear here.",
    ),
    "Экспорт в Word:": ("Word форматына экспорт:", "Export to Word:"),
    "Сохранить вид страниц...": ("Бет көрінісін сақтау...", "Preserve page appearance..."),
    "Извлечь только текст...": ("Тек мәтінді шығару...", "Extract text only..."),
    "Объединить PDF...": ("PDF біріктіру...", "Merge PDF..."),
    "Разделить PDF...": ("PDF бөлу...", "Split PDF..."),
    "Здесь появится результат операции": ("Операция нәтижесі осында көрсетіледі", "The operation result will appear here"),
    "Текст:": ("Мәтін:", "Text:"),
    "Ширина, px:": ("Ені, px:", "Width, px:"),
    "Высота, px:": ("Биіктігі, px:", "Height, px:"),
    "Шрифт, px:": ("Қаріп, px:", "Font, px:"),
    "Цвет текста:": ("Мәтін түсі:", "Text color:"),
    "Цвет фона:": ("Фон түсі:", "Background color:"),
    "Прозрачный фон": ("Мөлдір фон", "Transparent background"),
    "Рамка, px:": ("Жиек, px:", "Border, px:"),
    "Цвет рамки:": ("Жиек түсі:", "Border color:"),
    "Обновить предпросмотр": ("Алдын ала қарауды жаңарту", "Refresh preview"),
    "Сохранить логотип...": ("Логотипті сақтау...", "Save logo..."),
    "Предпросмотр": ("Алдын ала қарау", "Preview"),
    "Быстрые стили": ("Жылдам стильдер", "Quick styles"),
    "Строгий светлый": ("Қатаң ашық", "Clean light"),
    "Геологический": ("Геологиялық", "Geological"),
    "Технический синий": ("Техникалық көк", "Technical blue"),
    "Прозрачный": ("Мөлдір", "Transparent"),
    "Источники нового архива": ("Жаңа мұрағат көздері", "New archive sources"),
    "Добавить файлы...": ("Файлдарды қосу...", "Add files..."),
    "Добавить папку...": ("Буманы қосу...", "Add folder..."),
    "Очистить": ("Тазалау", "Clear"),
    "Формат:": ("Формат:", "Format:"),
    "Создать архив...": ("Мұрағат жасау...", "Create archive..."),
    "Показать состав архива...": ("Мұрағат құрамын көрсету...", "Inspect archive..."),
    "Распаковать архив...": ("Мұрағатты ашу...", "Extract archive..."),
    "Элемент": ("Элемент", "Item"),
    "Размер": ("Өлшем", "Size"),
    "Тип": ("Түрі", "Type"),
    "Инженерный калькулятор": ("Инженерлік калькулятор", "Engineering calculator"),
    "Конвертер единиц": ("Өлшем бірліктерін түрлендіру", "Unit converter"),
    "Категория": ("Санат", "Category"),
    "Значение": ("Мән", "Value"),
    "Из": ("Бастапқы", "From"),
    "В": ("Нәтиже бірлігі", "To"),
    "Результат": ("Нәтиже", "Result"),
    "Преобразовать": ("Түрлендіру", "Convert"),
    "⇄ Поменять местами": ("⇄ Орындарын ауыстыру", "⇄ Swap units"),
    "Высотные отметки буровой и привязка глубины": (
        "Бұрғылау қондырғысының биіктік белгілері және тереңдік байланысы",
        "Rig elevations and depth reference",
    ),
    "Рассчитать отметки": ("Белгілерді есептеу", "Calculate elevations"),
    "Уровень": ("Деңгей", "Level"),
    "Абсолютная отметка, м": ("Абсолюттік белгі, м", "Absolute elevation, m"),
    "Нефтегазовые, буровые и геологические расчёты": (
        "Мұнай-газ, бұрғылау және геологиялық есептеулер",
        "Oilfield, drilling and geological calculations",
    ),
    "Расчёты выполняются в SI. Проверяйте исходные данные по рабочей программе, паспорту буровой и утверждённой гидравлической модели; результаты являются инженерной проверкой, а не заменой проектного расчёта.": (
        "Есептеулер SI жүйесінде орындалады. Бастапқы деректерді жұмыс бағдарламасы, бұрғылау қондырғысының паспорты және бекітілген гидравликалық модель бойынша тексеріңіз; нәтиже жобалық есептің орнына емес, инженерлік тексеруге арналған.",
        "Calculations use SI units. Verify inputs against the drilling program, rig documentation and approved hydraulic model; results are an engineering check, not a replacement for a design calculation.",
    ),
    "Трубы": ("Құбырлар", "Pipes"),
    "Бурение": ("Бұрғылау", "Drilling"),
    "Буровой раствор": ("Бұрғылау ерітіндісі", "Drilling fluid"),
    "Геология": ("Геология", "Geology"),
    "Наружный диаметр, дюймы:": ("Сыртқы диаметр, дюйм:", "Outer diameter, inches:"),
    "Толщина стенки:": ("Қабырға қалыңдығы:", "Wall thickness:"),
    "Длина:": ("Ұзындығы:", "Length:"),
    "Плотность материала:": ("Материал тығыздығы:", "Material density:"),
    "Результат:": ("Нәтиже:", "Result:"),
    "Плотность раствора": ("Ерітінді тығыздығы", "Fluid density"),
    "Диаметр ствола": ("Ұңғыма диаметрі", "Hole diameter"),
    "Наружный диаметр трубы": ("Құбырдың сыртқы диаметрі", "Pipe outer diameter"),
    "Длина интервала": ("Интервал ұзындығы", "Interval length"),
    "Расход насосов": ("Сорғы шығыны", "Pump rate"),
    "Потери давления в затрубье": ("Сақиналы кеңістіктегі қысым шығыны", "Annular pressure loss"),
    "Объём 1": ("1-көлем", "Volume 1"),
    "Плотность 1": ("1-тығыздық", "Density 1"),
    "Объём 2": ("2-көлем", "Volume 2"),
    "Плотность 2": ("2-тығыздық", "Density 2"),
    "Абсолютная отметка datum:": ("Datum абсолюттік белгісі:", "Datum elevation:"),
    "TVD кровли:": ("Қабат төбесінің TVD:", "Top TVD:"),
    "TVD подошвы:": ("Қабат табанының TVD:", "Bottom TVD:"),
    "Документ": ("Құжат", "Document"),
    "Страницы": ("Беттер", "Pages"),
    "Быстрый порядок работы": ("Жылдам жұмыс тәртібі", "Quick workflow"),
    "Выделенная область": ("Белгіленген аймақ", "Selected area"),
    "Область не выбрана": ("Аймақ белгіленбеген", "No area selected"),
    "Состояние": ("Күйі", "Status"),
}


_LONG_TRANSLATIONS: dict[str, tuple[str, str]] = {
    "Введите наружный диаметр в дюймах: 7 1/2, 7½, 7.5 или 7,5. Прямой перевод 7 1/2″ равен 190,5 мм. Для внутреннего диаметра и массы нужна толщина стенки.": (
        "Сыртқы диаметрді дюйммен енгізіңіз: 7 1/2, 7½, 7.5 немесе 7,5. 7 1/2″ тікелей аудармасы 190,5 мм. Ішкі диаметр мен массаны есептеу үшін қабырға қалыңдығы қажет.",
        "Enter the outer diameter in inches: 7 1/2, 7½, 7.5 or 7.5. A direct conversion of 7 1/2″ is 190.5 mm. Wall thickness is required for inner diameter and mass.",
    ),
    "Гидростатическое давление считается по истинной вертикальной глубине TVD, а не по MD. Кольцевой объём определяется разностью площадей ствола и трубы; время циркуляции — объёмом и расходом.": (
        "Гидростатикалық қысым MD бойынша емес, шынайы тік тереңдік TVD бойынша есептеледі. Сақиналы көлем ұңғыма мен құбыр қималарының айырмасымен, ал циркуляция уақыты көлем мен шығын арқылы анықталады.",
        "Hydrostatic pressure is calculated from true vertical depth TVD, not MD. Annular volume is based on the difference between hole and pipe areas; circulation time depends on volume and flow rate.",
    ),
    "ECD учитывает плотность раствора и потери давления в затрубном пространстве. Смешение двух объёмов рассчитано по сохранению массы без учёта химической усадки и реакции компонентов.": (
        "ECD ерітінді тығыздығын және сақиналы кеңістіктегі қысым шығынын ескереді. Екі көлемді араластыру химиялық шөгу мен компонент реакцияларын есепке алмай, масса сақталуы бойынша есептеледі.",
        "ECD includes fluid density and annular pressure losses. Mixing two volumes uses mass conservation without accounting for chemical shrinkage or component reactions.",
    ),
    "Абсолютная отметка точки = абсолютная отметка datum − TVD. Используйте ту же точку отсчёта, что указана в шапке каротажа: KB/RKB, DF или другой datum.": (
        "Нүктенің абсолюттік белгісі = datum абсолюттік белгісі − TVD. Каротаж тақырыбында көрсетілген сол есептеу нүктесін пайдаланыңыз: KB/RKB, DF немесе басқа datum.",
        "Point elevation = datum elevation − TVD. Use the same reference shown in the log header: KB/RKB, DF or another datum.",
    ),
    "Цепочка: GL = datum + смещение GL; Wellhead = GL + высота устья; DF = GL + высота пола; RT = DF + превышение RT; KB/RKB = RT + превышение втулки.\nПример: datum 100 м, GL +2 м, DF +6 м, RT +0,5 м, RKB +0,3 м → GL 102 м, DF 108 м, RT 108,5 м, RKB 108,8 м.": (
        "Тізбек: GL = datum + GL ығысуы; Wellhead = GL + саға биіктігі; DF = GL + еден биіктігі; RT = DF + RT артуы; KB/RKB = RT + төлке биіктігі.\nМысал: datum 100 м, GL +2 м, DF +6 м, RT +0,5 м, RKB +0,3 м → GL 102 м, DF 108 м, RT 108,5 м, RKB 108,8 м.",
        "Chain: GL = datum + GL offset; Wellhead = GL + wellhead height; DF = GL + floor height; RT = DF + RT offset; KB/RKB = RT + bushing height.\nExample: datum 100 m, GL +2 m, DF +6 m, RT +0.5 m, RKB +0.3 m → GL 102 m, DF 108 m, RT 108.5 m, RKB 108.8 m.",
    ),
}


class FileWorkspaceWidget(_V2FileWorkspaceWidget):
    """Final localization pass over the tested interactive Files workspace."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent, language=language)
        self._fix_help_card_placement()
        self._fix_document_panel_titles()
        self._translate_remaining_widgets()
        self._translate_tables_and_tabs()
        self._translate_archive_capabilities()
        self._set_field_help()

    def _pick(self, values: tuple[str, str]) -> str:
        return values[0] if self.language == "kk" else values[1]

    def _fix_help_card_placement(self) -> None:
        keys = (
            ("help_documents_title", "help_documents_body"),
            ("help_pdf_title", "help_pdf_body"),
            ("help_logo_title", "help_logo_body"),
            ("help_archives_title", "help_archives_body"),
            ("help_engineering_title", "help_engineering_body"),
        )
        for index, (title_key, body_key) in enumerate(keys):
            page = self.sections.widget(index)
            if page is None:
                continue
            card = page.findChild(QFrame, "expertHelpCard")
            if card is None:
                continue
            labels = card.findChildren(QLabel)
            if labels:
                labels[0].setText(self._t(title_key))
            if len(labels) > 1:
                labels[1].setText(self._t(body_key))

        page = self.sections.widget(0)
        if page is not None:
            for child in page.children():
                if isinstance(child, QLabel) and child.objectName() == "hint":
                    child.setText(
                        self._pick(
                            _TRANSLATIONS[
                                "Выберите страницу и выделите область мышью. Затем примените контекстную команду и сохраните копию документа."
                            ]
                        )
                    )

    def _fix_document_panel_titles(self) -> None:
        page_list: Any = getattr(self, "_page_list", None)
        selection_info: Any = getattr(self, "_selection_info", None)
        document_info: Any = getattr(self, "_document_info", None)
        document_status: Any = getattr(self, "document_status", None)

        document_panel = page_list.parentWidget() if page_list is not None else None
        document_layout = document_panel.layout() if document_panel is not None else None
        if document_layout is not None:
            first = document_layout.itemAt(0)
            pages = document_layout.itemAt(2)
            first_widget = first.widget() if first is not None else None
            pages_widget = pages.widget() if pages is not None else None
            if isinstance(first_widget, QLabel):
                first_widget.setText(self._t("document"))
            if isinstance(pages_widget, QLabel):
                pages_widget.setText(self._t("pages"))
            if isinstance(document_info, QLabel) and not self.document_service.is_open:
                document_info.setText(self._t("file_not_open"))

        workflow_panel = selection_info.parentWidget() if selection_info is not None else None
        workflow_layout = workflow_panel.layout() if workflow_panel is not None else None
        if workflow_layout is None:
            return
        first = workflow_layout.itemAt(0)
        instructions = workflow_layout.itemAt(1)
        first_widget = first.widget() if first is not None else None
        instruction_widget = instructions.widget() if instructions is not None else None
        if isinstance(first_widget, QLabel):
            first_widget.setText(self._t("quick_workflow"))
        if isinstance(instruction_widget, QLabel):
            instruction_widget.setText(self._t("workflow_steps"))

        selection_index = workflow_layout.indexOf(selection_info)
        if selection_index > 0:
            item = workflow_layout.itemAt(selection_index - 1)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel):
                label.setText(self._t("selected_area"))
        if isinstance(selection_info, QLabel):
            selection_info.setText(self._t("no_area"))

        status_index = workflow_layout.indexOf(document_status)
        if status_index > 0:
            for index in range(status_index - 1, -1, -1):
                item = workflow_layout.itemAt(index)
                label = item.widget() if item is not None else None
                if isinstance(label, QLabel) and label is not selection_info:
                    label.setText(self._t("state"))
                    break

    def _translation(self, value: str) -> str | None:
        if self.language == "ru":
            return None
        pair = _TRANSLATIONS.get(value) or _LONG_TRANSLATIONS.get(value)
        return self._pick(pair) if pair is not None else None

    def _translate_remaining_widgets(self) -> None:
        if self.language == "ru":
            return
        for label in self.findChildren(QLabel):
            translated = self._translation(label.text())
            if translated is not None:
                label.setText(translated)
        for button_type in (QPushButton, QToolButton, QCheckBox):
            for button in self.findChildren(button_type):
                translated = self._translation(button.text())
                if translated is not None:
                    button.setText(translated)
        for group in self.findChildren(QGroupBox):
            translated = self._translation(group.title())
            if translated is not None:
                group.setTitle(translated)
        for widget in self.findChildren(QWidget):
            translated = self._translation(widget.toolTip())
            if translated is not None:
                widget.setToolTip(translated)
        for line_edit in self.findChildren(QLineEdit):
            translated = self._translation(line_edit.placeholderText())
            if translated is not None:
                line_edit.setPlaceholderText(translated)
        for text_edit in self.findChildren(QTextEdit):
            translated = self._translation(text_edit.placeholderText())
            if translated is not None:
                text_edit.setPlaceholderText(translated)

    def _translate_tables_and_tabs(self) -> None:
        if self.language == "ru":
            return
        datum_table: Any = getattr(self, "datum_table", None)
        if isinstance(datum_table, QTableWidget):
            datum_table.setHorizontalHeaderLabels(
                [self._pick(_TRANSLATIONS["Уровень"]), self._pick(_TRANSLATIONS["Абсолютная отметка, м"])]
            )
        archive_entries: Any = getattr(self, "archive_entries", None)
        if isinstance(archive_entries, QTreeWidget):
            archive_entries.setHeaderLabels(
                [
                    self._pick(_TRANSLATIONS["Элемент"]),
                    self._pick(_TRANSLATIONS["Размер"]),
                    self._pick(_TRANSLATIONS["Тип"]),
                ]
            )
        petroleum_tabs = self.findChild(QTabWidget, "petroleumCalculatorTabs")
        if petroleum_tabs is not None:
            for index, source in enumerate(("Трубы", "Бурение", "Буровой раствор", "Геология")):
                petroleum_tabs.setTabText(index, self._pick(_TRANSLATIONS[source]))

    def _translate_archive_capabilities(self) -> None:
        if self.language == "ru":
            return
        label: Any = getattr(self, "archive_capabilities", None)
        service: Any = getattr(self, "archive_service", None)
        if not isinstance(label, QLabel) or service is None:
            return
        create_word = "жасау" if self.language == "kk" else "create"
        extract_word = "ашу" if self.language == "kk" else "extract"
        unavailable = "қолжетімсіз" if self.language == "kk" else "unavailable"
        items: list[str] = []
        for capability in service.capabilities():
            states: list[str] = []
            if capability.can_create:
                states.append(create_word)
            if capability.can_extract:
                states.append(extract_word)
            if not states:
                states.append(unavailable)
            items.append(f"<b>{capability.archive_format.value.upper()}</b>: {', '.join(states)}")
        label.setText(" &nbsp; · &nbsp; ".join(items))

    def _set_field_help(self) -> None:
        kk = self.language == "kk"
        en = self.language == "en"
        if not (kk or en):
            return
        tips = {
            "expression_input": (
                "Қауіпсіз математикалық өрнекті енгізіңіз. Мысал: sqrt(144) + 2 1/2. Нүкте немесе үтір қолдануға болады.",
                "Enter a safe mathematical expression, for example sqrt(144) + 2 1/2. Decimal dots and commas are supported.",
            ),
            "converter_value": (
                "Санды, 7 1/2 аралас бөлшегін немесе 7½ таңбасын енгізіңіз.",
                "Enter a number, a mixed fraction such as 7 1/2, or a fraction symbol such as 7½.",
            ),
            "pipe_od_in": (
                "Құбырдың нақты сыртқы диаметрін дюйммен енгізіңіз; бұл шартты DN емес.",
                "Enter the actual pipe outer diameter in inches; this is not nominal DN.",
            ),
            "drill_tvd": (
                "TVD — қабылданған есептеу нүктесінен шынайы тік тереңдік.",
                "TVD is true vertical depth from the selected reference point.",
            ),
            "mud_annular_loss": (
                "Таңдалған тереңдікке дейінгі сақиналы кеңістіктегі жалпы қысым шығыны.",
                "Total annular pressure loss to the selected depth.",
            ),
            "geo_reference": (
                "Тереңдіктің қабылданған есептеу нүктесінің абсолюттік белгісі.",
                "Absolute elevation of the selected depth reference.",
            ),
        }
        for name, pair in tips.items():
            control: Any = getattr(self, name, None)
            if isinstance(control, (QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox)):
                control.setToolTip(pair[0] if kk else pair[1])
