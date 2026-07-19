from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.forms.draft import DraftFormController
from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.preview import FormPreviewController, PreviewCallback
from geoworkbench.forms.models import FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.domain.models import Dataset
from geoworkbench.tablet.models import TrackKind
from geoworkbench.ui.track_content_editor_dialog import TrackContentEditorDialog

_ITEM_KIND_ROLE = Qt.ItemDataRole.UserRole
_ITEM_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class _FormPreview(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._form: FormDocument | None = None
        self._selected_id: str | None = None
        self.setMinimumHeight(150)

    def set_form(self, form: FormDocument, selected_id: str | None = None) -> None:
        self._form = form
        self._selected_id = selected_id
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f7f8fa"))
        form = self._form
        if form is None or not form.columns:
            painter.setPen(QColor("#596273"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
            return
        margin = 10
        available = max(1, self.width() - margin * 2)
        total_width = max(1, sum(column.width for column in form.columns if column.visible))
        x = margin
        for column in form.columns:
            if not column.visible:
                continue
            width = max(34, round(available * column.width / total_width))
            rect = self.rect().adjusted(x, margin, x + width - self.width(), -margin)
            selected = self._selected_id == column.column_id
            painter.fillRect(rect, QColor("#dbeafe") if selected else QColor("#ffffff"))
            painter.setPen(QPen(QColor("#2563eb") if selected else QColor("#9aa4b2"), 2 if selected else 1))
            painter.drawRect(rect)
            header = rect.adjusted(4, 3, -4, -rect.height() + 25)
            painter.setPen(QColor("#111827"))
            painter.drawText(header, Qt.AlignmentFlag.AlignCenter, column.title)
            if column.tracks:
                track_height = max(18, (rect.height() - 32) // len(column.tracks))
                top = rect.top() + 28
                for track in column.tracks:
                    track_rect = rect.adjusted(4, top - rect.top(), -4, top + track_height - rect.bottom())
                    track_selected = self._selected_id == track.track_id
                    painter.fillRect(track_rect, QColor("#fef3c7") if track_selected else QColor("#f3f4f6"))
                    painter.setPen(QPen(QColor("#d97706") if track_selected else QColor("#c4cad3"), 2 if track_selected else 1))
                    painter.drawRect(track_rect)
                    painter.setPen(QColor("#374151"))
                    painter.drawText(track_rect.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignCenter, track.title)
                    top += track_height
            x += width


class FormStructureEditorDialog(QDialog):
    def __init__(
        self,
        form: FormDocument,
        repository: FormRepository,
        parent=None,
        *,
        language: str = "ru",
        dataset: Dataset | None = None,
        preview_callback: PreviewCallback | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.dataset = dataset
        self.language = language
        self.draft = DraftFormController.create(form)
        self.editor = FormStructureEditor(self.draft.form)
        self.preview_controller = FormPreviewController(preview_callback)
        self.saved_form: FormDocument | None = None
        self._updating_properties = False
        self._base_title = self._text("Редактор структуры формы", "Пішін құрылымының редакторы", "Form structure editor")
        self.setWindowTitle(self._base_title)
        self.resize(1080, 680)

        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            self._text("Структура", "Құрылым", "Structure"),
            self._text("Тип", "Түрі", "Type"),
            self._text("Ширина", "Ені", "Width"),
        ])
        self.tree.currentItemChanged.connect(self._selection_changed)
        left_layout.addWidget(self.tree, 1)

        column_buttons = QHBoxLayout()
        self._button(column_buttons, self._text("+ Колонка", "+ Баған", "+ Column"), self._add_column)
        self._button(column_buttons, self._text("− Колонка", "− Баған", "− Column"), self._remove_column)
        self._button(column_buttons, "↑", self._move_up)
        self._button(column_buttons, "↓", self._move_down)
        left_layout.addLayout(column_buttons)

        track_buttons = QHBoxLayout()
        self._button(track_buttons, self._text("+ Дорожка", "+ Жол", "+ Track"), self._add_track)
        self._button(track_buttons, self._text("− Дорожка", "− Жол", "− Track"), self._remove_track)
        self._button(track_buttons, self._text("Содержимое", "Мазмұны", "Content"), self._edit_track_content)
        left_layout.addLayout(track_buttons)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel(self._text("Предпросмотр структуры", "Құрылымды алдын ала қарау", "Structure preview")))
        self.preview = _FormPreview()
        right_layout.addWidget(self.preview)

        properties = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.editingFinished.connect(self._apply_title)
        properties.addRow(self._text("Заголовок", "Тақырып", "Title"), self.title_edit)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(80, 2000)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._apply_width)
        properties.addRow(self._text("Ширина колонки", "Баған ені", "Column width"), self.width_spin)

        self.kind_combo = QComboBox()
        for kind in TrackKind:
            self.kind_combo.addItem(kind.value, kind)
        self.kind_combo.currentIndexChanged.connect(self._apply_track_kind)
        properties.addRow(self._text("Тип дорожки", "Жол түрі", "Track type"), self.kind_combo)
        right_layout.addLayout(properties)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        actions = QHBoxLayout()
        self.live_preview_check = QCheckBox(self._text("Живой предпросмотр", "Тікелей алдын ала қарау", "Live preview"))
        self.live_preview_check.setChecked(True)
        self.live_preview_check.toggled.connect(self._toggle_live_preview)
        actions.addWidget(self.live_preview_check)
        actions.addStretch(1)
        self.apply_button = self._button(actions, self._text("Применить", "Қолдану", "Apply"), self._apply_preview)
        self.revert_button = self._button(actions, self._text("Отменить изменения", "Өзгерістерден бас тарту", "Revert"), self._revert)
        self.save_button = self._button(actions, self._text("Сохранить", "Сақтау", "Save"), self._save)
        self.close_button = self._button(actions, self._text("Закрыть", "Жабу", "Close"), self.accept)
        root.addLayout(actions)
        self._reload_tree()
        self._update_dirty_state()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def _button(self, layout: QHBoxLayout, caption: str, callback) -> QPushButton:
        button = QPushButton(caption)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _toggle_live_preview(self, enabled: bool) -> None:
        self.preview_controller.auto_apply = enabled
        if enabled and self.preview_controller.pending:
            self._apply_preview()

    def _form_changed(self) -> None:
        self.draft.changed()
        self.preview_controller.changed(self.editor.form)
        self._update_dirty_state()

    def _update_dirty_state(self) -> None:
        suffix = " *" if self.draft.dirty else ""
        self.setWindowTitle(f"{self._base_title} — {self.editor.form.name}{suffix}")
        self.revert_button.setEnabled(self.draft.dirty)

    def _apply_preview(self) -> None:
        try:
            self.editor.form.validate()
            self.preview_controller.apply(self.editor.form)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _revert(self) -> None:
        restored = self.draft.revert()
        self.editor = FormStructureEditor(restored)
        self.preview_controller.apply(restored)
        self._reload_tree()
        self._update_dirty_state()

    def _selected_ref(self) -> tuple[str, str] | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        kind = item.data(0, _ITEM_KIND_ROLE)
        object_id = item.data(0, _ITEM_ID_ROLE)
        if isinstance(kind, str) and isinstance(object_id, str):
            return kind, object_id
        return None

    def _reload_tree(self, selected_id: str | None = None) -> None:
        self.tree.clear()
        selected_item: QTreeWidgetItem | None = None
        for column in self.editor.form.columns:
            column_item = QTreeWidgetItem([column.title, self._text("Колонка", "Баған", "Column"), f"{column.width} px"])
            column_item.setData(0, _ITEM_KIND_ROLE, "column")
            column_item.setData(0, _ITEM_ID_ROLE, column.column_id)
            self.tree.addTopLevelItem(column_item)
            if selected_id == column.column_id:
                selected_item = column_item
            for track in column.tracks:
                track_item = QTreeWidgetItem([track.title, track.kind.value, ""])
                track_item.setData(0, _ITEM_KIND_ROLE, "track")
                track_item.setData(0, _ITEM_ID_ROLE, track.track_id)
                column_item.addChild(track_item)
                if selected_id == track.track_id:
                    selected_item = track_item
            column_item.setExpanded(True)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
        elif self.tree.topLevelItemCount():
            first_item = self.tree.topLevelItem(0)
            if first_item is not None:
                self.tree.setCurrentItem(first_item)
        self.preview.set_form(self.editor.form, selected_id)

    def _selection_changed(self, _current, _previous) -> None:
        ref = self._selected_ref()
        self._updating_properties = True
        try:
            if ref is None:
                self.title_edit.clear()
                self.title_edit.setEnabled(False)
                self.width_spin.setEnabled(False)
                self.kind_combo.setEnabled(False)
                return
            kind, object_id = ref
            self.title_edit.setEnabled(True)
            if kind == "column":
                column = self.editor.column(object_id)
                self.title_edit.setText(column.title)
                self.width_spin.setEnabled(True)
                self.width_spin.setValue(column.width)
                self.kind_combo.setEnabled(False)
            else:
                _column, track = self.editor.track(object_id)
                self.title_edit.setText(track.title)
                self.width_spin.setEnabled(False)
                self.kind_combo.setEnabled(True)
                index = self.kind_combo.findData(track.kind)
                if index >= 0:
                    self.kind_combo.setCurrentIndex(index)
            self.preview.set_form(self.editor.form, object_id)
        finally:
            self._updating_properties = False

    def _apply_title(self) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None:
            return
        try:
            if ref[0] == "column":
                self.editor.rename_column(ref[1], self.title_edit.text())
            else:
                self.editor.rename_track(ref[1], self.title_edit.text())
            self._reload_tree(ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._selection_changed(None, None)

    def _apply_width(self, value: int) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "column":
            return
        try:
            self.editor.set_column_width(ref[1], value)
            item = self.tree.currentItem()
            if item is not None:
                item.setText(2, f"{value} px")
            self.preview.set_form(self.editor.form, ref[1])
            self._form_changed()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _apply_track_kind(self, _index: int) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        kind = self.kind_combo.currentData()
        if not isinstance(kind, TrackKind):
            return
        try:
            self.editor.set_track_kind(ref[1], kind)
            self._reload_tree(ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _add_column(self) -> None:
        column = self.editor.add_column(self._text("Новая колонка", "Жаңа баған", "New column"))
        self._reload_tree(column.column_id)
        self._form_changed()

    def _remove_column(self) -> None:
        ref = self._selected_ref()
        if ref is None:
            return
        column_id = ref[1] if ref[0] == "column" else self.editor.track(ref[1])[0].column_id
        try:
            self.editor.remove_column(column_id)
            self._reload_tree()
            self._form_changed()
        except (KeyError, PermissionError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _add_track(self) -> None:
        ref = self._selected_ref()
        if ref is None:
            if not self.editor.form.columns:
                column = self.editor.add_column(self._text("Новая колонка", "Жаңа баған", "New column"))
                column_id = column.column_id
            else:
                column_id = self.editor.form.columns[0].column_id
        elif ref[0] == "column":
            column_id = ref[1]
        else:
            column_id = self.editor.track(ref[1])[0].column_id
        try:
            track = self.editor.add_track(
                column_id,
                title=self._text("Новая дорожка", "Жаңа жол", "New track"),
            )
            self._reload_tree(track.track_id)
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))


    def _edit_track_content(self) -> None:
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._text(
                    "Выберите дорожку.",
                    "Жолды таңдаңыз.",
                    "Select a track.",
                ),
            )
            return
        dialog = TrackContentEditorDialog(
            self.editor,
            ref[1],
            self,
            dataset=self.dataset,
            language=self.language,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_tree(ref[1])
            self._form_changed()

    def _remove_track(self) -> None:
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        try:
            self.editor.remove_track(ref[1])
            self._reload_tree()
            self._form_changed()
        except (KeyError, PermissionError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _move_up(self) -> None:
        self._move(-1)

    def _move_down(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        ref = self._selected_ref()
        if ref is None:
            return
        try:
            if ref[0] == "column":
                ids = [column.column_id for column in self.editor.form.columns]
                index = ids.index(ref[1])
                self.editor.move_column(ref[1], index + delta)
            else:
                column, _track = self.editor.track(ref[1])
                ids = [track.track_id for track in column.tracks]
                index = ids.index(ref[1])
                self.editor.move_track(ref[1], column.column_id, index + delta)
            self._reload_tree(ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _save(self) -> None:
        try:
            self.editor.form.validate()
            self.repository.save(self.editor.form)
        except (OSError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.draft.mark_saved()
        self.saved_form = self.draft.saved_copy()
        self.preview_controller.apply(self.editor.form)
        self._update_dirty_state()
