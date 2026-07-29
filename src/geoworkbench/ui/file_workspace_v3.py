from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
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


_EXACT: dict[str, tuple[str, str]] = {
    "Пакетные операции с PDF": ("PDF топтық операциялары", "Batch PDF operations"),
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
    "Инженерный калькулятор": ("Инженерлік калькулятор", "Engineering calculator"),
    "Конвертер единиц": ("Өлшем бірліктерін түрлендіру", "Unit converter"),
    "Категория": ("Санат", "Category"),
    "Значение": ("Мән", "Value"),
    "Из": ("Бастапқы", "From"),
    "В": ("Нәтиже бірлігі", "To"),
    "Результат": ("Нәтиже", "Result"),
    "Результат:": ("Нәтиже:", "Result:"),
    "Преобразовать": ("Түрлендіру", "Convert"),
    "⇄ Поменять местами": ("⇄ Орындарын ауыстыру", "⇄ Swap units"),
    "Высотные отметки буровой и привязка глубины": ("Бұрғылау қондырғысының биіктік белгілері және тереңдік байланысы", "Rig elevations and depth reference"),
    "Рассчитать отметки": ("Белгілерді есептеу", "Calculate elevations"),
    "Нефтегазовые, буровые и геологические расчёты": ("Мұнай-газ, бұрғылау және геологиялық есептеулер", "Oilfield, drilling and geological calculations"),
    "Трубы": ("Құбырлар", "Pipes"),
    "Бурение": ("Бұрғылау", "Drilling"),
    "Буровой раствор": ("Бұрғылау ерітіндісі", "Drilling fluid"),
    "Геология": ("Геология", "Geology"),
    "Наружный диаметр, дюймы:": ("Сыртқы диаметр, дюйм:", "Outer diameter, inches:"),
    "Толщина стенки:": ("Қабырға қалыңдығы:", "Wall thickness:"),
    "Длина:": ("Ұзындығы:", "Length:"),
    "Плотность материала:": ("Материал тығыздығы:", "Material density:"),
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
}

