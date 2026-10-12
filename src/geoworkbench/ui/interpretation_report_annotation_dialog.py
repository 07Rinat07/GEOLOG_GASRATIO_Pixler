from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.report_annotations import (
    ReportAnnotationAnchor,
    ReportAnnotationKind,
    ReportAnnotationRecord,
)
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.window_geometry import fit_window_to_screen


@dataclass(frozen=True, slots=True)
class _AnnotationEditorValues:
    kind: ReportAnnotationKind
    anchor: ReportAnnotationAnchor
    text: str
    track_key: str | None
    depth: float | None
    top_depth: float | None
    bottom_depth: float | None


class InterpretationReportAnnotationDialog(QDialog):
    """Transactional editor for annotations owned by one report composition."""

    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        shared_history: CommandHistory | None = None,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._language = language
        self._on_changed = on_changed
        self.controller = ReportAnnotationController(
            session,
            shared_history=shared_history,
        )
        # Reopening retains shared history; the controller gates Undo/Redo by
        # report ownership and Cancel restores this opening checkpoint.
        self._checkpoint = self.controller.checkpoint()

        self.setModal(True)

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.annotation = QComboBox(self)
        self.annotation.setObjectName("report-annotation-existing")
        form.addRow(self._text("Аннотация", "Аннотация", "Annotation"), self.annotation)

        self.kind = QComboBox(self)
        self.kind.setObjectName("report-annotation-kind")
        for kind_item in ReportAnnotationKind:
            self.kind.addItem(self._kind_label(kind_item), kind_item.value)
        form.addRow(self._text("Тип", "Түрі", "Type"), self.kind)

        self.anchor = QComboBox(self)
        self.anchor.setObjectName("report-annotation-anchor")
        for anchor_item in ReportAnnotationAnchor:
            self.anchor.addItem(self._anchor_label(anchor_item), anchor_item.value)
        form.addRow(self._text("Привязка", "Байлау", "Anchor"), self.anchor)

        self.track = QComboBox(self)
        self.track.setObjectName("report-annotation-track")
        self.track.setEditable(True)
        self._populate_tracks(session)
        form.addRow(self._text("Колонка", "Баған", "Track"), self.track)

        self.text = QLineEdit(self)
        self.text.setObjectName("report-annotation-text")
        form.addRow(self._text("Текст", "Мәтін", "Text"), self.text)

        self.depth_spin = self._depth_spin("report-annotation-depth")
        self.top_depth_spin = self._depth_spin("report-annotation-top")
        self.bottom_depth_spin = self._depth_spin("report-annotation-bottom")
        form.addRow(self._text("Глубина", "Тереңдік", "Depth"), self.depth_spin)
        form.addRow(self._text("Кровля", "Жоғарғы шекара", "Top"), self.top_depth_spin)
        form.addRow(self._text("Подошва", "Төменгі шекара", "Bottom"), self.bottom_depth_spin)

        actions = QHBoxLayout()
        self.add_button = QPushButton(self._text("Добавить", "Қосу", "Add"), self)
        self.save_button = QPushButton(self._text("Сохранить", "Сақтау", "Save"), self)
        self.remove_button = QPushButton(self._text("Удалить", "Жою", "Delete"), self)
        self.undo_button = QPushButton(self._text("Отменить", "Болдырмау", "Undo"), self)
        self.redo_button = QPushButton(self._text("Повторить", "Қайталау", "Redo"), self)
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.undo_shortcut.activated.connect(self.undo_button.click)
        self.redo_shortcut.activated.connect(self.redo_button.click)
        for button in (
            self.add_button,
            self.save_button,
            self.remove_button,
            self.undo_button,
            self.redo_button,
        ):
            actions.addWidget(button)
        root.addLayout(actions)
        self.batch_remove_button = QPushButton(
            self._text("Удалить группу…", "Топты жою…", "Delete group…"), self,
        )
        self.batch_remove_button.setObjectName("report-annotation-delete-group")
        self.batch_remove_button.clicked.connect(self._remove_group)
        root.addWidget(self.batch_remove_button)

        self.status = QLabel(self)
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply,
            parent=self,
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setText(self._text("Применить", "Қолдану", "Apply"))
        self.apply_button.setObjectName("report-annotation-apply")
        self.apply_button.clicked.connect(self._apply)
        root.addWidget(buttons)

        self.annotation.currentIndexChanged.connect(self._load_selected)
        self.anchor.currentIndexChanged.connect(self._sync_anchor_controls)
        self.add_button.clicked.connect(self._add)
        self.save_button.clicked.connect(self._save)
        self.remove_button.clicked.connect(self._remove)
        self.undo_button.clicked.connect(self._undo)
        self.redo_button.clicked.connect(self._redo)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self._reload_annotations()
        self._sync_anchor_controls()
        self._sync_actions()
        self.setWindowTitle(
            self._text(
                "Аннотации итогового отчёта",
                "Қорытынды есеп аннотациялары",
                "Final report annotations",
            )
        )
        fit_window_to_screen(
            self,
            preferred=QSize(620, 500),
            minimum=QSize(500, 380),
        )

    @staticmethod
    def _depth_spin(name: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setObjectName(name)
        # LAS/GTI depths may have sub-micrometre decimal increments.
        # Six places silently rounded annotation anchors on edit/reopen.
        spin.setDecimals(9)
        spin.setRange(-1.0e12, 1.0e12)
        return spin

    def _populate_tracks(self, session: ProjectSession) -> None:
        keys = [
            "depth:left",
            "depth:right",
            "geology:cuttings",
            "geology:lba",
        ]
        dataset = session.current_dataset
        if dataset is not None:
            for curve in dataset.curves.values():
                mnemonic = (
                    curve.metadata.canonical_mnemonic
                    or curve.metadata.original_mnemonic
                ).strip()
                if mnemonic:
                    keys.append(f"curve:{mnemonic}")
        for key in dict.fromkeys(keys):
            self.track.addItem(key)

    def _reload_annotations(self, selected_id: str | None = None) -> None:
        self.annotation.blockSignals(True)
        try:
            self.annotation.clear()
            self.annotation.addItem(self._text("Новая", "Жаңа", "New"), None)
            selected_index = 0
            for record in self.controller.available():
                label = record.text.strip() or record.kind.value
                self.annotation.addItem(
                    f"{label} · {record.anchor.value}",
                    record.annotation_id,
                )
                if record.annotation_id == selected_id:
                    selected_index = self.annotation.count() - 1
            self.annotation.setCurrentIndex(selected_index)
        finally:
            self.annotation.blockSignals(False)
        self._load_selected()
        self._sync_actions()

    def _selected_id(self) -> str | None:
        value = self.annotation.currentData()
        return value if isinstance(value, str) and value else None

    def _selected_record(self) -> ReportAnnotationRecord | None:
        annotation_id = self._selected_id()
        return self.controller.get(annotation_id) if annotation_id is not None else None

    def _load_selected(self) -> None:
        record = self._selected_record()
        if record is None:
            # "New" must not inherit depth, track or anchor from the last
            # selected record; otherwise the next note can be painted on the
            # wrong geological interval without the operator noticing.
            self._set_combo_value(self.kind, ReportAnnotationKind.CALLOUT.value)
            self._set_combo_value(self.anchor, ReportAnnotationAnchor.DEPTH.value)
            self.track.setCurrentText("")
            self.text.clear()
            self.depth_spin.setValue(0.0)
            self.top_depth_spin.setValue(0.0)
            self.bottom_depth_spin.setValue(0.0)
            self._sync_anchor_controls()
            self._sync_actions()
            return
        self._set_combo_value(self.kind, record.kind.value)
        self._set_combo_value(self.anchor, record.anchor.value)
        # A note without a track is attached to the chart, not to whichever
        # track happened to be selected earlier in the editor.
        self.track.setCurrentText(record.track_key or "")
        self.text.setText(record.text)
        self.depth_spin.setValue(record.depth or 0.0)
        self.top_depth_spin.setValue(record.top_depth or 0.0)
        self.bottom_depth_spin.setValue(record.bottom_depth or 0.0)
        self._sync_anchor_controls()
        self._sync_actions()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _current_kind(self) -> ReportAnnotationKind:
        return ReportAnnotationKind(str(self.kind.currentData()))

    def _current_anchor(self) -> ReportAnnotationAnchor:
        return ReportAnnotationAnchor(str(self.anchor.currentData()))

    def _values(self) -> _AnnotationEditorValues:
        anchor = self._current_anchor()
        return _AnnotationEditorValues(
            kind=self._current_kind(),
            anchor=anchor,
            text=self.text.text(),
            track_key=self.track.currentText().strip() or None,
            depth=(
                self.depth_spin.value()
                if anchor is ReportAnnotationAnchor.DEPTH
                else None
            ),
            top_depth=(
                self.top_depth_spin.value()
                if anchor is ReportAnnotationAnchor.INTERVAL
                else None
            ),
            bottom_depth=(
                self.bottom_depth_spin.value()
                if anchor is ReportAnnotationAnchor.INTERVAL
                else None
            ),
        )

    def _add(self) -> None:
        values = self._values()
        try:
            record = self.controller.add(
                kind=values.kind,
                anchor=values.anchor,
                text=values.text,
                track_key=values.track_key,
                depth=values.depth,
                top_depth=values.top_depth,
                bottom_depth=values.bottom_depth,
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            self._show_error(exc)
            return
        self._changed(record.annotation_id)

    def _save(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            self._add()
            return
        values = self._values()
        try:
            record = self.controller.update(
                annotation_id,
                kind=values.kind,
                anchor=values.anchor,
                text=values.text,
                track_key=values.track_key,
                depth=values.depth,
                top_depth=values.top_depth,
                bottom_depth=values.bottom_depth,
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            self._show_error(exc)
            return
        self._changed(record.annotation_id)

    def _remove(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            return
        try:
            self.controller.remove(annotation_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            self._show_error(exc)
            return
        self._changed()

    def _remove_group(self) -> None:
        selection = QDialog(self)
        selection.setWindowTitle(self.batch_remove_button.text().rstrip("…"))
        layout = QVBoxLayout(selection)
        listing = QListWidget(selection)
        listing.setObjectName("report-annotation-group-selection")
        listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for record in self.controller.available():
            item = QListWidgetItem(record.text.strip() or self._kind_label(record.kind), listing)
            item.setData(Qt.ItemDataRole.UserRole, record.annotation_id)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=selection,
        )
        confirm = buttons.button(QDialogButtonBox.StandardButton.Ok)
        confirm.setText(self._text("Удалить", "Жою", "Delete"))
        confirm.setEnabled(False)
        listing.itemSelectionChanged.connect(lambda: confirm.setEnabled(bool(listing.selectedItems())))
        buttons.accepted.connect(selection.accept)
        buttons.rejected.connect(selection.reject)
        layout.addWidget(buttons)
        fit_window_to_screen(selection, preferred=QSize(480, 360), minimum=QSize(320, 240))
        try:
            if selection.exec() != QDialog.DialogCode.Accepted:
                return
            ids = tuple(item.data(Qt.ItemDataRole.UserRole) for item in listing.selectedItems())
            if not ids:
                return
            try:
                self.controller.remove_many(ids)
            except (KeyError, RuntimeError, TypeError, ValueError) as exc:
                self._show_error(exc)
                return
            self._changed()
        finally:
            selection.deleteLater()

    def _undo(self) -> None:
        try:
            self.controller.undo()
        except RuntimeError as exc:
            self._show_error(exc)
            return
        self._changed()

    def _redo(self) -> None:
        try:
            self.controller.redo()
        except RuntimeError as exc:
            self._show_error(exc)
            return
        self._changed()

    def _changed(self, selected_id: str | None = None) -> None:
        self.status.clear()
        self._reload_annotations(selected_id)
        if self._on_changed is not None:
            self._on_changed()

    def _sync_anchor_controls(self) -> None:
        anchor = self._current_anchor()
        self.depth_spin.setEnabled(anchor is ReportAnnotationAnchor.DEPTH)
        self.top_depth_spin.setEnabled(anchor is ReportAnnotationAnchor.INTERVAL)
        self.bottom_depth_spin.setEnabled(anchor is ReportAnnotationAnchor.INTERVAL)
        self.track.setEnabled(True)

    def _sync_actions(self) -> None:
        has_selected = self._selected_id() is not None
        self.batch_remove_button.setEnabled(bool(self.controller.available()))
        self.save_button.setEnabled(True)
        self.remove_button.setEnabled(has_selected)
        self.undo_button.setEnabled(self.controller.can_undo)
        self.redo_button.setEnabled(self.controller.can_redo)

    def _apply(self) -> None:
        # Apply commits the current annotation draft without consuming history.
        # Individual form edits still use the existing Add/Save controls.
        self._checkpoint = self.controller.checkpoint()
        self.status.clear()
        self._sync_actions()
        if self._on_changed is not None:
            self._on_changed()

    def reject(self) -> None:
        try:
            self.controller.restore(self._checkpoint)
        except RuntimeError as exc:
            self._show_error(exc)
            return
        if self._on_changed is not None:
            self._on_changed()
        super().reject()

    def _show_error(self, exc: Exception) -> None:
        message = str(exc)
        self.status.setText(message)
        QMessageBox.warning(
            self,
            self._text("Аннотации отчёта", "Есеп аннотациялары", "Report annotations"),
            message,
        )

    def _text(self, ru: str, kk: str, en: str) -> str:
        if self._language is AppLanguage.KK:
            return kk
        if self._language is AppLanguage.EN:
            return en
        return ru

    def _kind_label(self, kind: ReportAnnotationKind) -> str:
        labels = {
            ReportAnnotationKind.TEXT: self._text("Текст", "Мәтін", "Text"),
            ReportAnnotationKind.CALLOUT: self._text("Выноска", "Түсіндірме", "Callout"),
            ReportAnnotationKind.ARROW: self._text("Стрелка", "Көрсеткі", "Arrow"),
            ReportAnnotationKind.INTERVAL_HIGHLIGHT: self._text(
                "Подсветка интервала",
                "Аралықты ерекшелеу",
                "Interval highlight",
            ),
            ReportAnnotationKind.REMARK: self._text("Примечание", "Ескертпе", "Remark"),
        }
        return labels[kind]

    def _anchor_label(self, anchor: ReportAnnotationAnchor) -> str:
        labels = {
            ReportAnnotationAnchor.DEPTH: self._text("Глубина", "Тереңдік", "Depth"),
            ReportAnnotationAnchor.INTERVAL: self._text("Интервал", "Аралық", "Interval"),
            ReportAnnotationAnchor.TRACK: self._text("Колонка", "Баған", "Track"),
        }
        return labels[anchor]


__all__ = ["InterpretationReportAnnotationDialog"]
