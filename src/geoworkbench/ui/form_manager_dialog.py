from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from geoworkbench.forms.codec import form_from_dict, form_to_dict
from geoworkbench.domain.models import Dataset, IndexRole
from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.apply import FormApplyEngine
from geoworkbench.forms.materialize import materialized_factory_templates
from geoworkbench.forms.templates import (
    CURATED_FACTORY_TEMPLATE_IDS,
    curated_factory_templates,
)
from geoworkbench.forms.preview import PreviewCallback
from geoworkbench.form_constructor.preview_revision import PreviewRevisionGate
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.ui.form_structure_editor_dialog import FormStructureEditorDialog
from geoworkbench.ui.collapsible_section import CollapsibleSection


class FormManagerDialog(QDialog):
    def __init__(
        self,
        repository: FormRepository,
        parent=None,
        *,
        language: str = "ru",
        dataset: Dataset | None = None,
        preview_callback: PreviewCallback | None = None,
        print_page_settings: PrintPageSettings | None = None,
        print_page_settings_changed: Callable[[PrintPageSettings], None] | None = None,
        print_form_callback: Callable[[FormDocument], None] | None = None,
        masterlog_sync_callback: Callable[[FormDocument], FormDocument | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.dataset = dataset
        self.language = language
        self.preview_callback = preview_callback
        self.print_page_settings = print_page_settings or PrintPageSettings()
        self.print_page_settings_changed = print_page_settings_changed
        self.print_form_callback = print_form_callback
        self.masterlog_sync_callback = masterlog_sync_callback
        self.apply_engine = FormApplyEngine()
        self.selected_form: FormDocument | None = None
        self.setWindowTitle(self._text("Библиотека форм", "Пішіндер кітапханасы", "Form library"))
        self.setMinimumSize(980, 620)
        self.resize(1180, 720)
        self.setStyleSheet(
            "QDialog { background: #f1f5f9; }"
            "QTreeWidget, QTextEdit { background: white; border: 1px solid #cbd5e1; "
            "border-radius: 7px; }"
            "QPushButton { min-height: 30px; padding: 4px 10px; }"
            "QPushButton#primary-action { background: #2563eb; color: white; "
            "font-weight: 600; border: 0; border-radius: 6px; }"
            "QPushButton#primary-action:hover { background: #1d4ed8; }"
        )

        root_layout = QVBoxLayout(self)
        heading = QLabel(
            self._text(
                "Формы разделены по типу вертикальной оси. Заводские образцы защищены, "
                "а пользовательские формы можно свободно изменять.",
                "Пішіндер тік ось түрі бойынша бөлінген. Зауыттық үлгілер қорғалған, "
                "пайдаланушы пішіндерін еркін өзгертуге болады.",
                "Forms are grouped by vertical-axis type. Factory presets are protected; "
                "user forms remain fully editable.",
            )
        )
        heading.setWordWrap(True)
        heading.setStyleSheet("font-size: 13px; color: #334155; padding: 2px 4px;")
        root_layout.addWidget(heading)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(
            self._text("Поиск формы…", "Пішінді іздеу…", "Search forms…")
        )
        self.search_input.setToolTip(
            self._text(
                "Фильтр по названию, описанию и параметрам формы.",
                "Пішін атауы, сипаттамасы және параметрлері бойынша сүзгі.",
                "Filter by form name, description and parameters.",
            )
        )
        self.search_input.textChanged.connect(self._filter_tree)
        left.addWidget(self.search_input)

        self._selection_gate = PreviewRevisionGate()
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(90)
        self._selection_timer.timeout.connect(self._render_pending_selection)
        self._pending_selection_revision = 0

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setUniformRowHeights(True)
        self.tree_widget.setIndentation(18)
        self.tree_widget.setAlternatingRowColors(False)
        self.tree_widget.currentItemChanged.connect(self._show_selected)
        self.tree_widget.itemDoubleClicked.connect(lambda _item, _column: self._apply())
        self.tree_widget.setToolTip(
            self._text(
                "Дважды нажмите пользовательскую форму, чтобы открыть её на планшете.",
                "Пайдаланушы пішінін планшетте ашу үшін екі рет басыңыз.",
                "Double-click a form to open it on the tablet.",
            )
        )
        # Compatibility alias for older UI tests and plugins.
        self.list_widget = self.tree_widget
        left.addWidget(self.tree_widget, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(0, 0, 0, 0)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setToolTip(
            self._text(
                "Состав выбранной формы, совместимость с текущим LAS и настройки печати.",
                "Таңдалған пішін құрамы, ағымдағы LAS-пен үйлесімділігі және баспа баптаулары.",
                "Selected form contents, LAS compatibility and print settings.",
            )
        )
        right.addWidget(self.details, 1)

        primary_row = QHBoxLayout()
        for caption, callback, tooltip in (
            (
                self._text("Создать форму", "Пішін жасау", "Create form"),
                self._create,
                self._text("Создать пустую глубинную или временную форму.", "Бос тереңдік немесе уақыт пішінін жасау.", "Create an empty depth or time form."),
            ),
            (
                self._text("Копировать", "Көшіру", "Copy"),
                self._copy,
                self._text("Создать независимую пользовательскую копию.", "Тәуелсіз пайдаланушы көшірмесін жасау.", "Create an independent user copy."),
            ),
            (
                self._text("Редактировать", "Өңдеу", "Edit"),
                self._edit,
                self._text("Открыть редактор колонок, дорожек и параметров.", "Бағандар, жолдар және параметрлер редакторын ашу.", "Edit columns, tracks and parameters."),
            ),
        ):
            button = QPushButton(caption)
            button.setObjectName("primary-action")
            button.setToolTip(tooltip)
            button.setStatusTip(tooltip)
            button.clicked.connect(callback)
            primary_row.addWidget(button)
        right.addLayout(primary_row)

        manage_widget = QWidget()
        manage_row = QHBoxLayout(manage_widget)
        manage_row.setContentsMargins(6, 4, 6, 4)
        for caption, callback, tooltip in (
            (self._text("Переименовать", "Атын өзгерту", "Rename"), self._rename, self._text("Изменить название пользовательской формы.", "Пайдаланушы пішінінің атауын өзгерту.", "Rename a user form.")),
            (self._text("Удалить", "Жою", "Delete"), self._delete, self._text("Удалить выбранную пользовательскую форму.", "Таңдалған пайдаланушы пішінін жою.", "Delete the selected user form.")),
        ):
            button = QPushButton(caption)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            manage_row.addWidget(button)
        manage_row.addStretch(1)
        right.addWidget(
            CollapsibleSection(
                self._text("Управление выбранной формой", "Таңдалған пішінді басқару", "Manage selected form"),
                manage_widget,
                expanded=False,
                tooltip=self._text("Редко используемые операции переименования и удаления.", "Сирек қолданылатын атауын өзгерту және жою әрекеттері.", "Less frequently used rename and delete actions."),
            )
        )

        exchange_widget = QWidget()
        exchange_row = QHBoxLayout(exchange_widget)
        exchange_row.setContentsMargins(6, 4, 6, 4)
        for caption, callback, tooltip in (
            (self._text("Импорт JSON", "JSON импорттау", "Import JSON"), self._import_json, self._text("Добавить форму из внешнего JSON-файла.", "Сыртқы JSON файлынан пішін қосу.", "Import a form from JSON.")),
            (self._text("Экспорт JSON", "JSON экспорттау", "Export JSON"), self._export_json, self._text("Сохранить выбранную форму отдельным JSON-файлом.", "Таңдалған пішінді жеке JSON файлына сақтау.", "Export the selected form to JSON.")),
        ):
            button = QPushButton(caption)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            exchange_row.addWidget(button)
        exchange_row.addStretch(1)
        right.addWidget(
            CollapsibleSection(
                self._text("Импорт и экспорт", "Импорт және экспорт", "Import and export"),
                exchange_widget,
                expanded=False,
                tooltip=self._text("Обмен пользовательскими формами между компьютерами.", "Пайдаланушы пішіндерін компьютерлер арасында алмасу.", "Exchange user forms between computers."),
            )
        )

        print_widget = QWidget()
        print_box = QVBoxLayout(print_widget)
        print_box.setContentsMargins(6, 4, 6, 4)
        print_row = QHBoxLayout()
        print_row.addWidget(QLabel(self._text("Печатный макет", "Баспа макеті", "Print layout")))
        self.print_orientation_combo = QComboBox()
        self.print_orientation_combo.addItem(
            self._text("A4 — книжная", "A4 — кітаптық", "A4 — portrait"),
            PrintOrientation.PORTRAIT.value,
        )
        self.print_orientation_combo.addItem(
            self._text("A4 — альбомная", "A4 — альбомдық", "A4 — landscape"),
            PrintOrientation.LANDSCAPE.value,
        )
        orientation_index = self.print_orientation_combo.findData(
            self.print_page_settings.orientation.value
        )
        self.print_orientation_combo.setCurrentIndex(max(0, orientation_index))
        self.print_orientation_combo.currentIndexChanged.connect(self._print_layout_changed)
        self.print_orientation_combo.setToolTip(self._text("Ориентация листа для быстрой печати формы.", "Пішінді жылдам басып шығару парағының бағыты.", "Page orientation for quick form printing."))
        print_row.addWidget(self.print_orientation_combo, 1)
        self.fit_columns_check = QCheckBox(
            self._text("Автоподбор колонок", "Бағандарды автотаңдау", "Auto-fit columns")
        )
        self.fit_columns_check.setChecked(self.print_page_settings.fit_form_columns)
        self.fit_columns_check.toggled.connect(self._print_layout_changed)
        self.fit_columns_check.setToolTip(self._text("Уместить все видимые колонки по ширине листа.", "Барлық көрінетін бағандарды парақ еніне сыйғызу.", "Fit all visible columns to the page width."))
        print_row.addWidget(self.fit_columns_check)
        print_box.addLayout(print_row)
        self.print_layout_hint = QLabel(
            self._text(
                "Все видимые колонки размещаются по ширине листа без горизонтального обрезания.",
                "Барлық көрінетін бағандар көлденең қиылмай парақ еніне орналастырылады.",
                "All visible columns are placed across the page without horizontal clipping.",
            )
        )
        self.print_layout_hint.setWordWrap(True)
        print_box.addWidget(self.print_layout_hint)
        right.addWidget(
            CollapsibleSection(
                self._text("Быстрые настройки печати", "Жылдам баспа баптаулары", "Quick print settings"),
                print_widget,
                expanded=False,
                tooltip=self._text("Разверните только перед печатью или экспортом формы.", "Пішінді басып шығару немесе экспорттау алдында ғана ашыңыз.", "Expand only when printing or exporting the form."),
            )
        )

        open_row = QHBoxLayout()
        self.apply_button = QPushButton(
            self._text("Открыть на планшете", "Планшетте ашу", "Open on tablet")
        )
        self.apply_button.setObjectName("primary-action")
        self.apply_button.setToolTip(self._text("Применить форму к текущему LAS и открыть планшет.", "Пішінді ағымдағы LAS-қа қолданып, планшетті ашу.", "Apply the form to the current LAS and open the tablet."))
        self.apply_button.clicked.connect(self._apply)
        open_row.addWidget(self.apply_button, 1)
        self.print_button = QPushButton(
            self._text("Печать / экспорт", "Басып шығару / экспорт", "Print / export")
        )
        self.print_button.setToolTip(self._text("Открыть центр печати для выбранной формы.", "Таңдалған пішін үшін баспа орталығын ашу.", "Open the print center for the selected form."))
        self.print_button.clicked.connect(self._print_selected)
        self.print_button.setEnabled(self.print_form_callback is not None)
        open_row.addWidget(self.print_button, 1)
        right.addLayout(open_row)

        self.masterlog_sync_button = QPushButton(
            self._text("Создать / обновить Masterlog", "Masterlog жасау / жаңарту", "Create / update Masterlog")
        )
        self.masterlog_sync_button.setToolTip(self._text("Перенести колонки, подписи, шкалы и стили глубинной формы в печатный Masterlog.", "Тереңдік пішінінің бағандарын, жазуларын, шкалаларын және стильдерін баспа Masterlog-қа көшіру.", "Transfer depth-form columns, captions, scales and styles into a printable Masterlog."))
        self.masterlog_sync_button.clicked.connect(self._sync_masterlog)
        self.masterlog_sync_button.setEnabled(self.masterlog_sync_callback is not None)
        right.addWidget(self.masterlog_sync_button)
        close_button = QPushButton(self._text("Закрыть", "Жабу", "Close"))
        close_button.setToolTip(self._text("Закрыть библиотеку без применения другой формы.", "Басқа пішінді қолданбай кітапхананы жабу.", "Close the library without applying another form."))
        close_button.clicked.connect(self.reject)
        right.addWidget(close_button)
        splitter.addWidget(right_panel)
        splitter.setSizes([390, 760])
        self.reload()
        for button in self.findChildren(QPushButton):
            if not button.toolTip().strip():
                button.setToolTip(button.text().replace("&", ""))
            if not button.statusTip().strip():
                button.setStatusTip(button.toolTip())

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def reload(self, selected_id: str | None = None) -> None:
        self.tree_widget.blockSignals(True)
        self.tree_widget.clear()
        try:
            try:
                materialized = materialized_factory_templates(self.dataset, self.language)
                factory = [
                    materialized[form_id]
                    for form_id in CURATED_FACTORY_TEMPLATE_IDS
                    if form_id in materialized
                ]
            except (KeyError, RuntimeError, ValueError):
                factory = list(curated_factory_templates(self.language).values())
            user_forms = self.repository.list_forms()
            categories = (
                (
                    "factory-depth",
                    self._text("Заводские формы — глубина", "Зауыттық пішіндер — тереңдік", "Factory forms — depth"),
                    [item for item in factory if item.axis_kind is FormAxisKind.DEPTH],
                    False,
                ),
                (
                    "factory-time",
                    self._text("Заводские формы — время", "Зауыттық пішіндер — уақыт", "Factory forms — time"),
                    [item for item in factory if item.axis_kind is FormAxisKind.TIME],
                    False,
                ),
                (
                    "user-depth",
                    self._text("Пользовательские формы — глубина", "Пайдаланушы пішіндері — тереңдік", "User forms — depth"),
                    [item for item in user_forms if item.axis_kind is FormAxisKind.DEPTH],
                    True,
                ),
                (
                    "user-time",
                    self._text("Пользовательские формы — время", "Пайдаланушы пішіндері — уақыт", "User forms — time"),
                    [item for item in user_forms if item.axis_kind is FormAxisKind.TIME],
                    True,
                ),
            )
            selected_item: QTreeWidgetItem | None = None
            first_form_item: QTreeWidgetItem | None = None
            for category_id, title, forms, expanded in categories:
                group = QTreeWidgetItem([f"{title}  ({len(forms)})"])
                group.setData(0, Qt.ItemDataRole.UserRole, None)
                group.setData(0, Qt.ItemDataRole.UserRole + 1, category_id)
                group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                group.setExpanded(expanded)
                font = group.font(0)
                font.setBold(True)
                group.setFont(0, font)
                group.setToolTip(
                    0,
                    self._text(
                        "Нажмите стрелку, чтобы свернуть или развернуть раздел.",
                        "Бөлімді жинау немесе ашу үшін көрсеткіні басыңыз.",
                        "Use the arrow to collapse or expand this section.",
                    ),
                )
                self.tree_widget.addTopLevelItem(group)
                for form in sorted(forms, key=lambda item: item.name.casefold()):
                    binding_count = sum(
                        len(track.bindings)
                        for column in form.columns
                        for track in column.tracks
                    )
                    count_suffix = f"  · {binding_count}" if binding_count else ""
                    prefix = "🔒 " if form.read_only else ""
                    item = QTreeWidgetItem([prefix + form.name + count_suffix])
                    item.setData(0, Qt.ItemDataRole.UserRole, form)
                    item.setToolTip(
                        0,
                        self._text(
                            "Двойной щелчок — открыть на планшете.",
                            "Екі рет басу — планшетте ашу.",
                            "Double-click to open on the tablet.",
                        ),
                    )
                    group.addChild(item)
                    if first_form_item is None:
                        first_form_item = item
                    if selected_id and form.form_id == selected_id:
                        selected_item = item
                        group.setExpanded(True)
            self.tree_widget.expandItem(
                next(
                    (
                        self.tree_widget.topLevelItem(index)
                        for index in range(self.tree_widget.topLevelItemCount())
                        if self.tree_widget.topLevelItem(index).data(
                            0, Qt.ItemDataRole.UserRole + 1
                        )
                        == "user-depth"
                    ),
                    self.tree_widget.topLevelItem(0),
                )
            )
            if selected_item is not None:
                self.tree_widget.setCurrentItem(selected_item)
            elif first_form_item is not None:
                self.tree_widget.setCurrentItem(first_form_item)
        finally:
            self.tree_widget.blockSignals(False)
        self._filter_tree(self.search_input.text())
        self._show_selected(self.tree_widget.currentItem(), None)

    def _filter_tree(self, text: str) -> None:
        query = text.strip().casefold()
        for group_index in range(self.tree_widget.topLevelItemCount()):
            group = self.tree_widget.topLevelItem(group_index)
            visible_children = 0
            for child_index in range(group.childCount()):
                child = group.child(child_index)
                form = child.data(0, Qt.ItemDataRole.UserRole)
                haystack = ""
                if isinstance(form, FormDocument):
                    parameter_names = [
                        binding.display_name
                        for column in form.columns
                        for track in column.tracks
                        for binding in track.bindings
                    ]
                    haystack = " ".join(
                        [form.name, form.description, *parameter_names]
                    ).casefold()
                match = not query or query in haystack
                child.setHidden(not match)
                visible_children += int(match)
            group.setHidden(bool(query) and visible_children == 0)
            if query and visible_children:
                group.setExpanded(True)

    def _current(self) -> FormDocument | None:
        item = self.tree_widget.currentItem()
        value = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        return value if isinstance(value, FormDocument) else None

    def _is_compatible(self, form: FormDocument) -> bool:
        if self.dataset is None:
            return False
        wanted_role = IndexRole.DEPTH if form.axis_kind is FormAxisKind.DEPTH else IndexRole.TIME
        return any(index.role is wanted_role for index in self.dataset.indexes.values())

    def _show_selected(self, current, _previous) -> None:
        """Debounce expensive compatibility resolution during rapid switching.

        Qt emits currentItemChanged synchronously. Building a full applied layout in
        that handler made the dialog appear frozen when the user moved through
        several large forms. Only the latest settled selection is rendered.
        """

        self._pending_selection_revision = self._selection_gate.request()
        self._selection_timer.start()

    def _render_pending_selection(self) -> None:
        revision = self._pending_selection_revision
        if not self._selection_gate.accepts(revision):
            return
        self._render_selected_details()

    def _render_selected_details(self) -> None:
        form = self._current()
        if form is None:
            self.details.clear()
            self.apply_button.setEnabled(False)
            self.print_button.setEnabled(False)
            self.masterlog_sync_button.setEnabled(False)
            return
        tracks = sum(len(column.tracks) for column in form.columns)
        bindings = sum(len(track.bindings) for column in form.columns for track in column.tracks)
        origin = (
            self._text("Заводская", "Зауыттық", "Factory")
            if form.read_only
            else self._text("Пользовательская", "Пайдаланушы", "User")
        )
        axis_name = (
            self._text("Глубина", "Тереңдік", "Depth")
            if form.axis_kind is FormAxisKind.DEPTH
            else self._text("Время", "Уақыт", "Time")
        )
        compatible = self._is_compatible(form)
        self.apply_button.setEnabled(bool(compatible))
        self.print_button.setEnabled(bool(compatible and self.print_form_callback is not None))
        self.masterlog_sync_button.setEnabled(
            bool(
                compatible
                and form.axis_kind is FormAxisKind.DEPTH
                and self.masterlog_sync_callback is not None
            )
        )

        status_lines: list[str] = []
        if self.dataset is None:
            status_lines.append(
                self._text(
                    "Откройте LAS-файл, чтобы шаблоны заполнились реальными кривыми.",
                    "Үлгілер нақты қисықтармен толтырылуы үшін LAS файлын ашыңыз.",
                    "Open a LAS file to populate the templates with actual curves.",
                )
            )
        elif not compatible:
            status_lines.append(
                self._text(
                    "В текущем файле нет подходящей оси для этой формы.",
                    "Ағымдағы файлда бұл пішінге сәйкес ось жоқ.",
                    "The current file has no compatible axis for this form.",
                )
            )
        else:
            try:
                result = self.apply_engine.build_layout(form, self.dataset)
                status_lines.append(
                    self._text(
                        f"Доступно кривых: {result.resolved_count} из {len(result.resolutions)}.",
                        f"Қолжетімді қисықтар: {result.resolved_count} / {len(result.resolutions)}.",
                        f"Available curves: {result.resolved_count} of {len(result.resolutions)}.",
                    )
                )
                if result.missing:
                    missing = ", ".join(item.canonical_parameter_id for item in result.missing)
                    status_lines.append(
                        self._text(
                            f"Не найдены: {missing}",
                            f"Табылмады: {missing}",
                            f"Missing: {missing}",
                        )
                    )
            except (KeyError, RuntimeError, ValueError) as exc:
                status_lines.append(str(exc))

        parameter_lines: list[str] = []
        for column in form.columns:
            for track in column.tracks:
                if not track.bindings:
                    continue
                parameter_lines.append(f"\n{column.title}:")
                for binding in track.bindings:
                    source = binding.source_mnemonic or binding.canonical_parameter_id
                    unit = f" [{binding.unit}]" if binding.unit else ""
                    parameter_lines.append(f"  • {binding.display_name} — {source}{unit}")

        edit_hint = (
            self._text(
                "Для изменения заводского шаблона нажмите «Редактировать»: программа создаст пользовательскую копию.",
                "Зауыттық үлгіні өзгерту үшін «Өңдеу» батырмасын басыңыз: бағдарлама пайдаланушы көшірмесін жасайды.",
                "To change a factory template, click Edit; the application will create a user copy.",
            )
            if form.read_only
            else ""
        )
        details = (
            f"{form.name}\n\n{form.description}\n"
            + (f"\n{edit_hint}\n" if edit_hint else "")
            + "\n"
            f"{self._text('Ось', 'Ось', 'Axis')}: {axis_name}\n"
            f"{self._text('Источник', 'Шығу тегі', 'Origin')}: {origin}\n"
            f"{self._text('Колонки', 'Бағандар', 'Columns')}: {len(form.columns)}\n"
            f"{self._text('Дорожки', 'Жолдар', 'Tracks')}: {tracks}\n"
            f"{self._text('Параметры', 'Параметрлер', 'Parameters')}: {bindings}\n"
            f"{self._text('Печать', 'Басып шығару', 'Print')}: "
            f"{self.print_orientation_combo.currentText()}, "
            f"{self._text('автоподбор ширины', 'енін автотаңдау', 'automatic width fitting') if self.fit_columns_check.isChecked() else self._text('экранные пропорции', 'экран пропорциялары', 'screen proportions')}\n\n"
            + "\n".join(status_lines)
            + "\n".join(parameter_lines)
        )
        self.details.setPlainText(details)

    def _print_layout_changed(self, _value=None) -> None:
        orientation = PrintOrientation(str(self.print_orientation_combo.currentData()))
        self.print_page_settings = PrintPageSettings(
            page_format=PrintPageFormat.A4,
            orientation=orientation,
            custom_width_mm=self.print_page_settings.custom_width_mm,
            custom_height_mm=self.print_page_settings.custom_height_mm,
            fit_form_columns=self.fit_columns_check.isChecked(),
            margin_left_mm=self.print_page_settings.margin_left_mm,
            margin_top_mm=self.print_page_settings.margin_top_mm,
            margin_right_mm=self.print_page_settings.margin_right_mm,
            margin_bottom_mm=self.print_page_settings.margin_bottom_mm,
        )
        if self.print_page_settings_changed is not None:
            self.print_page_settings_changed(self.print_page_settings)
        self._show_selected(self.tree_widget.currentItem(), None)

    def _create(self) -> None:
        name, ok = QInputDialog.getText(
            self, self.windowTitle(), self._text("Название формы", "Пішін атауы", "Form name")
        )
        if not ok or not name.strip():
            return
        depth_label = self._text("Глубина", "Тереңдік", "Depth")
        time_label = self._text("Время", "Уақыт", "Time")
        axis_text, ok = QInputDialog.getItem(
            self,
            self.windowTitle(),
            self._text("Вертикальная ось", "Тік ось", "Vertical axis"),
            [depth_label, time_label],
            editable=False,
        )
        if not ok:
            return
        axis_kind = FormAxisKind.DEPTH if axis_text == depth_label else FormAxisKind.TIME
        form = FormDocument.create(name.strip(), axis_kind)
        self.repository.save(form)
        self.reload(form.form_id)

    def _copy(self) -> None:
        source = self._current()
        if source is None:
            return
        name, ok = QInputDialog.getText(
            self,
            self.windowTitle(),
            self._text("Название копии", "Көшірме атауы", "Copy name"),
            text=f"{source.name} — {self._text('копия', 'көшірме', 'copy')}",
        )
        if not ok or not name.strip():
            return
        copy = source.editable_copy(name=name.strip())
        self.repository.save(copy)
        self.reload(copy.form_id)

    def _edit(self) -> None:
        form = self._current()
        if form is None:
            return
        if form.read_only:
            name, ok = QInputDialog.getText(
                self,
                self.windowTitle(),
                self._text(
                    "Название пользовательской копии",
                    "Пайдаланушы көшірмесінің атауы",
                    "User copy name",
                ),
                text=f"{form.name} — {self._text('копия', 'көшірме', 'copy')}",
            )
            if not ok or not name.strip():
                return
            form = form.editable_copy(name=name.strip())
            self.repository.save(form)
        dialog = FormStructureEditorDialog(
            form,
            self.repository,
            self,
            language=self.language,
            dataset=self.dataset,
            preview_callback=self.preview_callback,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_form is not None:
            self.reload(dialog.saved_form.form_id)

    def _rename(self) -> None:
        form = self._current()
        if form is None or form.read_only:
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._text(
                    "Сначала создайте пользовательскую копию.",
                    "Алдымен пайдаланушы көшірмесін жасаңыз.",
                    "Create a user copy first.",
                ),
            )
            return
        name, ok = QInputDialog.getText(
            self,
            self.windowTitle(),
            self._text("Новое название", "Жаңа атау", "New name"),
            text=form.name,
        )
        if ok and name.strip():
            form.name = name.strip()
            form.validate()
            self.repository.save(form)
            self.reload(form.form_id)

    def _delete(self) -> None:
        form = self._current()
        if form is None or form.read_only:
            return
        if (
            QMessageBox.question(
                self,
                self.windowTitle(),
                self._text(
                    "Удалить выбранную форму?",
                    "Таңдалған пішінді жою керек пе?",
                    "Delete selected form?",
                ),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.repository.delete(form.form_id)
        self.reload()

    def _import_json(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, self.windowTitle(), "", "JSON (*.json)")
        if not filename:
            return
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            form = form_from_dict(payload)
            if form.read_only:
                form = form.editable_copy(name=form.name)
            if any(existing.form_id == form.form_id for existing in self.repository.list_forms()):
                form = form.editable_copy(
                    name=f"{form.name} — {self._text('импорт', 'импорт', 'import')}"
                )
            self.repository.save(form)
            self.reload(form.form_id)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _export_json(self) -> None:
        form = self._current()
        if form is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, self.windowTitle(), f"{form.form_id}.json", "JSON (*.json)"
        )
        if filename:
            Path(filename).write_text(
                json.dumps(form_to_dict(form), ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def _print_selected(self) -> None:
        form = self._current()
        if form is None or not self._is_compatible(form) or self.print_form_callback is None:
            return
        self.print_form_callback(form)

    def _sync_masterlog(self) -> None:
        form = self._current()
        if (
            form is None
            or form.axis_kind is not FormAxisKind.DEPTH
            or self.masterlog_sync_callback is None
        ):
            return
        try:
            linked_form = self.masterlog_sync_callback(form)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        if linked_form is None:
            return
        self.reload(linked_form.form_id)
        QMessageBox.information(
            self,
            self.windowTitle(),
            self._text(
                "Печатный Masterlog синхронизирован с формой. Заголовки, порядок, ширины, шкалы и стили дорожек перенесены в печатный шаблон.",
                "Баспа Masterlog пішінмен синхрондалды. Жол атаулары, реті, ені, шкалалары және стильдері баспа үлгісіне көшірілді.",
                "The printable Masterlog was synchronized with the form. Track captions, order, widths, scales, and styles were transferred to the print template.",
            ),
        )

    def _apply(self) -> None:
        form = self._current()
        if form is None or not self._is_compatible(form):
            return
        self.selected_form = form
        self.accept()