_LONG: dict[str, tuple[str, str]] = {
    "Результаты обновляются сразу. После смены категории или единиц старое значение очищается и рассчитывается заново.": (
        "Нәтижелер бірден жаңартылады. Санат немесе өлшем бірлігі өзгергенде ескі мән тазартылып, қайта есептеледі.",
        "Results update immediately. When the category or units change, the old value is cleared and recalculated.",
    ),
    "Объединение сохраняет порядок выбранных файлов. Разделение создаёт отдельный PDF для каждой страницы. Экспорт DOCX переносит доступный текст без OCR.": (
        "Біріктіру таңдалған файлдардың ретін сақтайды. Бөлу әр бетке жеке PDF жасайды. DOCX экспорты OCR қолданбай қолжетімді мәтінді тасымалдайды.",
        "Merge preserves the selected order. Split creates one PDF per page. DOCX export transfers available text without OCR.",
    ),
    "Здесь появится журнал: исходный файл, созданный результат и количество страниц.": (
        "Мұнда бастапқы файл, жасалған нәтиже және бет саны көрсетіледі.",
        "The source file, result and page count will appear here.",
    ),
    "Расчёты выполняются в SI. Проверяйте исходные данные по рабочей программе, паспорту буровой и утверждённой гидравлической модели; результаты являются инженерной проверкой, а не заменой проектного расчёта.": (
        "Есептеулер SI жүйесінде орындалады. Деректерді жұмыс бағдарламасы, қондырғы паспорты және бекітілген гидравликалық модель бойынша тексеріңіз; нәтиже жобалық есепті алмастырмайды.",
        "Calculations use SI units. Verify inputs against the drilling program, rig documentation and approved hydraulic model; results do not replace a design calculation.",
    ),
    "Введите наружный диаметр в дюймах: 7 1/2, 7½, 7.5 или 7,5. Прямой перевод 7 1/2″ равен 190,5 мм. Для внутреннего диаметра и массы нужна толщина стенки.": (
        "Сыртқы диаметрді дюйммен енгізіңіз: 7 1/2, 7½, 7.5 немесе 7,5. 7 1/2″ = 190,5 мм. Ішкі диаметр мен масса үшін қабырға қалыңдығы қажет.",
        "Enter outer diameter in inches: 7 1/2, 7½ or 7.5. 7 1/2″ = 190.5 mm. Wall thickness is required for inner diameter and mass.",
    ),
    "Гидростатическое давление считается по истинной вертикальной глубине TVD, а не по MD. Кольцевой объём определяется разностью площадей ствола и трубы; время циркуляции — объёмом и расходом.": (
        "Гидростатикалық қысым MD емес, TVD бойынша есептеледі. Сақиналы көлем ұңғыма мен құбыр қималарының айырмасымен, циркуляция уақыты көлем мен шығынмен анықталады.",
        "Hydrostatic pressure uses TVD, not MD. Annular volume uses the difference between hole and pipe areas; circulation time uses volume and flow rate.",
    ),
    "ECD учитывает плотность раствора и потери давления в затрубном пространстве. Смешение двух объёмов рассчитано по сохранению массы без учёта химической усадки и реакции компонентов.": (
        "ECD ерітінді тығыздығын және сақиналы кеңістіктегі қысым шығынын ескереді. Араластыру химиялық шөгу мен реакцияларды есепке алмай, масса сақталуы бойынша есептеледі.",
        "ECD includes fluid density and annular pressure losses. Mixing uses mass conservation without chemical shrinkage or reactions.",
    ),
    "Абсолютная отметка точки = абсолютная отметка datum − TVD. Используйте ту же точку отсчёта, что указана в шапке каротажа: KB/RKB, DF или другой datum.": (
        "Нүктенің абсолюттік белгісі = datum белгісі − TVD. Каротаж тақырыбындағы KB/RKB, DF немесе басқа datum есептеу нүктесін пайдаланыңыз.",
        "Point elevation = datum elevation − TVD. Use the same KB/RKB, DF or other datum reference shown in the log header.",
    ),
}


