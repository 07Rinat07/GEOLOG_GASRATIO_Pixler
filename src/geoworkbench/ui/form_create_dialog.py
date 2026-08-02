from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.forms.models import (
    FormAxisKind,
    FormDocument,
    FormPageOrientation,
)
from geoworkbench.forms.naming import clean_form_name, normalized_form_name


class FormCreateDialog(QDialog):
    """Name a new form while keeping the complete library visible.

    ``mode="create"`` is used by Form Library. ``mode="save"`` replaces the
    former tiny ``QInputDialog`` used by the tablet toolbar. In save mode the
    active vertical axis is fixed and an existing editable form may be replaced;
    ready/factory templates remain protected.
    """

    def __init__(
        self,
        forms: Sequence[FormDocument],
        parent=None,
        *,
        language: str = "ru",
        mode: str = "create",
        initial_name: str = "",
        initial_axis_kind: FormAxisKind = FormAxisKind.DEPTH,
        axis_editable: bool = True,
        initial_page_orientation: FormPageOrientation = FormPageOrientation.PORTRAIT,
        page_orientation_editable: bool = True,
    ) -> None:
        super().__init__(parent)
        if mode not in {"create", "save"}:
            raise ValueError("mode должен быть create или save")
        self.forms = tuple(forms)
        self.language = language
        self.mode = mode
        self._name = ""
        self._axis_kind = initial_axis_kind
        self._page_orientation = initial_page_orientation
        self._existing_form: FormDocument | None = None

        self.setWindowTitle(
            self._text(
                "Сохранение пользовательской формы"
                if mode == "save"
                else "Создание формы",
                "Пайдаланушы пішінін сақтау"
                if mode == "save"
                else "Пішін жасау",
                "Save user form" if mode == "save" else "Create form",
            )
        )
        self.setMinimumSize(920, 610)
        self.resize(1120, 720)
        self.setStyleSheet(
            "QDialog { background: #f1f5f9; color: #0f172a; }"
            "QLabel { color: #334155; }"
            "QTreeWidget, QTextEdit, QLineEdit, QComboBox { "
            "background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; "
            "border-radius: 7px; selection-background-color: #dbeafe; "
            "selection-color: #0f172a; }"
            "QTreeWidget::item { color: #0f172a; min-height: 25px; padding: 2px 4px; }"
            "QTreeWidget::item:selected { background: #dbeafe; color: #0f172a; }"
            "QPushButton { min-height: 30px; padding: 4px 12px; "
            "background: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; "
            "border-radius: 6px; }"
            "QPushButton:hover { background: #dbeafe; border-color: #93c5fd; }"
            "QPushButton:disabled { background: #e5e7eb; color: #94a3b8; }"
        )

        root = QVBoxLayout(self)
        intro = QLabel(
            self._text(
                (
                    "Перед сохранением просмотрите все готовые, заводские и "
                    "пользовательские формы. Если указать имя существующей "
                    "пользовательской формы, будет сохранена её новая ревизия. "
                    "Готовые шаблоны перезаписывать нельзя."
                    if mode == "save"
                    else "Перед вводом имени просмотрите все готовые, заводские и "
                    "пользовательские формы. Совпадение имени с существующей "
                    "формой не допускается, включая различия только в регистре "
                    "и повторных пробелах."
                ),
                (
                    "Сақтамас бұрын барлық дайын, зауыттық және пайдаланушы "
                    "пішіндерін қарап шығыңыз. Бар пайдаланушы пішінінің атауын "
                    "енгізсеңіз, оның жаңа ревизиясы сақталады. Дайын үлгілерді "
                    "қайта жазуға болмайды."
                    if mode == "save"
                    else "Атау енгізер алдында барлық дайын, зауыттық және "
                    "пайдаланушы пішіндерін қарап шығыңыз. Тек әріп регистрі мен "
                    "қайталанған бос орындарымен ерекшеленетін атаулар да "
                    "қайталану болып саналады."
                ),
                (
                    "Review all ready, factory and user forms before saving. "
                    "Entering the name of an existing user form saves a new "
                    "revision. Ready templates cannot be overwritten."
                    if mode == "save"
                    else "Review all ready, factory and user forms before entering "
                    "a name. Names that differ only by case or repeated spacing "
                    "are also treated as duplicates."
                ),
            )
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        library_panel = QWidget(splitter)
        library_layout = QVBoxLayout(library_panel)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_heading = QLabel(
            self._text(
                "Все формы и шаблоны",
                "Барлық пішіндер мен үлгілер",
                "All forms and templates",
            )
        )
        font = library_heading.font()
        font.setBold(True)
        library_heading.setFont(font)
        library_layout.addWidget(library_heading)

        self.search_input = QLineEdit(library_panel)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(
            self._text(
                "Поиск по названию, описанию, колонкам и параметрам…",
                "Атауы, сипаттамасы, бағандары және параметрлері бойынша іздеу…",
                "Search names, descriptions, columns and parameters…",
            )
        )
        self.search_input.textChanged.connect(self._filter_tree)
        library_layout.addWidget(self.search_input)

        self.tree = QTreeWidget(library_panel)
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(
            [
                self._text("Название", "Атауы", "Name"),
                self._text("Ось", "Ось", "Axis"),
                self._text("Тип", "Түрі", "Type"),
                self._text("Состав", "Құрамы", "Structure"),
            ]
        )
        self.tree.setRootIsDecorated(True)
        self.tree.currentItemChanged.connect(self._show_details)
        self.tree.itemDoubleClicked.connect(self._use_selected_name)
        library_layout.addWidget(self.tree, 1)
        splitter.addWidget(library_panel)

        details_panel = QWidget(splitter)
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_heading = QLabel(
            self._text(
                "Детали выбранной формы",
                "Таңдалған пішін мәліметтері",
                "Selected form details",
            )
        )
        details_font = details_heading.font()
        details_font.setBold(True)
        details_heading.setFont(details_font)
        details_layout.addWidget(details_heading)
        self.details = QTextEdit(details_panel)
        self.details.setReadOnly(True)
        details_layout.addWidget(self.details, 1)
        splitter.addWidget(details_panel)
        splitter.setSizes([650, 450])

        input_box = QWidget(self)
        input_layout = QFormLayout(input_box)
        input_layout.setContentsMargins(0, 8, 0, 0)
        self.name_input = QLineEdit(input_box)
        self.name_input.setObjectName("form-name-input")
        self.name_input.setClearButtonEnabled(True)
        self.name_input.setPlaceholderText(
            self._text(
                "Например: Газовый каротаж — скважина 12",
                "Мысалы: Газ каротажы — 12-ұңғыма",
                "For example: Gas logging — well 12",
            )
        )
        self.name_input.textChanged.connect(self._validate)
        input_layout.addRow(
            self._text(
                "Имя сохраняемой формы:" if mode == "save" else "Название новой формы:",
                "Сақталатын пішін атауы:" if mode == "save" else "Жаңа пішін атауы:",
                "Saved form name:" if mode == "save" else "New form name:",
            ),
            self.name_input,
        )

        self.axis_combo = QComboBox(input_box)
        self.axis_combo.addItem(
            self._text("Глубина", "Тереңдік", "Depth"),
            FormAxisKind.DEPTH.value,
        )
        self.axis_combo.addItem(
            self._text("Время", "Уақыт", "Time"),
            FormAxisKind.TIME.value,
        )
        target_index = self.axis_combo.findData(initial_axis_kind.value)
        self.axis_combo.setCurrentIndex(max(0, target_index))
        self.axis_combo.setEnabled(axis_editable)
        self.axis_combo.currentIndexChanged.connect(self._validate)
        input_layout.addRow(
            self._text("Вертикальная ось:", "Тік ось:", "Vertical axis:"),
            self.axis_combo,
        )

        self.page_orientation_combo = QComboBox(input_box)
        self.page_orientation_combo.setObjectName("form-page-orientation")
        self.page_orientation_combo.addItem(
            self._text("A4 — книжная", "A4 — кітаптық", "A4 — portrait"),
            FormPageOrientation.PORTRAIT.value,
        )
        self.page_orientation_combo.addItem(
            self._text("A4 — альбомная", "A4 — альбомдық", "A4 — landscape"),
            FormPageOrientation.LANDSCAPE.value,
        )
        orientation_index = self.page_orientation_combo.findData(
            initial_page_orientation.value
        )
        self.page_orientation_combo.setCurrentIndex(max(0, orientation_index))
        self.page_orientation_combo.setEnabled(page_orientation_editable)
        self.page_orientation_combo.currentIndexChanged.connect(self._validate)
        self.page_orientation_combo.setToolTip(
            self._text(
                "Целевая ширина конструктора. Редактор предупредит, если колонки не помещаются, и предложит автоподбор.",
                "Конструктордың мақсатты ені. Бағандар сыймаса, редактор ескертіп, автотаңдауды ұсынады.",
                "Target constructor width. The editor warns when columns overflow and offers automatic fitting.",
            )
        )
        input_layout.addRow(
            self._text("Формат формы:", "Пішін форматы:", "Form format:"),
            self.page_orientation_combo,
        )
        root.addWidget(input_box)

        self.validation_label = QLabel(self)
        self.validation_label.setWordWrap(True)
        self.validation_label.setMinimumHeight(24)
        root.addWidget(self.validation_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        self.create_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.create_button.setObjectName("form-confirm-button")
        self.create_button.setText(
            self._text(
                "Сохранить" if mode == "save" else "Создать",
                "Сақтау" if mode == "save" else "Жасау",
                "Save" if mode == "save" else "Create",
            )
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._text("Отмена", "Бас тарту", "Cancel")
        )
        self.button_box.accepted.connect(self._accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

        self._populate_tree()
        self.name_input.setText(initial_name)
        self._validate()
        self.name_input.selectAll()
        self.name_input.setFocus()

    @property
    def form_name(self) -> str:
        return self._name

    @property
    def axis_kind(self) -> FormAxisKind:
        return self._axis_kind

    @property
    def page_orientation(self) -> FormPageOrientation:
        return self._page_orientation

    @property
    def existing_form(self) -> FormDocument | None:
        """Editable form selected for replacement in save mode."""

        return self._existing_form

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    @staticmethod
    def _is_factory(form: FormDocument) -> bool:
        return form.read_only and form.form_id.startswith("factory-")

    def _type_text(self, form: FormDocument) -> str:
        if self._is_factory(form):
            return self._text("Заводская", "Зауыттық", "Factory")
        if form.read_only:
            return self._text("Готовая", "Дайын", "Ready")
        return self._text("Пользовательская", "Пайдаланушы", "User")

    def _populate_tree(self) -> None:
        self.tree.clear()
        categories = (
            (
                self._text("Готовые формы", "Дайын пішіндер", "Ready forms"),
                [form for form in self.forms if form.read_only and not self._is_factory(form)],
            ),
            (
                self._text("Заводские формы", "Зауыттық пішіндер", "Factory forms"),
                [form for form in self.forms if self._is_factory(form)],
            ),
            (
                self._text("Пользовательские формы", "Пайдаланушы пішіндері", "User forms"),
                [form for form in self.forms if not form.read_only],
            ),
        )
        first_item: QTreeWidgetItem | None = None
        for title, forms in categories:
            group = QTreeWidgetItem([f"{title} ({len(forms)})", "", "", ""])
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            group.setExpanded(True)
            group_font = group.font(0)
            group_font.setBold(True)
            group.setFont(0, group_font)
            self.tree.addTopLevelItem(group)
            for form in sorted(forms, key=lambda item: item.name.casefold()):
                axis = (
                    self._text("Глубина", "Тереңдік", "Depth")
                    if form.axis_kind is FormAxisKind.DEPTH
                    else self._text("Время", "Уақыт", "Time")
                )
                tracks = sum(len(column.tracks) for column in form.columns)
                item = QTreeWidgetItem(
                    [
                        form.name,
                        axis,
                        self._type_text(form),
                        self._text(
                            f"{len(form.columns)} кол. / {tracks} дор.",
                            f"{len(form.columns)} бағ. / {tracks} жол",
                            f"{len(form.columns)} col. / {tracks} tracks",
                        ),
                    ]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, form)
                group.addChild(item)
                if first_item is None:
                    first_item = item
        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)
        if first_item is not None:
            self.tree.setCurrentItem(first_item)

    def _filter_tree(self, text: str) -> None:
        query = clean_form_name(text).casefold()
        for group_index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(group_index)
            if group is None:
                continue
            visible_count = 0
            for child_index in range(group.childCount()):
                item = group.child(child_index)
                form = item.data(0, Qt.ItemDataRole.UserRole) if item else None
                haystack = ""
                if isinstance(form, FormDocument):
                    column_titles = [column.title for column in form.columns]
                    parameter_names = [
                        binding.display_name
                        for column in form.columns
                        for track in column.tracks
                        for binding in track.bindings
                    ]
                    haystack = " ".join(
                        [form.name, form.description, *column_titles, *parameter_names]
                    ).casefold()
                visible = not query or query in haystack
                item.setHidden(not visible)
                visible_count += int(visible)
            group.setHidden(bool(query) and visible_count == 0)
            if query and visible_count:
                group.setExpanded(True)

    def _show_details(self, current: QTreeWidgetItem | None, _previous) -> None:
        form = current.data(0, Qt.ItemDataRole.UserRole) if current else None
        if not isinstance(form, FormDocument):
            self.details.clear()
            return
        axis = (
            self._text("Глубина", "Тереңдік", "Depth")
            if form.axis_kind is FormAxisKind.DEPTH
            else self._text("Время", "Уақыт", "Time")
        )
        tracks = sum(len(column.tracks) for column in form.columns)
        bindings = sum(
            len(track.bindings) for column in form.columns for track in column.tracks
        )
        column_lines = [
            f"  • {column.title} — {column.width} px"
            for column in form.columns
            if column.visible
        ]
        parameter_lines = [
            f"  • {binding.display_name} "
            f"({binding.source_mnemonic or binding.canonical_parameter_id})"
            for column in form.columns
            for track in column.tracks
            for binding in track.bindings
        ]
        text = (
            f"{form.name}\n\n"
            f"{form.description or self._text('Описание не задано.', 'Сипаттама берілмеген.', 'No description provided.')}\n\n"
            f"{self._text('Ось', 'Ось', 'Axis')}: {axis}\n"
            f"{self._text('Тип', 'Түрі', 'Type')}: {self._type_text(form)}\n"
            f"{self._text('Ревизия', 'Ревизия', 'Revision')}: {form.revision}\n"
            f"{self._text('Колонки', 'Бағандар', 'Columns')}: {len(form.columns)}\n"
            f"{self._text('Дорожки', 'Жолдар', 'Tracks')}: {tracks}\n"
            f"{self._text('Параметры', 'Параметрлер', 'Parameters')}: {bindings}\n\n"
            f"{self._text('Видимые колонки:', 'Көрінетін бағандар:', 'Visible columns:')}\n"
            + ("\n".join(column_lines) if column_lines else "  —")
        )
        if parameter_lines:
            text += (
                "\n\n"
                + self._text("Параметры:", "Параметрлер:", "Parameters:")
                + "\n"
                + "\n".join(parameter_lines)
            )
        self.details.setPlainText(text)

    def _use_selected_name(self, item: QTreeWidgetItem, _column: int) -> None:
        form = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(form, FormDocument) and self.mode == "save" and not form.read_only:
            self.name_input.setText(form.name)

    def _matching_forms(self, name: str) -> tuple[FormDocument, ...]:
        key = normalized_form_name(name)
        return tuple(form for form in self.forms if normalized_form_name(form.name) == key)

    def _validate(self, _value=None) -> None:
        name = clean_form_name(self.name_input.text())
        self._existing_form = None
        if not name:
            self.validation_label.setStyleSheet("color:#b45309;")
            self.validation_label.setText(
                self._text(
                    "Введите понятное название формы.",
                    "Пішінге түсінікті атау енгізіңіз.",
                    "Enter a clear form name.",
                )
            )
            self.create_button.setEnabled(False)
            return

        matches = self._matching_forms(name)
        protected = tuple(form for form in matches if form.read_only)
        editable = tuple(form for form in matches if not form.read_only)
        if protected:
            self.validation_label.setStyleSheet("color:#b91c1c; font-weight:600;")
            self.validation_label.setText(
                self._text(
                    f"Имя занято защищённым шаблоном «{protected[0].name}». Выберите другое имя.",
                    f"Атау «{protected[0].name}» қорғалған үлгісімен бос емес. Басқа атау таңдаңыз.",
                    f"The protected template “{protected[0].name}” already uses this name. Choose another name.",
                )
            )
            self.create_button.setEnabled(False)
            return
        if editable:
            if self.mode == "create":
                self.validation_label.setStyleSheet("color:#b91c1c; font-weight:600;")
                self.validation_label.setText(
                    self._text(
                        f"Пользовательская форма «{editable[0].name}» уже существует. Выберите другое имя.",
                        f"«{editable[0].name}» пайдаланушы пішіні бұрыннан бар. Басқа атау таңдаңыз.",
                        f"The user form “{editable[0].name}” already exists. Choose another name.",
                    )
                )
                self.create_button.setEnabled(False)
                return
            self._existing_form = editable[0]
            self.validation_label.setStyleSheet("color:#92400e; font-weight:600;")
            self.validation_label.setText(
                self._text(
                    f"Будет заменена пользовательская форма «{editable[0].name}» и создана новая ревизия.",
                    f"«{editable[0].name}» пайдаланушы пішіні ауыстырылып, жаңа ревизия жасалады.",
                    f"User form “{editable[0].name}” will be replaced with a new revision.",
                )
            )
            self.create_button.setEnabled(True)
            return

        self.validation_label.setStyleSheet("color:#166534;")
        self.validation_label.setText(
            self._text(
                "Название свободно. Форма будет сохранена в пользовательской библиотеке.",
                "Атау бос. Пішін пайдаланушы кітапханасына сақталады.",
                "The name is available. The form will be saved to the user library.",
            )
        )
        self.create_button.setEnabled(True)

    def _accept(self) -> None:
        self._validate()
        if not self.create_button.isEnabled():
            return
        self._name = clean_form_name(self.name_input.text())
        data = self.axis_combo.currentData()
        try:
            self._axis_kind = FormAxisKind(str(data))
        except ValueError:
            self._axis_kind = FormAxisKind.DEPTH
        orientation = self.page_orientation_combo.currentData()
        try:
            self._page_orientation = FormPageOrientation(str(orientation))
        except ValueError:
            self._page_orientation = FormPageOrientation.PORTRAIT
        self.accept()
