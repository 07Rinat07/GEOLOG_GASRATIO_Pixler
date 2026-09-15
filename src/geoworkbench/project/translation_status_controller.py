from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field

from geoworkbench.domain.localized_content import normalize_content_language
from geoworkbench.domain.models import Well
from geoworkbench.domain.translation_status import (
    TranslationStatus,
    TranslationStatusRegistry,
    TranslationStatusWorkflow,
)
from geoworkbench.domain.translation_readiness import (
    TranslatableField,
    TranslationReadinessQuery,
    TranslationReadinessSummary,
)
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class _TranslationStatusCommand:
    well_id: str
    before: TranslationStatusRegistry
    after: TranslationStatusRegistry
    before_field_revisions: dict[str, int]
    after_field_revisions: dict[str, int]
    before_revision: int
    after_revision: int


@dataclass(slots=True)
class TranslationStatusController:
    """Session boundary for atomic translation-status changes and history."""

    session: ProjectSession
    max_commands: int = 100
    _undo_stack: list[_TranslationStatusCommand] = field(default_factory=list, init=False)
    _redo_stack: list[_TranslationStatusCommand] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_commands, bool)
            or not isinstance(self.max_commands, int)
            or self.max_commands < 1
        ):
            raise ValueError("Размер истории должен быть положительным")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def status(self, field_id: str, language: object) -> TranslationStatus | None:
        well = self._require_well()
        return well.translation_statuses.get(field_id, {}).get(normalize_content_language(language))

    def authored_field_revision(self, field_id: str) -> int:
        normalized_field_id = self._field_id(field_id)
        return self._require_well().authored_field_revisions.get(normalized_field_id, 0)

    def readiness(
        self,
        fields: Iterable[TranslatableField],
        *,
        target_languages: Sequence[object],
        depth_range: tuple[float, float] | None = None,
        dependency_revisions: Mapping[str, int] | None = None,
        include_reviewed: bool = False,
    ) -> TranslationReadinessSummary:
        """Project the current well's readiness without mutating session state."""

        well = self._require_well()
        return TranslationReadinessQuery.summarize(
            fields,
            well.translation_statuses,
            target_languages=target_languages,
            depth_range=depth_range,
            source_revisions=well.authored_field_revisions,
            dependency_revisions=dependency_revisions,
            source_languages=well.authored_field_source_languages,
            include_reviewed=include_reviewed,
        )

    def record_authored_field_change(self, field_id: str) -> int:
        """Bump one source field and stale only translations based on its old revision."""

        well = self._require_well()
        normalized_field_id = self._field_id(field_id)
        after_revisions = deepcopy(well.authored_field_revisions)
        revision = after_revisions.get(normalized_field_id, 0) + 1
        after_revisions[normalized_field_id] = revision
        after_statuses = TranslationStatusWorkflow.invalidate_changed_revisions(
            well.translation_statuses,
            source_revisions={normalized_field_id: revision},
            dependency_revisions={},
        )
        self._apply(well, after_statuses, after_field_revisions=after_revisions)
        return revision

    def begin_draft(
        self,
        *,
        field_id: str,
        language: object,
        source_language: object,
        source_revision: int,
        dependency_revisions: Mapping[str, int] | None = None,
    ) -> TranslationStatus:
        well = self._require_well()
        after = TranslationStatusWorkflow.begin_draft(
            well.translation_statuses,
            field_id=field_id,
            language=language,
            source_language=source_language,
            source_revision=source_revision,
            dependency_revisions=dependency_revisions,
        )
        self._apply(well, after)
        status = self.status(field_id, language)
        assert status is not None
        return status

    def mark_missing(
        self,
        *,
        field_id: str,
        language: object,
        source_language: object,
        source_revision: int,
        dependency_revisions: Mapping[str, int] | None = None,
    ) -> TranslationStatus:
        well = self._require_well()
        after = TranslationStatusWorkflow.mark_missing(
            well.translation_statuses,
            field_id=field_id,
            language=language,
            source_language=source_language,
            source_revision=source_revision,
            dependency_revisions=dependency_revisions,
        )
        self._apply(well, after)
        status = self.status(field_id, language)
        assert status is not None
        return status

    def review(
        self,
        *,
        field_id: str,
        language: object,
        current_source_revision: int,
        current_dependency_revisions: Mapping[str, int] | None = None,
    ) -> TranslationStatus:
        well = self._require_well()
        after = TranslationStatusWorkflow.review(
            well.translation_statuses,
            field_id=field_id,
            language=language,
            current_source_revision=current_source_revision,
            current_dependency_revisions=current_dependency_revisions,
        )
        self._apply(well, after)
        status = self.status(field_id, language)
        assert status is not None
        return status

    def invalidate_changed_revisions(
        self,
        *,
        source_revisions: Mapping[str, int],
        dependency_revisions: Mapping[str, int],
    ) -> int:
        well = self._require_well()
        before = well.translation_statuses
        after = TranslationStatusWorkflow.invalidate_changed_revisions(
            before,
            source_revisions=source_revisions,
            dependency_revisions=dependency_revisions,
        )
        changed = sum(
            before.get(field_id, {}).get(language) != status
            for field_id, languages in after.items()
            for language, status in languages.items()
        )
        if changed:
            self._apply(well, after)
        return changed

    def undo(self) -> None:
        if not self._undo_stack:
            raise RuntimeError("Нет изменения статуса перевода для отмены")
        command = self._undo_stack[-1]
        well = self._command_well(command)
        if (
            well.translation_statuses != command.after
            or well.authored_field_revisions != command.after_field_revisions
            or well.content_revision != command.after_revision
        ):
            raise RuntimeError("Статусы переводов изменены вне истории команд")
        well.translation_statuses = deepcopy(command.before)
        well.authored_field_revisions = deepcopy(command.before_field_revisions)
        well.content_revision = command.before_revision
        self._undo_stack.pop()
        self._redo_stack.append(command)
        self.session.dirty = True

    def redo(self) -> None:
        if not self._redo_stack:
            raise RuntimeError("Нет изменения статуса перевода для повтора")
        command = self._redo_stack[-1]
        well = self._command_well(command)
        if (
            well.translation_statuses != command.before
            or well.authored_field_revisions != command.before_field_revisions
            or well.content_revision != command.before_revision
        ):
            raise RuntimeError("Статусы переводов изменены вне истории команд")
        well.translation_statuses = deepcopy(command.after)
        well.authored_field_revisions = deepcopy(command.after_field_revisions)
        well.content_revision = command.after_revision
        self._redo_stack.pop()
        self._undo_stack.append(command)
        self.session.dirty = True

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _apply(
        self,
        well: Well,
        after: TranslationStatusRegistry,
        *,
        after_field_revisions: dict[str, int] | None = None,
    ) -> None:
        before = deepcopy(well.translation_statuses)
        before_field_revisions = deepcopy(well.authored_field_revisions)
        before_revision = well.content_revision
        well.translation_statuses = after
        well.authored_field_revisions = (
            deepcopy(after_field_revisions)
            if after_field_revisions is not None
            else deepcopy(before_field_revisions)
        )
        well.content_revision += 1
        self._undo_stack.append(
            _TranslationStatusCommand(
                well_id=well.well_id,
                before=before,
                after=deepcopy(after),
                before_field_revisions=before_field_revisions,
                after_field_revisions=deepcopy(well.authored_field_revisions),
                before_revision=before_revision,
                after_revision=well.content_revision,
            )
        )
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()
        self.session.dirty = True

    @staticmethod
    def _field_id(field_id: str) -> str:
        if not isinstance(field_id, str) or not field_id.strip():
            raise ValueError("ID авторского поля не может быть пустым")
        return field_id.strip()

    def _command_well(self, command: _TranslationStatusCommand) -> Well:
        well = self._require_well()
        if well.well_id != command.well_id:
            raise RuntimeError("История статусов относится к другой скважине")
        return well

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well