class FileWorkspaceWidget(_V2FileWorkspaceWidget):
    """Final localization pass over the tested interactive Files workspace."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent, language=language)
        self._fix_help_cards()
        self._fix_document_panels()
        self._translate_widgets()
        self._translate_tables_tabs_and_archive()
        self._set_field_help()

    def _pick(self, pair: tuple[str, str]) -> str:
        return pair[0] if self.language == "kk" else pair[1]

    def _translate(self, value: str) -> str | None:
        if self.language == "ru":
            return None
        pair = _EXACT.get(value) or _LONG.get(value)
        return self._pick(pair) if pair is not None else None

    def _fix_help_cards(self) -> None:
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
        if page is None:
            return
        hints = {
            "ru": "Ластик: включите режим и ведите по странице с зажатой левой кнопкой. Текст: выделите прямоугольную область. Сохраните отдельную копию.",
            "kk": "Өшіргіш: режимді қосып, сол жақ батырманы басып ұстап бетпен жүргізіңіз. Мәтін: тікбұрышты аймақты белгілеңіз. Бөлек көшірмені сақтаңыз.",
            "en": "Eraser: enable the mode and drag while holding the left mouse button. Text: select a rectangular area. Save a separate copy.",
        }
        for child in page.children():
            if isinstance(child, QLabel) and child.objectName() == "hint":
                child.setText(hints[self.language])

    def _fix_document_panels(self) -> None:
        page_list: Any = getattr(self, "_page_list", None)
        selection_info: Any = getattr(self, "_selection_info", None)
        document_info: Any = getattr(self, "_document_info", None)
        document_status: Any = getattr(self, "document_status", None)

        document_panel = page_list.parentWidget() if page_list is not None else None
        document_layout = document_panel.layout() if document_panel is not None else None
        if document_layout is not None:
            first = document_layout.itemAt(0)
            third = document_layout.itemAt(2)
            first_widget = first.widget() if first is not None else None
            third_widget = third.widget() if third is not None else None
            if isinstance(first_widget, QLabel):
                first_widget.setText(self._t("document"))
            if isinstance(third_widget, QLabel):
                third_widget.setText(self._t("pages"))
            if isinstance(document_info, QLabel) and not self.document_service.is_open:
                document_info.setText(self._t("file_not_open"))

        workflow_panel = selection_info.parentWidget() if selection_info is not None else None
        workflow_layout = workflow_panel.layout() if workflow_panel is not None else None
        if workflow_layout is None:
            return
        first = workflow_layout.itemAt(0)
        second = workflow_layout.itemAt(1)
        first_widget = first.widget() if first is not None else None
        second_widget = second.widget() if second is not None else None
        if isinstance(first_widget, QLabel):
            first_widget.setText(self._t("quick_workflow"))
        if isinstance(second_widget, QLabel):
            second_widget.setText(self._t("workflow_steps"))
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

    def _translate_widgets(self) -> None:
        if self.language == "ru":
            return
        for label_widget in self.findChildren(QLabel):
            translated = self._translate(label_widget.text())
            if translated is not None:
                label_widget.setText(translated)
        for push_button in self.findChildren(QPushButton):
            translated = self._translate(push_button.text())
            if translated is not None:
                push_button.setText(translated)
        for tool_button in self.findChildren(QToolButton):
            translated = self._translate(tool_button.text())
            if translated is not None:
                tool_button.setText(translated)
        for check_box in self.findChildren(QCheckBox):
            translated = self._translate(check_box.text())
            if translated is not None:
                check_box.setText(translated)
        for group_box in self.findChildren(QGroupBox):
            translated = self._translate(group_box.title())
            if translated is not None:
                group_box.setTitle(translated)
        for generic_widget in self.findChildren(QWidget):
            translated = self._translate(generic_widget.toolTip())
            if translated is not None:
                generic_widget.setToolTip(translated)
        for line_edit in self.findChildren(QLineEdit):
            translated = self._translate(line_edit.placeholderText())
            if translated is not None:
                line_edit.setPlaceholderText(translated)
        for text_edit in self.findChildren(QTextEdit):
            translated = self._translate(text_edit.placeholderText())
            if translated is not None:
                text_edit.setPlaceholderText(translated)

    def _translate_tables_tabs_and_archive(self) -> None:
        if self.language == "ru":
            return
        datum_table: Any = getattr(self, "datum_table", None)
        if isinstance(datum_table, QTableWidget):
            headers = ("Деңгей", "Абсолюттік белгі, м") if self.language == "kk" else ("Level", "Absolute elevation, m")
            datum_table.setHorizontalHeaderLabels(list(headers))
        archive_entries: Any = getattr(self, "archive_entries", None)
        if isinstance(archive_entries, QTreeWidget):
            headers = ("Элемент", "Өлшем", "Түрі") if self.language == "kk" else ("Item", "Size", "Type")
            archive_entries.setHeaderLabels(list(headers))
        petroleum_tabs = self.findChild(QTabWidget, "petroleumCalculatorTabs")
        if petroleum_tabs is not None:
            for index, source in enumerate(("Трубы", "Бурение", "Буровой раствор", "Геология")):
                petroleum_tabs.setTabText(index, self._pick(_EXACT[source]))

        label: Any = getattr(self, "archive_capabilities", None)
        service: Any = getattr(self, "archive_service", None)
        if isinstance(label, QLabel) and service is not None:
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
        if self.language == "ru":
            return
        kk = self.language == "kk"
        tips = {
            "expression_input": (
                "Қауіпсіз математикалық өрнек енгізіңіз: sqrt(144) + 2 1/2. Нүкте немесе үтір қолдануға болады.",
                "Enter a safe expression: sqrt(144) + 2 1/2. Decimal dots and commas are supported.",
            ),
            "converter_value": (
                "Санды, 7 1/2 аралас бөлшегін немесе 7½ таңбасын енгізіңіз.",
                "Enter a number, a mixed fraction such as 7 1/2, or 7½.",
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
