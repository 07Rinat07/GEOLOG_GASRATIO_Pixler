from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from geoworkbench.forms.codec import form_from_dict, form_to_dict
from geoworkbench.domain.models import Dataset, IndexRole
from geoworkbench.forms.models import FormAxisKind, FormDocument, FormTemplateOrigin
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.apply import FormApplyEngine
from geoworkbench.forms.materialize import materialized_factory_templates
from geoworkbench.forms.templates import factory_templates
from geoworkbench.forms.preview import PreviewCallback
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.ui.form_structure_editor_dialog import FormStructureEditorDialog


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
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.dataset = dataset
        self.language = language
        self.preview_callback = preview_callback
        self.print_page_settings = print_page_settings or PrintPageSettings()
        self.print_page_settings_changed = print_page_settings_changed
        self.print_form_callback = print_form_callback
        self.apply_engine = FormApplyEngine()
        self.selected_form: FormDocument | None = None
        self.setWindowTitle(self._text("Менеджер форм", "Пішіндер менеджері", "Form manager"))
        self.resize(840, 560)

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        self.search = QInputDialog  # keep static type checkers from confusing Qt overloads
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._show_selected)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._apply())
        left.addWidget(QLabel(self._text("Формы", "Пішіндер", "Forms")))
        left.addWidget(self.list_widget, 1)
        root.addLayout(left, 2)

        right = QVBoxLayout()
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        right.addWidget(self.details, 1)

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
        print_row.addWidget(self.print_orientation_combo, 1)
        self.fit_columns_check = QCheckBox(
            self._text("Автоподбор колонок", "Бағандарды автотаңдау", "Auto-fit columns")
        )
        self.fit_columns_check.setChecked(self.print_page_settings.fit_form_columns)
        self.fit_columns_check.toggled.connect(self._print_layout_changed)
        print_row.addWidget(self.fit_columns_check)
        right.addLayout(print_row)
        self.print_layout_hint = QLabel(
            self._text(
                "При печати все видимые колонки формы размещаются по ширине листа без горизонтального обрезания.",
                "Басып шығару кезінде пішіннің барлық көрінетін бағандары көлденең қиылмай парақ еніне орналастырылады.",
                "All visible form columns are placed across the sheet width without horizontal clipping.",
            )
        )
        self.print_layout_hint.setWordWrap(True)
        right.addWidget(self.print_layout_hint)

        row1 = QHBoxLayout()
        for caption, callback in (
            (self._text("Создать", "Жасау", "Create"), self._create),
            (self._text("Копировать", "Көшіру", "Copy"), self._copy),
            (self._text("Редактировать", "Өңдеу", "Edit"), self._edit),
            (self._text("Переименовать", "Атын өзгерту", "Rename"), self._rename),
            (self._text("Удалить", "Жою", "Delete"), self._delete),
        ):
            button = QPushButton(caption)
            button.clicked.connect(callback)
            row1.addWidget(button)
        right.addLayout(row1)

        row2 = QHBoxLayout()
        for caption, callback in (
            (self._text("Импорт JSON", "JSON импорттау", "Import JSON"), self._import_json),
            (self._text("Экспорт JSON", "JSON экспорттау", "Export JSON"), self._export_json),
        ):
            button = QPushButton(caption)
            button.clicked.connect(callback)
            row2.addWidget(button)
        right.addLayout(row2)

        open_row = QHBoxLayout()
        self.apply_button = QPushButton(
            self._text("Открыть на планшете", "Планшетте ашу", "Open on tablet")
        )
        self.apply_button.clicked.connect(self._apply)
        open_row.addWidget(self.apply_button, 1)
        self.print_button = QPushButton(
            self._text("Печать / экспорт", "Басып шығару / экспорт", "Print / export")
        )
        self.print_button.clicked.connect(self._print_selected)
        self.print_button.setEnabled(self.print_form_callback is not None)
        open_row.addWidget(self.print_button, 1)
        right.addLayout(open_row)
        close_button = QPushButton(self._text("Закрыть", "Жабу", "Close"))
        close_button.clicked.connect(self.reject)
        right.addWidget(close_button)
        root.addLayout(right, 3)
        self.reload()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def reload(self, selected_id: str | None = None) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        try:
            try:
                factory = list(materialized_factory_templates(self.dataset, self.language).values())
            except (KeyError, RuntimeError, ValueError):
                # Keep the manager available even when one legacy curve carries
                # unusable metadata. The raw factory forms remain selectable;
                # applying them will show a localized diagnostic instead of
                # terminating the dialog.
                factory = list(factory_templates(self.language).values())
            forms = factory + self.repository.list_forms()
            forms.sort(
                key=lambda form: (
                    form.origin is FormTemplateOrigin.USER,
                    form.name.casefold(),
                )
            )
            selected_item: QListWidgetItem | None = None
            for form in forms:
                prefix = "🔒 " if form.read_only else ""
                binding_count = sum(
                    len(track.bindings) for column in form.columns for track in column.tracks
                )
                count_suffix = f"  · {binding_count}" if binding_count else ""
                item = QListWidgetItem(prefix + form.name + count_suffix)
                item.setData(Qt.ItemDataRole.UserRole, form)
                self.list_widget.addItem(item)
                if selected_id and form.form_id == selected_id:
                    selected_item = item
            if selected_item is not None:
                self.list_widget.setCurrentItem(selected_item)
            elif self.list_widget.count():
                self.list_widget.setCurrentRow(0)
        finally:
            self.list_widget.blockSignals(False)
        self._show_selected(self.list_widget.currentItem(), None)

    def _current(self) -> FormDocument | None:
        item = self.list_widget.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value if isinstance(value, FormDocument) else None

    def _is_compatible(self, form: FormDocument) -> bool:
        if self.dataset is None:
            return False
        wanted_role = IndexRole.DEPTH if form.axis_kind is FormAxisKind.DEPTH else IndexRole.TIME
        return any(index.role is wanted_role for index in self.dataset.indexes.values())

    def _show_selected(self, current, _previous) -> None:
        form = self._current()
        if form is None:
            self.details.clear()
            self.apply_button.setEnabled(False)
            self.print_button.setEnabled(False)
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
        self._show_selected(self.list_widget.currentItem(), None)

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

    def _apply(self) -> None:
        form = self._current()
        if form is None or not self._is_compatible(form):
            return
        self.selected_form = form
        self.accept()
