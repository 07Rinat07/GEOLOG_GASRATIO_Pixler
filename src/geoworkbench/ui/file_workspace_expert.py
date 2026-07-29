from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.files.pdf_tools import PdfTools, PdfToolsError
from geoworkbench.files.petroleum_calculations import (
    annular_volume,
    circulation_time_minutes,
    equivalent_circulating_density,
    formation_elevations,
    hydrostatic_pressure,
    mixed_fluid_density,
    pipe_geometry,
)
from geoworkbench.ui.file_workspace_production import (
    FileWorkspaceWidget as _ProductionFileWorkspaceWidget,
)


class FileWorkspaceWidget(_ProductionFileWorkspaceWidget):
    """Guided production workspace for documents and oilfield calculations."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent, language=language)
        self._toolbar_attempts = 0
        self._install_help_cards()
        self._configure_existing_controls()
        self._configure_datum_explanation()
        self._install_pdf_eraser_and_replacement()
        self._install_docx_export_modes()
        self._install_petroleum_calculators()
        self._install_header_shortcuts()
        QTimer.singleShot(0, self._install_main_toolbar_entry)

    def show_section(self, index: int) -> None:
        self.sections.setCurrentIndex(max(0, min(self.sections.count() - 1, index)))

    def _install_help_cards(self) -> None:
        help_texts = (
            (
                "Как работать с документом",
                "Откройте PDF или изображение. Для PDF выберите страницу, протяните мышью "
                "прямоугольник и примените инструмент. «Ластик / заменить» действительно удаляет "
                "содержимое области; до сохранения действие можно отменить. Сохраняйте результат "
                "через «Сохранить как», чтобы оставить исходник без изменений.",
            ),
            (
                "Как работают PDF-инструменты",
                "Объединение собирает несколько PDF в заданном порядке. Разделение создаёт отдельный "
                "PDF для каждой страницы. Экспорт «вид страниц» переносит страницы в Word как изображения "
                "и сохраняет таблицы, схемы и расположение; экспорт «только текст» создаёт редактируемые "
                "абзацы, но не сохраняет исходную вёрстку.",
            ),
            (
                "Как создать логотип",
                "Введите текст, задайте размер изображения и шрифта, выберите цвета или готовый стиль. "
                "Предпросмотр обновляется автоматически. Прозрачный фон лучше сохранять в PNG.",
            ),
            (
                "Как работать с архивами",
                "Для создания добавьте файлы или папку, выберите формат и нажмите «Создать архив». "
                "Для просмотра или распаковки выберите существующий архив. ZIP и TAR работают встроенно; "
                "7Z и RAR зависят от установленных системных компонентов.",
            ),
            (
                "Как пользоваться расчётами",
                "У каждого поля указана единица измерения. Универсальный калькулятор принимает дроби "
                "вида 7 1/2 и 7½. Конвертер показывает полное равенство. Ниже расположены отдельные "
                "калькуляторы труб, бурения, бурового раствора и геологических отметок.",
            ),
        )
        for index, (title, text) in enumerate(help_texts):
            page = self.sections.widget(index)
            if page is None:
                continue
            layout = page.layout()
            if not isinstance(layout, (QVBoxLayout, QHBoxLayout)):
                continue
            card = QFrame(page)
            card.setObjectName("expertHelpCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 9, 12, 9)
            card_layout.setSpacing(3)
            heading = QLabel(title, card)
            heading.setStyleSheet("font-weight: 700;")
            body = QLabel(text, card)
            body.setWordWrap(True)
            body.setObjectName("muted")
            card_layout.addWidget(heading)
            card_layout.addWidget(body)
            layout.insertWidget(0, card)

        self.setStyleSheet(
            self.styleSheet()
            + "\nQFrame#expertHelpCard { border: 1px solid palette(mid); "
            "border-radius: 9px; background: palette(base); }"
        )

    def _configure_existing_controls(self) -> None:
        self.expression_input.setToolTip(
            "Введите безопасное математическое выражение. Примеры: 7 1/2 * 25.4; "
            "sqrt(144); sin(pi/2). Десятичный разделитель может быть точкой или запятой."
        )
        self.converter_category.setToolTip(
            "Сначала выберите физическую величину: длина, объём, давление и т. д."
        )
        self.converter_value.setToolTip(
            "Введите число, дробь 7 1/2, запись 7½ или выражение."
        )
        self.converter_source.setToolTip("Единица исходного значения.")
        self.converter_target.setToolTip("Единица результата.")
        self.converter_result.setToolTip(
            "Автоматически рассчитанное значение в выбранной единице."
        )
        self.zoom_spin.setToolTip(
            "Масштаб просмотра страницы от 10 до 800 процентов."
        )

        button_tips = {
            "Открыть": "Открыть PDF, JPEG, PNG, TIFF или BMP.",
            "Сохранить": "Сохранить изменения в текущий файл.",
            "Сохранить как": "Сохранить отдельную копию и не изменять исходный файл.",
            "Добавить текст": "Сначала выделите прямоугольник на PDF, затем введите текст.",
            "Выделить": "Создать PDF-аннотацию выделения внутри выбранной области.",
            "Примечание": "Добавить текстовую заметку в верхний левый угол выделенной области.",
            "Безопасно скрыть": "Навсегда удалить содержимое выбранной области после сохранения PDF.",
            "Удалить аннотации": "Удалить аннотации, пересекающие выбранную область.",
            "Размер": "Изменить ширину и высоту растрового изображения.",
            "Обрезать": "Оставить только выделенную часть изображения.",
            "Коррекция": "Настроить яркость, контраст, насыщенность и резкость изображения.",
            "Создать архив...": "Создать архив из списка добавленных файлов и папок.",
            "Показать состав архива...": "Прочитать список файлов без распаковки архива.",
            "Распаковать архив...": "Безопасно извлечь содержимое архива в выбранную папку.",
        }
        buttons: list[QPushButton | QToolButton] = []
        buttons.extend(self.findChildren(QPushButton))
        buttons.extend(self.findChildren(QToolButton))
        for button in buttons:
            tip = button_tips.get(button.text().replace("&", ""))
            if tip:
                button.setToolTip(tip)

    def _configure_datum_explanation(self) -> None:
        if not self.datum_inputs:
            return
        group = self.datum_inputs[0].parentWidget()
        layout = group.layout() if group is not None else None
        if not isinstance(layout, QGridLayout):
            return
        if isinstance(group, QGroupBox):
            group.setTitle("Высотные отметки буровой и привязка глубины")

        labels = (
            "Опорная абсолютная отметка, м",
            "Смещение уровня земли GL от опорной отметки, м",
            "Высота устья Wellhead над GL, м",
            "Высота пола буровой DF над GL, м",
            "Высота принятой отметки роторного стола RT над DF, м",
            "Высота KB/RKB над RT, м",
        )
        tips = (
            "Известная абсолютная высота исходного datum относительно принятой системы высот.",
            "GL (Ground Level) — уровень земли. Положительное значение означает, что GL выше datum.",
            "Wellhead — устье скважины. Введите вертикальную высоту устья над уровнем земли.",
            "DF (Drill Floor) — рабочая площадка буровой, а не роторный стол.",
            "RT (Rotary Table) — отдельное оборудование в центре drill floor. Укажите 0, если в документации отметки DF и RT совпадают.",
            "KB/RKB — верх ведущей втулки над RT; эта точка часто служит нулём измеряемой глубины.",
        )
        for row, (text, tip, control) in enumerate(
            zip(labels, tips, self.datum_inputs, strict=True)
        ):
            item = layout.itemAtPosition(row, 0)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel):
                label.setText(text)
                label.setToolTip(tip)
                label.setWordWrap(True)
            control.setSuffix(" м")
            control.setToolTip(tip)

        explanation = QLabel(
            "Цепочка: GL = datum + смещение GL; Wellhead = GL + высота устья; "
            "DF = GL + высота пола; RT = DF + превышение RT; KB/RKB = RT + превышение втулки.\n"
            "Пример: datum 100 м, GL +2 м, DF +6 м, RT +0,5 м, RKB +0,3 м → "
            "GL 102 м, DF 108 м, RT 108,5 м, RKB 108,8 м.",
            group,
        )
        explanation.setObjectName("hint")
        explanation.setWordWrap(True)
        layout.addWidget(explanation, 7, 0, 1, 3)

    def _install_pdf_eraser_and_replacement(self) -> None:
        context_bar = self.findChild(QFrame, "contextBar")
        layout = context_bar.layout() if context_bar is not None else None
        if not isinstance(layout, QHBoxLayout):
            return
        button = QToolButton(context_bar)
        button.setText("Ластик / заменить")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setToolTip(
            "Выделите область. Пустой новый текст удалит содержимое; введённый текст будет "
            "вставлен после настоящего PDF-redaction. До сохранения используйте «Отменить»."
        )
        button.clicked.connect(self._erase_and_replace_pdf)
        layout.insertWidget(max(0, layout.count() - 1), button)
        self._pdf_tools.append(button)

    def _erase_and_replace_pdf(self) -> None:
        try:
            rect = self._selected_document_rect()
        except Exception as error:
            self._show_error("Ластик PDF", error)
            return
        replacement, accepted = QInputDialog.getMultiLineText(
            self,
            "Ластик и замена текста",
            "Введите новый текст. Оставьте поле пустым, чтобы только удалить содержимое области:",
        )
        if not accepted:
            return
        answer = QMessageBox.question(
            self,
            "Подтверждение удаления",
            "Содержимое выбранной области будет удалено из структуры PDF. "
            "До сохранения операцию можно отменить. Продолжить?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.document_service.redact_pdf_area(rect)
            if replacement.strip():
                try:
                    self.document_service.add_pdf_text(rect, replacement)
                except Exception:
                    self.document_service.undo()
                    raise
            self._refresh_document()
            self.document_status.setText(
                "Область удалена"
                + (" и заменена новым текстом" if replacement.strip() else "")
                + ". Сохраните отдельную копию PDF."
            )
        except Exception as error:
            self._show_error("Ластик PDF", error)

    def _install_docx_export_modes(self) -> None:
        page = self.sections.widget(1)
        layout = page.layout() if page is not None else None
        if not isinstance(layout, QVBoxLayout):
            return
        if page is None:
            return
        for button in page.findChildren(QPushButton):
            if button.text().startswith("Экспорт PDF в DOCX"):
                button.hide()

        card = QFrame(page)
        card.setObjectName("floatingCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        label = QLabel("Экспорт в Word:", card)
        label.setStyleSheet("font-weight: 700;")
        card_layout.addWidget(label)
        visual = QPushButton("Сохранить вид страниц...", card)
        visual.setObjectName("primaryButton")
        visual.setToolTip(
            "Каждая страница PDF будет помещена в DOCX как изображение. "
            "Сохраняются таблицы, схемы, подписи и расположение, но текст внутри страницы не редактируется."
        )
        visual.clicked.connect(self._export_pdf_pages_docx)
        card_layout.addWidget(visual)
        text = QPushButton("Извлечь только текст...", card)
        text.setToolTip(
            "Создать редактируемые абзацы из текстового слоя PDF. "
            "Таблицы, колонки, изображения и исходная вёрстка не сохраняются."
        )
        text.clicked.connect(self._export_pdf_docx)
        card_layout.addWidget(text)
        card_layout.addStretch(1)
        layout.insertWidget(2, card)

    def _export_pdf_pages_docx(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "PDF для переноса страниц", "", "PDF (*.pdf)"
        )
        if not source:
            return
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить Word с видом страниц",
            "document_pages.docx",
            "DOCX (*.docx)",
        )
        if not target:
            return
        try:
            result = PdfTools.export_pages_docx(Path(source), Path(target))
            self.pdf_tools_log.append(
                f"DOCX с сохранённым видом страниц: {result}\n"
                "Страницы вставлены как изображения; внешний вид сохранён, текст не редактируется."
            )
        except PdfToolsError as error:
            self._show_error("Экспорт страниц PDF в Word", error)

    def _install_petroleum_calculators(self) -> None:
        page = self.sections.widget(4)
        layout = page.layout() if page is not None else None
        if not isinstance(layout, QVBoxLayout):
            return
        if page is None:
            return
        group = QGroupBox("Нефтегазовые, буровые и геологические расчёты", page)
        group_layout = QVBoxLayout(group)
        intro = QLabel(
            "Расчёты выполняются в SI. Проверяйте исходные данные по рабочей программе, "
            "паспорту буровой и утверждённой гидравлической модели; результаты являются инженерной проверкой, "
            "а не заменой проектного расчёта.",
            group,
        )
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        group_layout.addWidget(intro)
        tabs = QTabWidget(group)
        tabs.setObjectName("petroleumCalculatorTabs")
        tabs.addTab(self._build_pipe_calculator(tabs), "Трубы")
        tabs.addTab(self._build_drilling_calculator(tabs), "Бурение")
        tabs.addTab(self._build_mud_calculator(tabs), "Буровой раствор")
        tabs.addTab(self._build_geology_calculator(tabs), "Геология")
        group_layout.addWidget(tabs)
        layout.addWidget(group)

    @staticmethod
    def _spin(
        value: float,
        minimum: float,
        maximum: float,
        suffix: str,
        tooltip: str,
        decimals: int = 3,
    ) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(minimum, maximum)
        control.setDecimals(decimals)
        control.setValue(value)
        control.setSuffix(suffix)
        control.setToolTip(tooltip)
        return control

    def _result_label(self, parent: QWidget) -> QLabel:
        label = QLabel(parent=parent)
        label.setObjectName("statusCard")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _build_pipe_calculator(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        layout = QFormLayout(page)
        help_label = QLabel(
            "Введите наружный диаметр в дюймах: 7 1/2, 7½, 7.5 или 7,5. "
            "Прямой перевод 7 1/2″ равен 190,5 мм. Для внутреннего диаметра и массы нужна толщина стенки.",
            page,
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("hint")
        layout.addRow(help_label)
        self.pipe_od_in = QLineEdit("7 1/2", page)
        self.pipe_od_in.setPlaceholderText("Например: 7 1/2")
        self.pipe_od_in.setToolTip(
            "Фактический наружный диаметр трубы в дюймах, а не условный DN."
        )
        self.pipe_wall_mm = self._spin(
            9.5,
            0.0,
            500.0,
            " мм",
            "Радиальная толщина одной стенки трубы.",
        )
        self.pipe_length_m = self._spin(
            12.0,
            0.0,
            1_000_000.0,
            " м",
            "Длина одной трубы или всей колонны.",
        )
        self.pipe_density = self._spin(
            7_850.0,
            1.0,
            30_000.0,
            " кг/м³",
            "Плотность материала; для стали обычно около 7850 кг/м³.",
            1,
        )
        self.pipe_result = self._result_label(page)
        layout.addRow("Наружный диаметр, дюймы:", self.pipe_od_in)
        layout.addRow("Толщина стенки:", self.pipe_wall_mm)
        layout.addRow("Длина:", self.pipe_length_m)
        layout.addRow("Плотность материала:", self.pipe_density)
        layout.addRow("Результат:", self.pipe_result)
        self.pipe_od_in.textChanged.connect(self._update_pipe_calculator)
        for control in (
            self.pipe_wall_mm,
            self.pipe_length_m,
            self.pipe_density,
        ):
            control.valueChanged.connect(self._update_pipe_calculator)
        self._update_pipe_calculator()
        return page

    def _update_pipe_calculator(self, *_args: object) -> None:
        try:
            result = pipe_geometry(
                self.pipe_od_in.text(),
                self.pipe_wall_mm.value(),
                self.pipe_length_m.value(),
                self.pipe_density.value(),
            )
            self.pipe_result.setText(
                f"Наружный диаметр: <b>{result.outer_diameter_mm:.3f} мм</b><br>"
                f"Внутренний диаметр: {result.inner_diameter_mm:.3f} мм<br>"
                f"Площадь прохода: {result.flow_area_mm2:.1f} мм²<br>"
                f"Вместимость: {result.capacity_l_per_m:.3f} л/м<br>"
                f"Масса: {result.mass_kg_per_m:.3f} кг/м; всего {result.total_mass_kg:.3f} кг"
            )
        except Exception as error:
            self.pipe_result.setText(f"Ошибка исходных данных: {error}")

    def _build_drilling_calculator(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        layout = QGridLayout(page)
        help_label = QLabel(
            "Гидростатическое давление считается по истинной вертикальной глубине TVD, а не по MD. "
            "Кольцевой объём определяется разностью площадей ствола и трубы; время циркуляции — объёмом и расходом.",
            page,
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("hint")
        layout.addWidget(help_label, 0, 0, 1, 4)
        self.drill_mud_density = self._spin(
            1_200.0,
            1.0,
            5_000.0,
            " кг/м³",
            "Текущая плотность бурового раствора.",
            1,
        )
        self.drill_tvd = self._spin(
            2_500.0,
            0.0,
            20_000.0,
            " м",
            "TVD — истинная вертикальная глубина от принятой точки отсчёта.",
            1,
        )
        self.drill_hole_d = self._spin(
            215.9,
            0.1,
            5_000.0,
            " мм",
            "Фактический диаметр ствола или внутренний диаметр обсадной колонны.",
            2,
        )
        self.drill_pipe_d = self._spin(
            127.0,
            0.0,
            5_000.0,
            " мм",
            "Наружный диаметр трубы внутри рассматриваемого интервала.",
            2,
        )
        self.drill_interval = self._spin(
            1_000.0,
            0.0,
            50_000.0,
            " м",
            "Длина интервала для расчёта кольцевого объёма.",
            1,
        )
        self.drill_flow = self._spin(
            30.0,
            0.001,
            10_000.0,
            " л/с",
            "Фактическая подача насосов.",
            2,
        )
        self.drill_result = self._result_label(page)
        fields = (
            ("Плотность раствора", self.drill_mud_density),
            ("TVD", self.drill_tvd),
            ("Диаметр ствола", self.drill_hole_d),
            ("Наружный диаметр трубы", self.drill_pipe_d),
            ("Длина интервала", self.drill_interval),
            ("Расход насосов", self.drill_flow),
        )
        for row, (label, control) in enumerate(fields, start=1):
            layout.addWidget(QLabel(label, page), row, 0)
            layout.addWidget(control, row, 1)
        layout.addWidget(self.drill_result, 1, 2, len(fields), 2)
        for _label, control in fields:
            control.valueChanged.connect(self._update_drilling_calculator)
        self._update_drilling_calculator()
        return page

    def _update_drilling_calculator(self, *_args: object) -> None:
        try:
            pressure = hydrostatic_pressure(
                self.drill_mud_density.value(), self.drill_tvd.value()
            )
            annulus = annular_volume(
                self.drill_hole_d.value(),
                self.drill_pipe_d.value(),
                self.drill_interval.value(),
            )
            minutes = circulation_time_minutes(
                annulus.volume_m3, self.drill_flow.value()
            )
            self.drill_result.setText(
                f"Гидростатическое давление: <b>{pressure.pressure_mpa:.3f} МПа</b> "
                f"({pressure.pressure_psi:.1f} psi)<br>"
                f"Градиент: {pressure.gradient_kpa_per_m:.4f} кПа/м<br>"
                f"Кольцевая вместимость: {annulus.capacity_l_per_m:.3f} л/м<br>"
                f"Объём интервала: {annulus.volume_m3:.3f} м³ ({annulus.volume_l:.1f} л)<br>"
                f"Теоретическое время прокачки: {minutes:.2f} мин"
            )
        except Exception as error:
            self.drill_result.setText(f"Ошибка исходных данных: {error}")

    def _build_mud_calculator(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        layout = QGridLayout(page)
        help_label = QLabel(
            "ECD учитывает плотность раствора и потери давления в затрубном пространстве. "
            "Смешение двух объёмов рассчитано по сохранению массы без учёта химической усадки и реакции компонентов.",
            page,
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("hint")
        layout.addWidget(help_label, 0, 0, 1, 4)
        self.mud_density = self._spin(
            1_200.0,
            1.0,
            5_000.0,
            " кг/м³",
            "Статическая плотность раствора.",
            1,
        )
        self.mud_annular_loss = self._spin(
            2.5,
            0.0,
            200.0,
            " МПа",
            "Суммарные потери давления в кольцевом пространстве до выбранной глубины.",
            3,
        )
        self.mud_tvd = self._spin(
            2_500.0,
            0.001,
            20_000.0,
            " м",
            "TVD точки, для которой рассчитывается ECD.",
            1,
        )
        self.mix_v1 = self._spin(
            10.0, 0.0, 1_000_000.0, " м³", "Объём первого раствора.", 2
        )
        self.mix_rho1 = self._spin(
            1_200.0,
            0.0,
            5_000.0,
            " кг/м³",
            "Плотность первого раствора.",
            1,
        )
        self.mix_v2 = self._spin(
            5.0, 0.0, 1_000_000.0, " м³", "Объём добавляемой жидкости.", 2
        )
        self.mix_rho2 = self._spin(
            1_000.0,
            0.0,
            5_000.0,
            " кг/м³",
            "Плотность добавляемой жидкости.",
            1,
        )
        self.mud_result = self._result_label(page)
        fields = (
            ("Плотность раствора", self.mud_density),
            ("Потери давления в затрубье", self.mud_annular_loss),
            ("TVD", self.mud_tvd),
            ("Объём 1", self.mix_v1),
            ("Плотность 1", self.mix_rho1),
            ("Объём 2", self.mix_v2),
            ("Плотность 2", self.mix_rho2),
        )
        for row, (label, control) in enumerate(fields, start=1):
            layout.addWidget(QLabel(label, page), row, 0)
            layout.addWidget(control, row, 1)
        layout.addWidget(self.mud_result, 1, 2, len(fields), 2)
        for _label, control in fields:
            control.valueChanged.connect(self._update_mud_calculator)
        self._update_mud_calculator()
        return page

    def _update_mud_calculator(self, *_args: object) -> None:
        try:
            ecd = equivalent_circulating_density(
                self.mud_density.value(),
                self.mud_annular_loss.value(),
                self.mud_tvd.value(),
            )
            mixture = mixed_fluid_density(
                self.mix_v1.value(),
                self.mix_rho1.value(),
                self.mix_v2.value(),
                self.mix_rho2.value(),
            )
            self.mud_result.setText(
                f"ECD: <b>{ecd:.2f} кг/м³</b> ({ecd / 119.826427316:.3f} ppg)<br>"
                f"Плотность смеси: <b>{mixture:.2f} кг/м³</b><br>"
                "Примечание: ECD требует реальных потерь давления из гидравлической модели или измерений."
            )
        except Exception as error:
            self.mud_result.setText(f"Ошибка исходных данных: {error}")

    def _build_geology_calculator(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        layout = QFormLayout(page)
        help_label = QLabel(
            "Абсолютная отметка точки = абсолютная отметка datum − TVD. "
            "Используйте ту же точку отсчёта, что указана в шапке каротажа: KB/RKB, DF или другой datum.",
            page,
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("hint")
        layout.addRow(help_label)
        self.geo_reference = self._spin(
            135.0,
            -20_000.0,
            20_000.0,
            " м",
            "Абсолютная отметка принятой точки отсчёта глубины.",
            3,
        )
        self.geo_top_tvd = self._spin(
            2_200.0,
            0.0,
            30_000.0,
            " м",
            "TVD кровли пласта от выбранного datum.",
            3,
        )
        self.geo_bottom_tvd = self._spin(
            2_250.0,
            0.0,
            30_000.0,
            " м",
            "TVD подошвы пласта от того же datum.",
            3,
        )
        self.geo_result = self._result_label(page)
        layout.addRow("Абсолютная отметка datum:", self.geo_reference)
        layout.addRow("TVD кровли:", self.geo_top_tvd)
        layout.addRow("TVD подошвы:", self.geo_bottom_tvd)
        layout.addRow("Результат:", self.geo_result)
        for control in (
            self.geo_reference,
            self.geo_top_tvd,
            self.geo_bottom_tvd,
        ):
            control.valueChanged.connect(self._update_geology_calculator)
        self._update_geology_calculator()
        return page

    def _update_geology_calculator(self, *_args: object) -> None:
        try:
            result = formation_elevations(
                self.geo_reference.value(),
                self.geo_top_tvd.value(),
                self.geo_bottom_tvd.value(),
            )
            self.geo_result.setText(
                f"Абсолютная отметка кровли: <b>{result.top_elevation_m:.3f} м</b><br>"
                f"Абсолютная отметка подошвы: <b>{result.bottom_elevation_m:.3f} м</b><br>"
                f"Вертикальная мощность: {result.vertical_thickness_m:.3f} м"
            )
        except Exception as error:
            self.geo_result.setText(f"Ошибка исходных данных: {error}")

    def _install_header_shortcuts(self) -> None:
        header = self.findChild(QFrame, "filesHeader")
        layout = header.layout() if header is not None else None
        if not isinstance(layout, QHBoxLayout):
            return
        archive_button = QPushButton("Архивы", header)
        archive_button.setToolTip("Перейти к созданию или распаковке архива.")
        archive_button.clicked.connect(lambda: self.show_section(3))
        layout.addWidget(archive_button)
        engineering_button = QPushButton("Нефтегазовые расчёты", header)
        engineering_button.setToolTip(
            "Открыть расчёты труб, бурения, раствора и геологии."
        )
        engineering_button.clicked.connect(lambda: self.show_section(4))
        layout.addWidget(engineering_button)

    def _install_main_toolbar_entry(self) -> None:
        self._toolbar_attempts += 1
        window: Any = self.window()
        row = getattr(window, "main_toolbar_row", None)
        layout = getattr(window, "main_toolbar_layout", None)
        action = getattr(window, "file_workspace_action", None)
        separator = getattr(window, "_main_toolbar_separator_files", None)
        if row is None or layout is None or action is None:
            if self._toolbar_attempts < 20:
                QTimer.singleShot(100, self._install_main_toolbar_entry)
            return
        if getattr(window, "files_workspace_toolbar_button", None) is not None:
            return
        action.setText("Файлы и расчёты")
        action.setToolTip(
            "Быстро открыть PDF-редактор, архиватор, конвертер единиц и нефтегазовые расчёты (Ctrl+Alt+F)."
        )
        button = QToolButton(row)
        button.setObjectName("filesWorkspaceToolbarButton")
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        index = layout.indexOf(separator) if separator is not None else -1
        if index >= 0:
            layout.insertWidget(index, button)
        else:
            layout.addWidget(button)
        window.files_workspace_toolbar_button = button

        overflow = getattr(window, "main_toolbar_overflow_menu", None)
        if overflow is not None and action not in overflow.actions():
            overflow.addAction(action)
        compact = getattr(window, "_main_toolbar_compact_buttons", ())
        window._main_toolbar_compact_buttons = tuple(compact) + (button,)
        candidates = getattr(window, "_main_toolbar_overflow_candidates", ())
        window._main_toolbar_overflow_candidates = tuple(candidates) + (
            ("files_workspace", button),
        )
