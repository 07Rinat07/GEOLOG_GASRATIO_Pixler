from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
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
        # The modal editor owns one transactional command suffix. Reusing commands
        # from an earlier dialog or another dataset would make Cancel ambiguous.
        self.controller.clear_history()
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
        for button in (
            self.add_button,
            self.save_button,
            self.remove_button,
            self.undo_button,
            self.redo_button,
        ):
            actions.addWidget(button)
        root.addLayout(actions)

        self.status = QLabel(self)
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
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
        spin.setDecimals(6)
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
            self.text.clear()
            self._sync_actions()
            return
        self._set_combo_value(self.kind, record.kind.value)
        self._set_combo_value(self.anchor, record.anchor.value)
        if record.track_key:
            self.track.setCurrentText(record.track_key)
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
        self.save_button.setEnabled(True)
        self.remove_button.setEnabled(has_selected)
        self.undo_button.setEnabled(self.controller.can_undo)
        self.redo_button.setEnabled(self.controller.can_redo)

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
