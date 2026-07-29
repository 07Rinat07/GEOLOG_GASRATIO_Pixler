from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.files.document_service import DocumentError, DocumentKind
from geoworkbench.files.engineering import (
    EngineeringExpressionError,
    format_engineering_value,
)
from geoworkbench.ui.file_workspace_full_widget import (
    FileWorkspaceWidget as _LegacyFileWorkspaceWidget,
)


class FileWorkspaceWidget(_LegacyFileWorkspaceWidget):
    """Production-oriented shell for the document and engineering services.

    The previous implementation exposed working service methods through a set of
    raw forms. This class keeps the tested services but presents them as a
    discoverable desktop workspace: a visible header, a command bar, page and
    property sidebars, contextual tools, live calculations and explicit status.
    """

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        self._redesign_ready = False
        self._syncing_pages = False
        super().__init__(parent, language=language)
        self.setObjectName("modernFileWorkspace")

        self._page_list = QListWidget(self)
        self._selection_info = QLabel(self)
        self._document_info = QLabel(self)
        self._converter_equation = QLabel(self)
        self._converter_error = QLabel(self)
        self._calculator_error = QLabel(self)
        self._logo_preview_timer = QTimer(self)
        self._logo_preview_timer.setSingleShot(True)
        self._logo_preview_timer.setInterval(120)
        self._logo_preview_timer.timeout.connect(self._refresh_logo)

        self._pdf_tools: list[QToolButton] = []
        self._image_tools: list[QToolButton] = []
        self._document_actions: list[QToolButton] = []

        self._build_header_and_navigation()
        self._rebuild_document_page()
        self._improve_engineering_page()
        self._improve_logo_page()
        self._improve_archive_page()
        self._improve_pdf_tools_page()
        self._apply_theme()

        self._redesign_ready = True
        self._calculate_expression_live()
        self._convert_units_live()
        self._sync_document_state()

    @staticmethod
    def tab_title(language: str) -> str:
        return {
            "ru": "Файлы / PDF / Калькулятор",
            "kk": "Файлдар / PDF / Калькулятор",
            "en": "Files / PDF / Calculator",
        }.get(language, "Файлы / PDF / Калькулятор")

    def _build_header_and_navigation(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return

        header = QFrame(self)
        header.setObjectName("filesHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(10)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = QLabel("Файлы · PDF · Инженерные инструменты", header)
        title.setObjectName("filesTitle")
        subtitle = QLabel(
            "Полноценное рабочее пространство для документов, архивов и расчётов "
            "без обязательного открытия LAS-проекта.",
            header,
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        row.addLayout(copy, 1)

        open_button = QPushButton("Открыть документ", header)
        open_button.setObjectName("primaryButton")
        open_button.setMinimumHeight(36)
        open_button.clicked.connect(self._open_document)
        row.addWidget(open_button)

        calculator_button = QPushButton("Калькулятор", header)
        calculator_button.setMinimumHeight(36)
        calculator_button.clicked.connect(lambda: self.sections.setCurrentIndex(4))
        row.addWidget(calculator_button)

        root.insertWidget(0, header)

        self.sections.setTabPosition(QTabWidget.TabPosition.West)
        self.sections.setDocumentMode(True)
        self.sections.setUsesScrollButtons(True)
        titles = (
            "Документы",
            "PDF-инструменты",
            "Логотип",
            "Архивы",
            "Инженерные расчёты",
        )
        tooltips = (
            "Просмотр и редактирование PDF и изображений",
            "Объединение, разделение PDF и экспорт в DOCX",
            "Создание растровых логотипов",
            "Создание, просмотр и безопасная распаковка архивов",
            "Калькулятор, конвертер единиц и вертикальные отметки",
        )
        for index, (title_text, tooltip) in enumerate(
            zip(titles, tooltips, strict=True)
        ):
            self.sections.setTabText(index, title_text)
            self.sections.setTabToolTip(index, tooltip)

    def _rebuild_document_page(self) -> None:
        page = self.sections.widget(0)
        layout = page.layout()
        if not isinstance(layout, QVBoxLayout):
            return

        for row_index in (0, 1):
            row_item = layout.itemAt(row_index)
            row = row_item.layout() if row_item is not None else None
            if isinstance(row, QHBoxLayout):
                for item_index in range(row.count()):
                    widget = row.itemAt(item_index).widget()
                    if widget is not None:
                        widget.hide()

        command_bar = QFrame(page)
        command_bar.setObjectName("commandBar")
        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(8, 7, 8, 7)
        command_layout.setSpacing(5)

        self.open_document_button = self._command_button(
            "Открыть",
            QStyle.StandardPixmap.SP_DialogOpenButton,
            self._open_document,
            parent=command_bar,
            primary=True,
        )
        self.save_document_button = self._command_button(
            "Сохранить",
            QStyle.StandardPixmap.SP_DialogSaveButton,
            self._save_document,
            parent=command_bar,
        )
        self.save_as_document_button = self._command_button(
            "Сохранить как",
            QStyle.StandardPixmap.SP_DialogSaveButton,
            self._save_document_as,
            parent=command_bar,
        )
        self._document_actions.extend(
            [
                self.save_document_button,
                self.save_as_document_button,
            ]
        )
        command_layout.addWidget(self.open_document_button)
        command_layout.addWidget(self.save_document_button)
        command_layout.addWidget(self.save_as_document_button)
        command_layout.addWidget(self._separator(command_bar))

        self.undo_document_button = self._command_button(
            "Отменить",
            QStyle.StandardPixmap.SP_ArrowBack,
            self._undo_document,
            parent=command_bar,
        )
        self.redo_document_button = self._command_button(
            "Повторить",
            QStyle.StandardPixmap.SP_ArrowForward,
            self._redo_document,
            parent=command_bar,
        )
        command_layout.addWidget(self.undo_document_button)
        command_layout.addWidget(self.redo_document_button)
        command_layout.addWidget(self._separator(command_bar))

        previous = self._command_button(
            "Назад",
            QStyle.StandardPixmap.SP_ArrowLeft,
            self._previous_page,
            parent=command_bar,
            text_visible=False,
        )
        next_button = self._command_button(
            "Вперёд",
            QStyle.StandardPixmap.SP_ArrowRight,
            self._next_page,
            parent=command_bar,
            text_visible=False,
        )
        self.page_label.show()
        self.page_label.setMinimumWidth(105)
        command_layout.addWidget(previous)
        command_layout.addWidget(self.page_label)
        command_layout.addWidget(next_button)
        command_layout.addWidget(self._separator(command_bar))

        zoom_out = self._text_button("−", self._zoom_out, command_bar)
        zoom_out.setToolTip("Уменьшить масштаб")
        zoom_in = self._text_button("+", self._zoom_in, command_bar)
        zoom_in.setToolTip("Увеличить масштаб")
        self.zoom_spin.show()
        self.zoom_spin.setFixedWidth(92)
        command_layout.addWidget(zoom_out)
        command_layout.addWidget(self.zoom_spin)
        command_layout.addWidget(zoom_in)
        command_layout.addWidget(self._text_button("По ширине", self._fit_width, command_bar))
        command_layout.addWidget(self._text_button("Вся страница", self._fit_page, command_bar))
        command_layout.addStretch(1)
        layout.insertWidget(0, command_bar)

        context_bar = QFrame(page)
        context_bar.setObjectName("contextBar")
        context_layout = QHBoxLayout(context_bar)
        context_layout.setContentsMargins(8, 6, 8, 6)
        context_layout.setSpacing(5)
        context_label = QLabel("Инструменты:", context_bar)
        context_label.setObjectName("muted")
        context_layout.addWidget(context_label)

        for text, callback in (
            ("Добавить текст", self._add_pdf_text),
            ("Выделить", self._highlight_pdf),
            ("Примечание", self._note_pdf),
            ("Безопасно скрыть", self._redact_pdf),
            ("Удалить аннотации", self._delete_pdf_annotations),
        ):
            button = self._text_button(text, callback, context_bar)
            self._pdf_tools.append(button)
            context_layout.addWidget(button)

        context_layout.addWidget(self._separator(context_bar))
        for text, callback in (
            ("Размер", self._resize_image),
            ("Обрезать", self._crop_image),
            ("Коррекция", self._correct_image),
        ):
            button = self._text_button(text, callback, context_bar)
            self._image_tools.append(button)
            context_layout.addWidget(button)
        context_layout.addStretch(1)
        layout.insertWidget(1, context_bar)

        hint = QLabel(
            "Выберите страницу и выделите область мышью. После этого примените "
            "контекстную команду и сохраните копию документа.",
            page,
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.insertWidget(2, hint)

        layout.removeWidget(self.document_scroll)
        layout.removeWidget(self.document_status)

        splitter = QSplitter(Qt.Orientation.Horizontal, page)
        splitter.setObjectName("documentWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)

        left = self._side_panel(splitter)
        left_layout = left.layout()
        assert isinstance(left_layout, QVBoxLayout)
        left_layout.addWidget(self._panel_title("Документ"))
        self._document_info.setObjectName("muted")
        self._document_info.setText("Файл не открыт")
        self._document_info.setWordWrap(True)
        left_layout.addWidget(self._document_info)
        left_layout.addWidget(self._panel_title("Страницы"))
        self._page_list.setObjectName("pageList")
        self._page_list.setIconSize(QSize(72, 96))
        self._page_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._page_list.currentRowChanged.connect(self._page_selected)
        left_layout.addWidget(self._page_list, 1)

        center = QFrame(splitter)
        center.setObjectName("canvasFrame")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.document_scroll.setObjectName("documentScroll")
        center_layout.addWidget(self.document_scroll, 1)

        right = self._side_panel(splitter)
        right_layout = right.layout()
        assert isinstance(right_layout, QVBoxLayout)
        right_layout.addWidget(self._panel_title("Быстрый порядок работы"))
        instructions = QLabel(
            "1. Откройте файл.\n"
            "2. Выберите страницу.\n"
            "3. Выделите область.\n"
            "4. Примените инструмент.\n"
            "5. Сохраните отдельную копию.",
            right,
        )
        instructions.setObjectName("muted")
        instructions.setWordWrap(True)
        right_layout.addWidget(instructions)
        right_layout.addWidget(self._panel_title("Выделенная область"))
        self._selection_info.setObjectName("muted")
        self._selection_info.setText("Область не выбрана")
        self._selection_info.setWordWrap(True)
        right_layout.addWidget(self._selection_info)
        right_layout.addStretch(1)
        right_layout.addWidget(self._panel_title("Состояние"))
        self.document_status.setObjectName("statusCard")
        self.document_status.setWordWrap(True)
        right_layout.addWidget(self.document_status)

        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 920, 250])
        layout.addWidget(splitter, 1)

        self.document_canvas.selection_changed.connect(self._selection_changed)

    def _improve_engineering_page(self) -> None:
        page = self.sections.widget(4)
        layout = page.layout()
        if not isinstance(layout, QVBoxLayout):
            return

        hint = QLabel(
            "Результаты обновляются сразу. При изменении категории или единиц "
            "старое значение очищается и рассчитывается заново.",
            page,
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.insertWidget(0, hint)

        self.expression_input.setPlaceholderText("Например: sqrt(144) + 2 1/2")
        self.expression_result.setObjectName("resultField")
        self.expression_result.setPlaceholderText("Результат")
        self.expression_input.textChanged.connect(self._calculate_expression_live)
        self._calculator_error.setObjectName("inlineError")
        self._calculator_error.setWordWrap(True)
        calculator_group = self.expression_input.parentWidget()
        if calculator_group is not None and calculator_group.layout() is not None:
            calculator_group.layout().addWidget(self._calculator_error)

        self.converter_result.setObjectName("resultField")
        self.converter_result.setPlaceholderText("Результат")
        self._converter_equation.setObjectName("equation")
        self._converter_equation.setWordWrap(True)
        self._converter_error.setObjectName("inlineError")
        self._converter_error.setWordWrap(True)

        converter_group = self.converter_category.parentWidget()
        converter_layout = converter_group.layout() if converter_group is not None else None
        if isinstance(converter_layout, QGridLayout):
            swap_button = QPushButton("⇄ Поменять местами", converter_group)
            swap_button.clicked.connect(self._swap_converter_units)
            converter_layout.addWidget(swap_button, 2, 0, 1, 2)
            converter_layout.addWidget(self._converter_equation, 2, 2, 1, 4)
            converter_layout.addWidget(self._converter_error, 3, 0, 1, 6)

        self.converter_value.textChanged.connect(self._convert_units_live)
        self.converter_category.currentIndexChanged.connect(self._schedule_conversion)
        self.converter_source.currentIndexChanged.connect(self._schedule_conversion)
        self.converter_target.currentIndexChanged.connect(self._schedule_conversion)

        for control in self.datum_inputs:
            control.valueChanged.connect(self._calculate_datum)

        header = self.datum_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.datum_table.verticalHeader().setVisible(False)

    def _improve_logo_page(self) -> None:
        page = self.sections.widget(2)
        layout = page.layout()
        if not isinstance(layout, QHBoxLayout):
            return

        presets = QFrame(page)
        presets.setObjectName("floatingCard")
        preset_layout = QVBoxLayout(presets)
        preset_layout.addWidget(self._panel_title("Быстрые стили"))
        for title, foreground, background, transparent, border in (
            ("Строгий светлый", "#0f172a", "#ffffff", False, 0),
            ("Геологический", "#f8fafc", "#1f4d3a", False, 2),
            ("Технический синий", "#ffffff", "#1d4ed8", False, 0),
            ("Прозрачный", "#0f172a", "#ffffff", True, 0),
        ):
            button = QPushButton(title, presets)
            button.clicked.connect(
                lambda _checked=False,
                fg=foreground,
                bg=background,
                tr=transparent,
                bw=border: self._apply_logo_preset(fg, bg, tr, bw)
            )
            preset_layout.addWidget(button)
        preset_layout.addStretch(1)
        layout.insertWidget(1, presets)

        self.logo_preview.setObjectName("logoPreview")
        for widget in (
            self.logo_text,
            self.logo_width,
            self.logo_height,
            self.logo_font_size,
            self.logo_foreground,
            self.logo_background,
            self.logo_transparent,
            self.logo_border_width,
            self.logo_border_color,
        ):
            signal = getattr(widget, "textChanged", None)
            if signal is not None:
                signal.connect(self._schedule_logo_preview)
                continue
            signal = getattr(widget, "valueChanged", None)
            if signal is not None:
                signal.connect(self._schedule_logo_preview)
                continue
            signal = getattr(widget, "toggled", None)
            if signal is not None:
                signal.connect(self._schedule_logo_preview)

    def _improve_archive_page(self) -> None:
        page = self.sections.widget(3)
        layout = page.layout()
        if not isinstance(layout, QVBoxLayout):
            return
        capabilities = []
        for capability in self.archive_service.capabilities():
            state = []
            if capability.can_create:
                state.append("создание")
            if capability.can_extract:
                state.append("распаковка")
            if not state:
                state.append("не установлен backend")
            capabilities.append(
                f"<b>{capability.archive_format.value.upper()}</b>: {', '.join(state)}"
            )
        self.archive_capabilities.setText(" &nbsp; · &nbsp; ".join(capabilities))
        self.archive_capabilities.setObjectName("capabilityStrip")
        self.archive_capabilities.setTextFormat(Qt.TextFormat.RichText)
        header = self.archive_entries.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

    def _improve_pdf_tools_page(self) -> None:
        page = self.sections.widget(1)
        layout = page.layout()
        if not isinstance(layout, QVBoxLayout):
            return
        title = QLabel("Пакетные операции с PDF", page)
        title.setObjectName("sectionTitle")
        layout.insertWidget(0, title)
        self.pdf_tools_log.setObjectName("operationLog")
        self.pdf_tools_log.setPlaceholderText(
            "Здесь появится журнал: исходный файл, созданный результат и количество страниц."
        )

    def _apply_theme(self) -> None:
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        if dark:
            colors = {
                "window": "#171a1f",
                "panel": "#20242b",
                "card": "#262b34",
                "hover": "#303744",
                "border": "#3a4351",
                "text": "#f4f7fb",
                "muted": "#aeb8c7",
                "accent": "#4c9dff",
                "accent_hover": "#69adff",
                "accent_text": "#07111f",
                "danger": "#ff7676",
                "canvas": "#111418",
            }
        else:
            colors = {
                "window": "#f4f7fb",
                "panel": "#ffffff",
                "card": "#f8fafc",
                "hover": "#eaf2ff",
                "border": "#d6deea",
                "text": "#172033",
                "muted": "#5e6b7e",
                "accent": "#2563eb",
                "accent_hover": "#1d4ed8",
                "accent_text": "#ffffff",
                "danger": "#c62828",
                "canvas": "#dfe6ef",
            }
        self.setStyleSheet(
            f"""
            QWidget#modernFileWorkspace {{ background: {colors['window']}; color: {colors['text']}; }}
            QFrame#filesHeader {{ background: {colors['panel']}; border: 1px solid {colors['border']}; border-radius: 12px; }}
            QLabel#filesTitle {{ font-size: 18px; font-weight: 700; color: {colors['text']}; }}
            QLabel#sectionTitle {{ font-size: 17px; font-weight: 700; padding: 4px 2px; }}
            QLabel#muted {{ color: {colors['muted']}; }}
            QLabel#hint, QLabel#capabilityStrip {{ background: {colors['card']}; border: 1px solid {colors['border']}; border-radius: 8px; padding: 8px 10px; color: {colors['muted']}; }}
            QLabel#equation {{ color: {colors['accent']}; font-size: 14px; font-weight: 700; padding: 4px; }}
            QLabel#inlineError {{ color: {colors['danger']}; padding: 2px 4px; }}
            QLabel#statusCard {{ background: {colors['card']}; border: 1px solid {colors['border']}; border-radius: 8px; padding: 10px; }}
            QFrame#commandBar, QFrame#contextBar, QFrame#floatingCard {{ background: {colors['panel']}; border: 1px solid {colors['border']}; border-radius: 9px; }}
            QFrame#sidePanel {{ background: {colors['panel']}; border: 1px solid {colors['border']}; border-radius: 9px; }}
            QFrame#canvasFrame {{ background: {colors['canvas']}; border: 1px solid {colors['border']}; border-radius: 9px; }}
            QFrame#separator {{ background: {colors['border']}; min-width: 1px; max-width: 1px; margin: 4px 3px; }}
            QPushButton, QToolButton {{ min-height: 30px; border: 1px solid {colors['border']}; border-radius: 7px; padding: 4px 9px; background: {colors['card']}; color: {colors['text']}; }}
            QPushButton:hover, QToolButton:hover {{ background: {colors['hover']}; border-color: {colors['accent']}; }}
            QPushButton:disabled, QToolButton:disabled {{ color: {colors['muted']}; background: {colors['panel']}; border-color: {colors['border']}; }}
            QPushButton#primaryButton, QToolButton#primaryButton {{ background: {colors['accent']}; border-color: {colors['accent']}; color: {colors['accent_text']}; font-weight: 700; }}
            QPushButton#primaryButton:hover, QToolButton#primaryButton:hover {{ background: {colors['accent_hover']}; }}
            QTabWidget#fileWorkspaceSections::pane {{ border: 1px solid {colors['border']}; border-radius: 9px; background: {colors['window']}; }}
            QTabWidget#fileWorkspaceSections QTabBar::tab {{ min-width: 150px; min-height: 36px; padding: 7px 12px; margin: 2px 5px 2px 0; border: 1px solid transparent; border-radius: 8px; color: {colors['muted']}; background: transparent; text-align: left; }}
            QTabWidget#fileWorkspaceSections QTabBar::tab:hover {{ background: {colors['hover']}; color: {colors['text']}; }}
            QTabWidget#fileWorkspaceSections QTabBar::tab:selected {{ background: {colors['card']}; border-color: {colors['border']}; color: {colors['accent']}; font-weight: 700; }}
            QListWidget#pageList, QTextEdit#operationLog, QTreeWidget, QTableWidget, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {colors['panel']}; color: {colors['text']}; border: 1px solid {colors['border']}; border-radius: 7px; selection-background-color: {colors['accent']}; selection-color: {colors['accent_text']}; }}
            QListWidget#pageList::item {{ padding: 7px; margin: 2px; border-radius: 6px; }}
            QListWidget#pageList::item:selected {{ background: {colors['accent']}; color: {colors['accent_text']}; }}
            QLineEdit#resultField {{ font-size: 15px; font-weight: 700; color: {colors['accent']}; }}
            QLabel#logoPreview {{ background: {colors['canvas']}; border: 1px solid {colors['border']}; border-radius: 10px; }}
            QScrollArea#documentScroll {{ border: none; background: {colors['canvas']}; }}
            QGroupBox {{ border: 1px solid {colors['border']}; border-radius: 9px; margin-top: 12px; padding-top: 8px; font-weight: 600; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
            """
        )

    def _command_button(self, text: str, icon: QStyle.StandardPixmap, callback: Callable[[], None], *, parent: QWidget, primary: bool = False, text_visible: bool = True) -> QToolButton:
        button = QToolButton(parent)
        button.setText(text)
        button.setIcon(self.style().standardIcon(icon))
        button.setIconSize(QSize(17, 17))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text_visible else Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setToolTip(text)
        if primary:
            button.setObjectName("primaryButton")
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _text_button(text: str, callback: Callable[[], None], parent: QWidget) -> QToolButton:
        button = QToolButton(parent)
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _separator(parent: QWidget) -> QFrame:
        separator = QFrame(parent)
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        return separator

    @staticmethod
    def _side_panel(parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("sidePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        return panel

    @staticmethod
    def _panel_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 700;")
        return label

    def _open_document(self) -> None:
        super()._open_document()
        if self.document_service.is_open:
            self._populate_page_list()
        self._sync_document_state()

    def _refresh_document(self) -> None:
        super()._refresh_document()
        if self._redesign_ready:
            self._sync_document_state()

    def _sync_document_state(self) -> None:
        is_open = self.document_service.is_open
        is_pdf = self.document_service.kind is DocumentKind.PDF
        is_image = self.document_service.kind is DocumentKind.IMAGE
        for button in self._document_actions:
            button.setEnabled(is_open)
        self.undo_document_button.setEnabled(is_open and self.document_service.can_undo)
        self.redo_document_button.setEnabled(is_open and self.document_service.can_redo)
        for button in self._pdf_tools:
            button.setEnabled(is_pdf)
        for button in self._image_tools:
            button.setEnabled(is_image)
        if not is_open:
            self._document_info.setText("Файл не открыт")
            self._page_list.clear()
            return
        path = self.document_service.path
        kind = "PDF" if is_pdf else "Изображение"
        self._document_info.setText(f"<b>{path.name if path else 'Документ'}</b><br>{kind} · страниц: {self.document_service.page_count}")
        if self._page_list.count() != self.document_service.page_count:
            self._populate_page_list()
        if self._page_list.count():
            self._syncing_pages = True
            self._page_list.setCurrentRow(self.document_service.page_index)
            self._syncing_pages = False

    def _populate_page_list(self) -> None:
        self._syncing_pages = True
        self._page_list.clear()
        count = self.document_service.page_count
        for page_index in range(count):
            item = QListWidgetItem(f"Страница {page_index + 1}")
            item.setData(Qt.ItemDataRole.UserRole, page_index)
            item.setToolTip(f"Перейти на страницу {page_index + 1}")
            self._page_list.addItem(item)
        if count:
            self._page_list.setCurrentRow(self.document_service.page_index)
        self._syncing_pages = False
        self._load_visible_page_icons()

    def _load_visible_page_icons(self) -> None:
        if self.document_service.kind is not DocumentKind.PDF:
            return
        count = self._page_list.count()
        if not count:
            return
        current = self.document_service.page_index
        indexes = {current}
        for offset in (1, 2):
            if current - offset >= 0:
                indexes.add(current - offset)
            if current + offset < count:
                indexes.add(current + offset)
        try:
            for page_index in sorted(indexes):
                self.document_service.set_page(page_index)
                rendered = self.document_service.render(0.18)
                pixmap = QPixmap()
                if pixmap.loadFromData(rendered.payload):
                    icon = pixmap.scaled(QSize(72, 96), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self._page_list.item(page_index).setIcon(icon)
        except DocumentError:
            pass
        finally:
            self.document_service.set_page(current)

    def _page_selected(self, row: int) -> None:
        if self._syncing_pages or row < 0:
            return
        try:
            self.document_service.set_page(row)
            self._refresh_document()
            self._load_visible_page_icons()
        except DocumentError as error:
            self._show_error("Переход по страницам", error)

    def _selection_changed(self, selection: QRect) -> None:
        if selection.isNull() or selection.width() < 2 or selection.height() < 2:
            self._selection_info.setText("Область не выбрана")
            return
        scale = max(self._render_zoom, 0.1)
        width = selection.width() / scale
        height = selection.height() / scale
        self._selection_info.setText(f"{width:.1f} × {height:.1f} pt\nЭкран: {selection.width()} × {selection.height()} px")

    def _zoom_out(self) -> None:
        self.zoom_spin.setValue(max(self.zoom_spin.minimum(), self.zoom_spin.value() - 10))

    def _zoom_in(self) -> None:
        self.zoom_spin.setValue(min(self.zoom_spin.maximum(), self.zoom_spin.value() + 10))

    def _fit_width(self) -> None:
        self._fit_document(use_height=False)

    def _fit_page(self) -> None:
        self._fit_document(use_height=True)

    def _fit_document(self, *, use_height: bool) -> None:
        if not self.document_service.is_open:
            return
        try:
            rendered = self.document_service.render(1.0)
        except DocumentError as error:
            self._show_error("Масштаб", error)
            return
        viewport = self.document_scroll.viewport().size()
        width_scale = max(0.1, (viewport.width() - 34) / max(1, rendered.width))
        scale = width_scale
        if use_height:
            height_scale = max(0.1, (viewport.height() - 34) / max(1, rendered.height))
            scale = min(width_scale, height_scale)
        self.zoom_spin.setValue(max(10, min(800, round(scale * 100))))

    def _calculate_expression_live(self, *_args: object) -> None:
        expression = self.expression_input.text().strip()
        if not expression:
            self.expression_result.clear()
            self._calculator_error.clear()
            return
        try:
            result = self.calculator.evaluate(expression)
        except EngineeringExpressionError as error:
            self.expression_result.clear()
            self._calculator_error.setText(str(error))
            return
        self.expression_result.setText(format_engineering_value(result))
        self._calculator_error.clear()

    def _calculate_expression(self) -> None:
        self._calculate_expression_live()

    def _schedule_conversion(self, *_args: object) -> None:
        QTimer.singleShot(0, self._convert_units_live)

    def _convert_units_live(self, *_args: object) -> None:
        value_text = self.converter_value.text().strip()
        category = self.converter_category.currentData()
        source = self.converter_source.currentData()
        target = self.converter_target.currentData()
        if not value_text or not isinstance(category, str) or not isinstance(source, str) or not isinstance(target, str):
            self.converter_result.clear()
            self._converter_equation.clear()
            self._converter_error.clear()
            return
        try:
            numeric = self.converter.parse_value(value_text)
            result = self.converter.convert(numeric, category, source, target)
        except (EngineeringExpressionError, KeyError, ValueError) as error:
            self.converter_result.clear()
            self._converter_equation.clear()
            self._converter_error.setText(str(error))
            return
        formatted = format_engineering_value(result)
        self.converter_result.setText(formatted)
        source_label = self.converter_source.currentText()
        target_label = self.converter_target.currentText()
        self._converter_equation.setText(f"{format_engineering_value(numeric)} {source_label} = {formatted} {target_label}")
        self._converter_error.clear()

    def _convert_units(self) -> None:
        self._convert_units_live()

    def _swap_converter_units(self) -> None:
        source_index = self.converter_source.currentIndex()
        target_index = self.converter_target.currentIndex()
        self.converter_source.setCurrentIndex(target_index)
        self.converter_target.setCurrentIndex(source_index)
        self._convert_units_live()

    def _apply_logo_preset(self, foreground: str, background: str, transparent: bool, border_width: int) -> None:
        self.logo_foreground.setText(foreground)
        self.logo_background.setText(background)
        self.logo_transparent.setChecked(transparent)
        self.logo_border_width.setValue(border_width)
        self.logo_border_color.setText(foreground)
        self._schedule_logo_preview()

    def _schedule_logo_preview(self, *_args: object) -> None:
        self._logo_preview_timer.start()
