from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.naming import clean_form_name, duplicate_form_names


class FormCreateDialog(QDialog):
    """Create a form while keeping the complete form library visible.

    The old workflow asked for a name in a small modal input and hid the library.
    This dialog keeps factory and user names, axis types and structural details in
    view so a user can choose a meaningful, non-duplicating name before creating
    the new form.
    """

    def __init__(
        self,
        forms: Sequence[FormDocument],
        parent=None,
        *,
        language: str = "ru",
    ) -> None:
        super().__init__(parent)
        self.forms = tuple(forms)
        self.language = language
        self._name = ""
        self._axis_kind = FormAxisKind.DEPTH

        self.setWindowTitle(
            self._text("Создание формы", "Пішін жасау", "Create form")
        )
        self.setMinimumSize(900, 590)
        self.resize(1080, 680)
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
                "Перед вводом имени просмотрите существующие формы. Точное совпадение "
                "названия не допускается; различия только в регистре и пробелах также "
                "считаются совпадением.",
                "Атау енгізер алдында бар пішіндерді қарап шығыңыз. Атаудың дәл "
                "қайталануына жол берілмейді; тек әріп регистрі мен бос орындардағы "
                "айырмашылық та қайталану болып саналады.",
                "Review the existing forms before entering a name. Exact duplicate "
                "names are not allowed; differences in letter case or spacing still "
                "count as duplicates.",
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
                "Существующие формы и шаблоны",
                "Бар пішіндер мен үлгілер",
                "Existing forms and templates",
            )
        )
        font = library_heading.font()
        font.setBold(True)
        library_heading.setFont(font)
        library_layout.addWidget(library_heading)

        self.search_input = QLineEdit(library_panel)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(
            self._text("Поиск по названию и описанию…", "Атауы мен сипаттамасы бойынша іздеу…", "Search name and description…")
        )
        self.search_input.textChanged.connect(self._filter_tree)
        library_layout.addWidget(self.search_input)

        self.tree = QTreeWidget(library_panel)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(
            [
                self._text("Название", "Атауы", "Name"),
                self._text("Ось", "Ось", "Axis"),
                self._text("Источник", "Шығу тегі", "Origin"),
            ]
        )
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.currentItemChanged.connect(self._show_details)
        library_layout.addWidget(self.tree, 1)
        splitter.addWidget(library_panel)

        details_panel = QWidget(splitter)
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_heading = QLabel(
            self._text("Детали выбранной формы", "Таңдалған пішін мәліметтері", "Selected form details")
        )
        details_font = details_heading.font()
        details_font.setBold(True)
        details_heading.setFont(details_font)
        details_layout.addWidget(details_heading)
        self.details = QTextEdit(details_panel)
        self.details.setReadOnly(True)
        details_layout.addWidget(self.details, 1)
        splitter.addWidget(details_panel)
        splitter.setSizes([570, 430])

        input_box = QWidget(self)
        input_layout = QFormLayout(input_box)
        input_layout.setContentsMargins(0, 8, 0, 0)
        self.name_input = QLineEdit(input_box)
        self.name_input.setClearButtonEnabled(True)
        self.name_input.setPlaceholderText(
            self._text(
                "Например: Газовый каротаж — рабочая форма",
                "Мысалы: Газ каротажы — жұмыс пішіні",
                "For example: Gas logging — working form",
            )
        )
        self.name_input.textChanged.connect(self._validate)
        input_layout.addRow(
            self._text("Название новой формы:", "Жаңа пішін атауы:", "New form name:"),
            self.name_input,
        )

        self.axis_combo = QComboBox(input_box)
        self.axis_combo.addItem(self._text("Глубина", "Тереңдік", "Depth"), FormAxisKind.DEPTH)
        self.axis_combo.addItem(self._text("Время", "Уақыт", "Time"), FormAxisKind.TIME)
        self.axis_combo.currentIndexChanged.connect(self._validate)
        input_layout.addRow(
            self._text("Вертикальная ось:", "Тік ось:", "Vertical axis:"),
            self.axis_combo,
        )
        root.addWidget(input_box)

        self.validation_label = QLabel(self)
        self.validation_label.setWordWrap(True)
        self.validation_label.setMinimumHeight(22)
        root.addWidget(self.validation_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        self.create_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.create_button.setText(self._text("Создать", "Жасау", "Create"))
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._text("Отмена", "Бас тарту", "Cancel")
        )
        self.button_box.accepted.connect(self._accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

        self._populate_tree()
        self._validate()
        self.name_input.setFocus()

    @property
    def form_name(self) -> str:
        return self._name

    @property
    def axis_kind(self) -> FormAxisKind:
        return self._axis_kind

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def _populate_tree(self) -> None:
        self.tree.clear()
        categories = (
            (
                self._text("Заводские формы", "Зауыттық пішіндер", "Factory forms"),
                [form for form in self.forms if form.read_only],
            ),
            (
                self._text("Пользовательские формы", "Пайдаланушы пішіндері", "User forms"),
                [form for form in self.forms if not form.read_only],
            ),
        )
        first_item: QTreeWidgetItem | None = None
        for title, forms in categories:
            group = QTreeWidgetItem([f"{title} ({len(forms)})", "", ""])
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
                origin = (
                    self._text("Заводская", "Зауыттық", "Factory")
                    if form.read_only
                    else self._text("Пользовательская", "Пайдаланушы", "User")
                )
                item = QTreeWidgetItem([form.name, axis, origin])
                item.setData(0, Qt.ItemDataRole.UserRole, form)
                group.addChild(item)
                if first_item is None:
                    first_item = item
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.tree.resizeColumnToContents(2)
        if first_item is not None:
            self.tree.setCurrentItem(first_item)

    def _filter_tree(self, text: str) -> None:
        query = text.strip().casefold()
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
        origin = (
            self._text("Заводская", "Зауыттық", "Factory")
            if form.read_only
            else self._text("Пользовательская", "Пайдаланушы", "User")
        )
        tracks = sum(len(column.tracks) for column in form.columns)
        bindings = sum(
            len(track.bindings)
            for column in form.columns
            for track in column.tracks
        )
        column_lines = [
            f"  • {column.title} — {column.width} px"
            for column in form.columns
            if column.visible
        ]
        parameter_lines = [
            f"  • {binding.display_name} ({binding.source_mnemonic or binding.canonical_parameter_id})"
            for column in form.columns
            for track in column.tracks
            for binding in track.bindings
        ]
        text = (
            f"{form.name}\n\n"
            f"{form.description or self._text('Описание не задано.', 'Сипаттама берілмеген.', 'No description provided.')}\n\n"
            f"{self._text('Ось', 'Ось', 'Axis')}: {axis}\n"
            f"{self._text('Источник', 'Шығу тегі', 'Origin')}: {origin}\n"
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

    def _validate(self, _value=None) -> None:
        name = clean_form_name(self.name_input.text())
        duplicates = duplicate_form_names(name, self.forms)
        if not name:
            self.validation_label.setStyleSheet("color:#b45309;")
            self.validation_label.setText(
                self._text(
                    "Введите понятное название новой формы.",
                    "Жаңа пішінге түсінікті атау енгізіңіз.",
                    "Enter a clear name for the new form.",
                )
            )
            self.create_button.setEnabled(False)
            return
        if duplicates:
            self.validation_label.setStyleSheet("color:#b91c1c; font-weight:600;")
            self.validation_label.setText(
                self._text(
                    f"Форма с таким названием уже существует: {', '.join(duplicates)}. Выберите другое название.",
                    f"Мұндай атауы бар пішін бұрыннан бар: {', '.join(duplicates)}. Басқа атау таңдаңыз.",
                    f"A form with this name already exists: {', '.join(duplicates)}. Choose another name.",
                )
            )
            self.create_button.setEnabled(False)
            return
        self.validation_label.setStyleSheet("color:#166534;")
        self.validation_label.setText(
            self._text(
                "Название свободно. Новая форма будет добавлена в пользовательскую библиотеку.",
                "Атау бос. Жаңа пішін пайдаланушы кітапханасына қосылады.",
                "The name is available. The new form will be added to the user library.",
            )
        )
        self.create_button.setEnabled(True)

    def _accept(self) -> None:
        self._validate()
        if not self.create_button.isEnabled():
            return
        self._name = clean_form_name(self.name_input.text())
        data = self.axis_combo.currentData()
        self._axis_kind = data if isinstance(data, FormAxisKind) else FormAxisKind.DEPTH
        self.accept()
