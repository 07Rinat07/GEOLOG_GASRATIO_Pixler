from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Literal

from geoworkbench.domain.annotation_style import AnnotationStyle
from geoworkbench.domain.report_annotations import (
    ReportAnnotationAnchor,
    ReportAnnotationKind,
    ReportAnnotationRecord,
    new_report_annotation_id,
    report_annotation_scope_id,
    validate_report_annotation,
)
from geoworkbench.domain.report_composition import (
    DEFAULT_INTERPRETATION_REPORT_COMPOSITION,
    InterpretationReportComposition,
    ensure_report_composition_id,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import (
    CommandHistory,
    CommandHistoryCheckpoint,
)


_HISTORY_DOMAIN = "report_annotation"


@dataclass(frozen=True, slots=True)
class ReportAnnotationEditorCheckpoint:
    dataset_id: str
    composition_id: str
    composition_existed: bool
    presentation_state: InterpretationReportComposition
    annotations: tuple[ReportAnnotationRecord, ...]
    history: CommandHistoryCheckpoint = field(repr=False)


@dataclass(slots=True)
class _ReportAnnotationCommand:
    session: ProjectSession = field(repr=False)
    dataset_id: str
    composition_id: str
    presentation_state: InterpretationReportComposition = field(repr=False)
    operation: Literal["add", "update", "remove"]
    index: int
    before: ReportAnnotationRecord | None
    after: ReportAnnotationRecord | None
    composition_created: bool
    description: str
    history_domain: str = field(default=_HISTORY_DOMAIN, init=False)
    _applied: bool = field(default=True, init=False, repr=False)

    def execute(self) -> None:
        if self._applied:
            raise RuntimeError("Команда report annotation уже выполнена")
        if self.operation == "add":
            self._redo_add()
        elif self.operation == "update":
            self._redo_update()
        else:
            self._redo_remove()
        self._applied = True
        self.session.dirty = True

    def undo(self) -> None:
        if not self._applied:
            raise RuntimeError("Команда report annotation ещё не выполнена")
        if self.operation == "add":
            self._undo_add()
        elif self.operation == "update":
            self._undo_update()
        else:
            self._undo_remove()
        self._applied = False
        self.session.dirty = True

    def _current(self, *, allow_missing_created: bool = False) -> InterpretationReportComposition:
        current = self.session.report_compositions.get(self.dataset_id)
        if current is None:
            if allow_missing_created and self.composition_created:
                return self.presentation_state
            raise RuntimeError("Report composition была удалена вне истории команд")
        if current.composition_id != self.composition_id:
            raise RuntimeError("Report composition была заменена вне истории команд")
        if replace(current, annotations=()) != self.presentation_state:
            raise RuntimeError("Report composition была изменена вне истории report annotations")
        return current

    def _write_annotations(
        self,
        current: InterpretationReportComposition,
        annotations: tuple[ReportAnnotationRecord, ...],
    ) -> None:
        self.session.report_compositions[self.dataset_id] = replace(
            current,
            annotations=annotations,
        )

    def _redo_add(self) -> None:
        if self.after is None:
            raise RuntimeError("Повреждена команда добавления report annotation")
        current = self._current(allow_missing_created=True)
        annotations = list(current.annotations)
        if not 0 <= self.index <= len(annotations):
            raise RuntimeError("Позиция report annotation была изменена вне истории команд")
        annotations.insert(self.index, self.after)
        self._write_annotations(current, tuple(annotations))

    def _undo_add(self) -> None:
        if self.after is None:
            raise RuntimeError("Повреждена команда добавления report annotation")
        current = self._current()
        annotations = list(current.annotations)
        if not 0 <= self.index < len(annotations) or annotations[self.index] != self.after:
            raise RuntimeError("Report annotation была изменена вне истории команд")
        annotations.pop(self.index)
        if self.composition_created and not annotations:
            self.session.report_compositions.pop(self.dataset_id, None)
            return
        self._write_annotations(current, tuple(annotations))

    def _redo_update(self) -> None:
        if self.before is None or self.after is None:
            raise RuntimeError("Повреждена команда изменения report annotation")
        current = self._current()
        annotations = list(current.annotations)
        if not 0 <= self.index < len(annotations) or annotations[self.index] != self.before:
            raise RuntimeError("Report annotation была изменена вне истории команд")
        annotations[self.index] = self.after
        self._write_annotations(current, tuple(annotations))

    def _undo_update(self) -> None:
        if self.before is None or self.after is None:
            raise RuntimeError("Повреждена команда изменения report annotation")
        current = self._current()
        annotations = list(current.annotations)
        if not 0 <= self.index < len(annotations) or annotations[self.index] != self.after:
            raise RuntimeError("Report annotation была изменена вне истории команд")
        annotations[self.index] = self.before
        self._write_annotations(current, tuple(annotations))

    def _redo_remove(self) -> None:
        if self.before is None:
            raise RuntimeError("Повреждена команда удаления report annotation")
        current = self._current()
        annotations = list(current.annotations)
        if not 0 <= self.index < len(annotations) or annotations[self.index] != self.before:
            raise RuntimeError("Report annotation была изменена вне истории команд")
        annotations.pop(self.index)
        self._write_annotations(current, tuple(annotations))

    def _undo_remove(self) -> None:
        if self.before is None:
            raise RuntimeError("Повреждена команда удаления report annotation")
        current = self._current()
        annotations = list(current.annotations)
        if not 0 <= self.index <= len(annotations):
            raise RuntimeError("Позиция report annotation была изменена вне истории команд")
        annotations.insert(self.index, self.before)
        self._write_annotations(current, tuple(annotations))


@dataclass(slots=True)
class ReportAnnotationController:
    """CRUD and transactional editor boundary for report-owned annotations."""

    session: ProjectSession
    shared_history: CommandHistory | None = field(default=None, kw_only=True, repr=False)
    _history: CommandHistory = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._history = self.shared_history or CommandHistory()

    @property
    def can_undo(self) -> bool:
        command = self._history.next_undo
        return command is not None and command.history_domain == _HISTORY_DOMAIN

    @property
    def can_redo(self) -> bool:
        command = self._history.next_redo
        return command is not None and command.history_domain == _HISTORY_DOMAIN

    def current_scope_id(self) -> str:
        well_id, dataset_id = self._current_ids()
        composition = self._resolved_composition(dataset_id)
        return report_annotation_scope_id(well_id, dataset_id, composition.composition_id)

    def available(self) -> tuple[ReportAnnotationRecord, ...]:
        _, dataset_id = self._current_ids()
        return self._resolved_composition(dataset_id).annotations

    def get(self, annotation_id: str) -> ReportAnnotationRecord:
        _, record = self._record_with_index(annotation_id)
        return record

    def add(
        self,
        *,
        kind: ReportAnnotationKind | str = ReportAnnotationKind.CALLOUT,
        anchor: ReportAnnotationAnchor | str = ReportAnnotationAnchor.DEPTH,
        text: str = "",
        track_key: str | None = None,
        depth: float | None = None,
        top_depth: float | None = None,
        bottom_depth: float | None = None,
        x_fraction: float = 0.5,
        offset_x: float = 18.0,
        offset_y: float = -36.0,
        width: float = 220.0,
        height: float = 76.0,
        style: AnnotationStyle | Mapping[str, object] | None = None,
        visible: bool = True,
        locked: bool = False,
        print_enabled: bool = True,
        text_i18n: Mapping[str, str] | None = None,
    ) -> ReportAnnotationRecord:
        well_id, dataset_id = self._current_ids()
        existing = self.session.report_compositions.get(dataset_id)
        composition = self._resolved_composition(dataset_id)
        scope_id = report_annotation_scope_id(well_id, dataset_id, composition.composition_id)
        normalized_style = self._style(style)
        record = validate_report_annotation(
            ReportAnnotationRecord(
                annotation_id=new_report_annotation_id(),
                scope_id=scope_id,
                kind=ReportAnnotationKind(kind),
                anchor=ReportAnnotationAnchor(anchor),
                text=text,
                track_key=track_key,
                depth=depth,
                top_depth=top_depth,
                bottom_depth=bottom_depth,
                x_fraction=x_fraction,
                offset_x=offset_x,
                offset_y=offset_y,
                width=width,
                height=height,
                style=normalized_style,
                visible=self._bool(visible, "visible"),
                locked=self._bool(locked, "locked"),
                print_enabled=self._bool(print_enabled, "print_enabled"),
                text_i18n=dict(text_i18n or {}),
            )
        )
        index = len(composition.annotations)
        after = replace(composition, annotations=(*composition.annotations, record))
        self.session.report_compositions[dataset_id] = after
        command = _ReportAnnotationCommand(
            session=self.session,
            dataset_id=dataset_id,
            composition_id=composition.composition_id,
            presentation_state=replace(composition, annotations=()),
            operation="add",
            index=index,
            before=None,
            after=record,
            composition_created=existing is None,
            description="Добавление report annotation",
        )
        self._history.record_applied(command)
        self.session.dirty = True
        return record

    def update(
        self,
        annotation_id: str,
        **changes: object,
    ) -> ReportAnnotationRecord:
        _, dataset_id = self._current_ids()
        composition = self._resolved_composition(dataset_id)
        index, current = self._record_with_index(annotation_id)
        forbidden = {"annotation_id", "scope_id"}
        unknown = set(changes) - {
            "kind",
            "anchor",
            "text",
            "track_key",
            "depth",
            "top_depth",
            "bottom_depth",
            "x_fraction",
            "offset_x",
            "offset_y",
            "width",
            "height",
            "style",
            "visible",
            "locked",
            "print_enabled",
            "text_i18n",
        }
        if forbidden & set(changes) or unknown:
            raise ValueError(
                "Нельзя изменить identity/scope или неизвестное поле report annotation"
            )
        normalized = dict(changes)
        if "kind" in normalized:
            normalized["kind"] = ReportAnnotationKind(normalized["kind"])
        if "anchor" in normalized:
            normalized["anchor"] = ReportAnnotationAnchor(normalized["anchor"])
        if "style" in normalized:
            normalized["style"] = self._style(normalized["style"])
        for key in ("visible", "locked", "print_enabled"):
            if key in normalized:
                normalized[key] = self._bool(normalized[key], key)
        if "text_i18n" in normalized:
            value = normalized["text_i18n"]
            if value is None:
                normalized["text_i18n"] = {}
            elif isinstance(value, Mapping):
                normalized["text_i18n"] = dict(value)
            else:
                raise ValueError("text_i18n report annotation должен быть объектом")

        updated = validate_report_annotation(replace(current, **normalized))
        if updated == current:
            return current

        annotations = list(composition.annotations)
        annotations[index] = updated
        self.session.report_compositions[dataset_id] = replace(
            composition,
            annotations=tuple(annotations),
        )
        self._history.record_applied(
            _ReportAnnotationCommand(
                session=self.session,
                dataset_id=dataset_id,
                composition_id=composition.composition_id,
                presentation_state=replace(composition, annotations=()),
                operation="update",
                index=index,
                before=current,
                after=updated,
                composition_created=False,
                description="Изменение report annotation",
            )
        )
        self.session.dirty = True
        return updated

    def remove(self, annotation_id: str) -> ReportAnnotationRecord:
        _, dataset_id = self._current_ids()
        composition = self._resolved_composition(dataset_id)
        index, current = self._record_with_index(annotation_id)
        annotations = list(composition.annotations)
        annotations.pop(index)
        self.session.report_compositions[dataset_id] = replace(
            composition,
            annotations=tuple(annotations),
        )
        self._history.record_applied(
            _ReportAnnotationCommand(
                session=self.session,
                dataset_id=dataset_id,
                composition_id=composition.composition_id,
                presentation_state=replace(composition, annotations=()),
                operation="remove",
                index=index,
                before=current,
                after=None,
                composition_created=False,
                description="Удаление report annotation",
            )
        )
        self.session.dirty = True
        return current

    def undo(self) -> str:
        if not self.can_undo:
            raise RuntimeError("Нет изменений report annotations для отмены")
        command = self._history.undo()
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        if not self.can_redo:
            raise RuntimeError("Нет изменений report annotations для повтора")
        command = self._history.redo()
        self.session.dirty = True
        return command.description

    def checkpoint(self) -> ReportAnnotationEditorCheckpoint:
        _, dataset_id = self._current_ids()
        existing = self.session.report_compositions.get(dataset_id)
        composition = self._resolved_composition(dataset_id)
        return ReportAnnotationEditorCheckpoint(
            dataset_id=dataset_id,
            composition_id=composition.composition_id,
            composition_existed=existing is not None,
            presentation_state=replace(composition, annotations=()),
            annotations=composition.annotations,
            history=self._history.checkpoint(),
        )

    def restore(self, checkpoint: ReportAnnotationEditorCheckpoint) -> None:
        if not isinstance(checkpoint, ReportAnnotationEditorCheckpoint):
            raise TypeError("Ожидалась контрольная точка report annotations")
        current = self.session.report_compositions.get(checkpoint.dataset_id)
        if current is None:
            if checkpoint.composition_existed:
                raise RuntimeError("Report composition была удалена после checkpoint")
            current = checkpoint.presentation_state
        if current.composition_id != checkpoint.composition_id:
            raise RuntimeError("Report composition была заменена после checkpoint")
        if replace(current, annotations=()) != checkpoint.presentation_state:
            raise RuntimeError("Presentation settings изменены после checkpoint")

        if checkpoint.composition_existed:
            self.session.report_compositions[checkpoint.dataset_id] = replace(
                current,
                annotations=checkpoint.annotations,
            )
        else:
            self.session.report_compositions.pop(checkpoint.dataset_id, None)
        self._history.restore(checkpoint.history)
        self.session.dirty = True

    def clear_history(self) -> None:
        self._history.clear()

    def _resolved_composition(self, dataset_id: str) -> InterpretationReportComposition:
        composition = self.session.report_compositions.get(
            dataset_id,
            DEFAULT_INTERPRETATION_REPORT_COMPOSITION,
        )
        return ensure_report_composition_id(composition, dataset_id)

    def _record_with_index(self, annotation_id: str) -> tuple[int, ReportAnnotationRecord]:
        normalized = annotation_id.strip() if isinstance(annotation_id, str) else ""
        if not normalized:
            raise ValueError("ID report annotation не может быть пустым")
        _, dataset_id = self._current_ids()
        for index, record in enumerate(self._resolved_composition(dataset_id).annotations):
            if record.annotation_id == normalized:
                expected_scope = self.current_scope_id()
                if record.scope_id != expected_scope:
                    raise RuntimeError("Report annotation принадлежит другой report composition")
                return index, record
        raise KeyError(normalized)

    def _current_ids(self) -> tuple[str, str]:
        well = self.session.current_well
        dataset = self.session.current_dataset
        if well is None or dataset is None:
            raise RuntimeError("Сначала выберите скважину и набор данных")
        return well.well_id, dataset.dataset_id

    @staticmethod
    def _style(value: object) -> AnnotationStyle:
        if value is None:
            return AnnotationStyle()
        if isinstance(value, AnnotationStyle):
            return value
        if isinstance(value, Mapping):
            return AnnotationStyle.from_mapping(value)
        raise ValueError("Некорректный стиль report annotation")

    @staticmethod
    def _bool(value: object, label: str) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{label} report annotation должен быть boolean")
        return value


__all__ = ["ReportAnnotationController", "ReportAnnotationEditorCheckpoint"]
