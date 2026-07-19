from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from geoworkbench.domain.models import Dataset
from geoworkbench.forms.models import FormAxisKind, FormDocument, FormTemplateOrigin
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.templates import factory_templates
from geoworkbench.ui.form_structure_editor_dialog import FormStructureEditorDialog


class FormManagerDialog(QDialog):
    def __init__(
        self,
        repository: FormRepository,
        parent=None,
        *,
        language: str = "ru",
        dataset: Dataset | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.dataset = dataset
        self.language = language
        self.selected_form: FormDocument | None = None
        self.setWindowTitle(self._text("Менеджер форм", "Пішіндер менеджері", "Form manager"))
        self.resize(840, 560)

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        self.search = QInputDialog  # keep static type checkers from confusing Qt overloads
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._show_selected)
        left.addWidget(QLabel(self._text("Формы", "Пішіндер", "Forms")))
        left.addWidget(self.list_widget, 1)
        root.addLayout(left, 2)

        right = QVBoxLayout()
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        right.addWidget(self.details, 1)

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

        apply_button = QPushButton(self._text("Применить к планшету", "Планшетке қолдану", "Apply to tablet"))
        apply_button.clicked.connect(self._apply)
        right.addWidget(apply_button)
        close_button = QPushButton(self._text("Закрыть", "Жабу", "Close"))
        close_button.clicked.connect(self.reject)
        right.addWidget(close_button)
        root.addLayout(right, 3)
        self.reload()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def reload(self, selected_id: str | None = None) -> None:
        self.list_widget.clear()
        forms = list(factory_templates().values()) + self.repository.list_forms()
        forms.sort(key=lambda form: (form.origin is FormTemplateOrigin.USER, form.name.casefold()))
        for form in forms:
            prefix = "🔒 " if form.read_only else ""
            item = QListWidgetItem(prefix + form.name)
            item.setData(Qt.ItemDataRole.UserRole, form)
            self.list_widget.addItem(item)
            if selected_id and form.form_id == selected_id:
                self.list_widget.setCurrentItem(item)
        if self.list_widget.currentItem() is None and self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _current(self) -> FormDocument | None:
        item = self.list_widget.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value if isinstance(value, FormDocument) else None

    def _show_selected(self, current, _previous) -> None:
        form = self._current()
        if form is None:
            self.details.clear()
            return
        tracks = sum(len(column.tracks) for column in form.columns)
        bindings = sum(len(track.bindings) for column in form.columns for track in column.tracks)
        origin = self._text("Заводская", "Зауыттық", "Factory") if form.read_only else self._text("Пользовательская", "Пайдаланушы", "User")
        self.details.setPlainText(
            f"{form.name}\n\n{form.description}\n\n"
            f"{self._text('Тип', 'Түрі', 'Type')}: {form.axis_kind.value}\n"
            f"{self._text('Источник', 'Шығу тегі', 'Origin')}: {origin}\n"
            f"{self._text('Колонки', 'Бағандар', 'Columns')}: {len(form.columns)}\n"
            f"{self._text('Дорожки', 'Жолдар', 'Tracks')}: {tracks}\n"
            f"{self._text('Параметры', 'Параметрлер', 'Parameters')}: {bindings}"
        )

    def _create(self) -> None:
        name, ok = QInputDialog.getText(self, self.windowTitle(), self._text("Название формы", "Пішін атауы", "Form name"))
        if not ok or not name.strip():
            return
        axis_text, ok = QInputDialog.getItem(
            self,
            self.windowTitle(),
            self._text("Вертикальная ось", "Тік ось", "Vertical axis"),
            ["depth", "time"],
            editable=False,
        )
        if not ok:
            return
        form = FormDocument.create(name.strip(), FormAxisKind(axis_text))
        self.repository.save(form)
        self.reload(form.form_id)

    def _copy(self) -> None:
        source = self._current()
        if source is None:
            return
        name, ok = QInputDialog.getText(self, self.windowTitle(), self._text("Название копии", "Көшірме атауы", "Copy name"), text=f"{source.name} — copy")
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
                text=f"{form.name} — copy",
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
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_form is not None:
            self.reload(dialog.saved_form.form_id)

    def _rename(self) -> None:
        form = self._current()
        if form is None or form.read_only:
            QMessageBox.information(self, self.windowTitle(), self._text("Сначала создайте пользовательскую копию.", "Алдымен пайдаланушы көшірмесін жасаңыз.", "Create a user copy first."))
            return
        name, ok = QInputDialog.getText(self, self.windowTitle(), self._text("Новое название", "Жаңа атау", "New name"), text=form.name)
        if ok and name.strip():
            form.name = name.strip()
            form.validate()
            self.repository.save(form)
            self.reload(form.form_id)

    def _delete(self) -> None:
        form = self._current()
        if form is None or form.read_only:
            return
        if QMessageBox.question(self, self.windowTitle(), self._text("Удалить выбранную форму?", "Таңдалған пішінді жою керек пе?", "Delete selected form?")) != QMessageBox.StandardButton.Yes:
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
                form = form.editable_copy(name=f"{form.name} — import")
            self.repository.save(form)
            self.reload(form.form_id)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _export_json(self) -> None:
        form = self._current()
        if form is None:
            return
        filename, _ = QFileDialog.getSaveFileName(self, self.windowTitle(), f"{form.form_id}.json", "JSON (*.json)")
        if filename:
            Path(filename).write_text(json.dumps(form_to_dict(form), ensure_ascii=False, indent=2), encoding="utf-8")

    def _apply(self) -> None:
        self.selected_form = self._current()
        if self.selected_form is not None:
            self.accept()
