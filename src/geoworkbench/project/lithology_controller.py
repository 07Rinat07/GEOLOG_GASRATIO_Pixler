from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields
from functools import partial
from typing import Callable

import numpy as np

from geoworkbench.domain.authored_translation_tracking import (
    AuthoredTranslationPlan,
    AuthoredTranslationWorkflow,
)
from geoworkbench.domain.localized_content import (
    SUPPORTED_CONTENT_LANGUAGES,
    bump_language_revision,
    normalize_content_language,
    set_localized_text,
    validate_localized_texts,
)
from geoworkbench.domain.models import LithologyInterval, Well, new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CallbackCommand, CommandHistory


@dataclass(frozen=True, slots=True)
class _LithologyTrackingSnapshot:
    translation_statuses: dict[str, object]
    authored_field_revisions: dict[str, int]
    authored_field_source_languages: dict[str, str]
    language_revisions: dict[str, int]
    content_revision: int


@dataclass(slots=True)
class LithologyController:
    session: ProjectSession
    shared_history: CommandHistory | None = field(default=None, kw_only=True, repr=False)
    _history: CommandHistory = field(init=False, repr=False)

    _HISTORY_DOMAIN = "lithology"

    def __post_init__(self) -> None:
        self._history = self.shared_history or CommandHistory()

    @property
    def can_undo(self) -> bool:
        command = self._history.next_undo
        return command is not None and command.history_domain == self._HISTORY_DOMAIN

    @property
    def can_redo(self) -> bool:
        command = self._history.next_redo
        return command is not None and command.history_domain == self._HISTORY_DOMAIN

    def available(self) -> tuple[LithologyInterval, ...]:
        return tuple(
            sorted(
                self._require_well().lithology,
                key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
            )
        )

    def get(self, interval_id: str) -> LithologyInterval:
        return self._require_interval(interval_id)

    def source_language(self, interval_id: str) -> str | None:
        field_id = self._description_field_id(self._require_interval(interval_id).interval_id)
        return self._require_well().authored_field_source_languages.get(field_id)

    def add(
        self,
        top_depth: float,
        bottom_depth: float,
        lithotype_id: str,
        *,
        description: str | None = None,
        content_language: object | None = None,
        description_i18n: object | None = None,
        source_language: object | None = None,
    ) -> LithologyInterval:
        top, bottom, lithotype, normalized_description = self._validate(
            top_depth,
            bottom_depth,
            lithotype_id,
            description,
        )
        localized_descriptions = self._validate_descriptions(description_i18n)
        self._ensure_no_overlap(top, bottom)
        interval_id = new_id()
        well = self._require_well()
        position = len(well.lithology)
        before_tracking = self._tracking_snapshot(interval_id)

        tracking_plan: AuthoredTranslationPlan | None = None
        after_language_revisions: dict[str, int] | None = None
        if source_language is not None:
            if localized_descriptions is None:
                raise ValueError("Для языка оригинала требуется многоязычное описание")
            tracking_plan = self._translation_plan(
                interval_id,
                previous_texts={},
                current_texts=localized_descriptions,
                source_language=source_language,
                top_depth=top,
                bottom_depth=bottom,
                lithotype_id=lithotype,
                previous_interval=None,
            )
            after_language_revisions = self._language_revisions_after(
                {}, localized_descriptions
            )

        interval = LithologyInterval(
            interval_id=interval_id,
            top_depth=top,
            bottom_depth=bottom,
            lithotype_id=lithotype,
            description=normalized_description,
        )
        if tracking_plan is not None:
            interval.description_i18n.update(localized_descriptions or {})
            if localized_descriptions and "ru" in localized_descriptions:
                interval.description = localized_descriptions["ru"]
            self._apply_translation_plan(
                well,
                tracking_plan,
                after_language_revisions=after_language_revisions or dict(well.language_revisions),
            )
        else:
            if content_language is not None:
                language = normalize_content_language(content_language)
                set_localized_text(
                    interval.description_i18n,
                    language,
                    normalized_description,
                    maximum=4_000,
                )
                if language != "ru":
                    interval.description = None
                self._bump_content(language)
            if localized_descriptions is not None:
                interval.description_i18n.update(localized_descriptions)
                if "ru" in localized_descriptions:
                    interval.description = localized_descriptions["ru"]
                for language in localized_descriptions:
                    if language != "und":
                        self._bump_content(language)
        well.lithology.append(interval)
        after_interval = deepcopy(interval)
        after_tracking = self._tracking_snapshot(interval_id)
        self._record(
            description=f"Добавление литологии {top:g}–{bottom:g} м",
            undo_action=partial(
                self._undo_add,
                interval,
                after_interval,
                position,
                before_tracking,
                after_tracking,
            ),
            redo_action=partial(
                self._redo_add,
                interval,
                after_interval,
                position,
                before_tracking,
                after_tracking,
            ),
        )
        self.session.dirty = True
        return interval

    def update(
        self,
        interval_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        lithotype_id: str,
        description: str | None = None,
        content_language: object | None = None,
        description_i18n: object | None = None,
        source_language: object | None = None,
    ) -> LithologyInterval:
        interval = self._require_interval(interval_id)
        before_interval = deepcopy(interval)
        before_tracking = self._tracking_snapshot(interval_id)
        top, bottom, lithotype, normalized_description = self._validate(
            top_depth,
            bottom_depth,
            lithotype_id,
            description,
        )
        localized_descriptions = self._validate_descriptions(description_i18n)
        self._ensure_no_overlap(top, bottom, excluded_id=interval_id)

        well = self._require_well()
        field_id = self._description_field_id(interval.interval_id)
        persisted_source_language = well.authored_field_source_languages.get(field_id)
        effective_source_language = (
            source_language if source_language is not None else persisted_source_language
        )
        if effective_source_language is not None:
            previous_descriptions = dict(interval.description_i18n)
            current_descriptions = self._tracked_descriptions(
                interval,
                localized_descriptions=localized_descriptions,
                normalized_description=normalized_description,
                content_language=content_language,
                source_language=effective_source_language,
            )
            tracking_plan = self._translation_plan(
                interval.interval_id,
                previous_texts=previous_descriptions,
                current_texts=current_descriptions,
                source_language=effective_source_language,
                top_depth=top,
                bottom_depth=bottom,
                lithotype_id=lithotype,
                previous_interval=interval,
            )
            after_language_revisions = self._language_revisions_after(
                previous_descriptions,
                current_descriptions,
            )
            changed = (
                interval.top_depth != top
                or interval.bottom_depth != bottom
                or interval.lithotype_id != lithotype
                or previous_descriptions != current_descriptions
                or well.translation_statuses != tracking_plan.translation_statuses
                or well.authored_field_revisions != tracking_plan.authored_field_revisions
                or well.authored_field_source_languages
                != tracking_plan.authored_field_source_languages
            )
            if not changed:
                return interval

            interval.top_depth = top
            interval.bottom_depth = bottom
            interval.lithotype_id = lithotype
            interval.description_i18n.clear()
            interval.description_i18n.update(current_descriptions)
            if "ru" in current_descriptions:
                interval.description = current_descriptions["ru"]
            elif "ru" in previous_descriptions:
                interval.description = None
            self._apply_translation_plan(
                well,
                tracking_plan,
                after_language_revisions=after_language_revisions,
            )
            self._record_update_if_changed(
                interval,
                before_interval,
                before_tracking,
            )
            self.session.dirty = True
            return interval

        interval.top_depth = top
        interval.bottom_depth = bottom
        interval.lithotype_id = lithotype
        if content_language is None and description_i18n is None:
            interval.description = normalized_description
        elif content_language is not None:
            language = normalize_content_language(content_language)
            set_localized_text(
                interval.description_i18n,
                language,
                normalized_description,
                maximum=4_000,
            )
            if language == "ru":
                interval.description = normalized_description
            self._bump_content(language)
        if localized_descriptions is not None:
            previous_languages = set(interval.description_i18n)
            interval.description_i18n.clear()
            interval.description_i18n.update(localized_descriptions)
            if "ru" in localized_descriptions:
                interval.description = localized_descriptions["ru"]
            elif "ru" in previous_languages:
                interval.description = None
            for language in previous_languages | set(localized_descriptions):
                if language != "und":
                    self._bump_content(language)
        self._record_update_if_changed(
            interval,
            before_interval,
            before_tracking,
        )
        self.session.dirty = True
        return interval

    def remove(self, interval_id: str) -> LithologyInterval:
        well = self._require_well()
        interval = self._require_interval(interval_id)
        position = well.lithology.index(interval)
        before_interval = deepcopy(interval)
        before_tracking = self._tracking_snapshot(interval_id)
        well.lithology.remove(interval)
        field_id = self._description_field_id(interval.interval_id)
        well.translation_statuses.pop(field_id, None)
        well.authored_field_source_languages.pop(field_id, None)
        for revision_id in (
            field_id,
            self._depth_dependency_id(interval.interval_id),
            self._lithotype_dependency_id(interval.interval_id),
        ):
            well.authored_field_revisions.pop(revision_id, None)
        after_tracking = self._tracking_snapshot(interval_id)
        self._record(
            description=f"Удаление литологии {interval.top_depth:g}–{interval.bottom_depth:g} м",
            undo_action=partial(
                self._undo_remove,
                interval,
                before_interval,
                position,
                before_tracking,
                after_tracking,
            ),
            redo_action=partial(
                self._redo_remove,
                interval,
                before_interval,
                before_tracking,
                after_tracking,
            ),
        )
        self.session.dirty = True
        return interval

    def undo(self) -> str:
        if not self.can_undo:
            raise RuntimeError("Нет изменений литологии для отмены")
        command = self._history.undo()
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        if not self.can_redo:
            raise RuntimeError("Нет изменений литологии для повтора")
        command = self._history.redo()
        self.session.dirty = True
        return command.description

    def clear_history(self) -> None:
        self._history.clear()

    def _record_update_if_changed(
        self,
        interval: LithologyInterval,
        before_interval: LithologyInterval,
        before_tracking: _LithologyTrackingSnapshot,
    ) -> None:
        after_interval = deepcopy(interval)
        after_tracking = self._tracking_snapshot(interval.interval_id)
        if before_interval == after_interval and before_tracking == after_tracking:
            return
        self._record(
            description=f"Изменение литологии {interval.top_depth:g}–{interval.bottom_depth:g} м",
            undo_action=partial(
                self._restore_update,
                interval,
                after_interval,
                before_interval,
                after_tracking,
                before_tracking,
            ),
            redo_action=partial(
                self._restore_update,
                interval,
                before_interval,
                after_interval,
                before_tracking,
                after_tracking,
            ),
        )

    def _record(
        self,
        *,
        description: str,
        undo_action: Callable[[], None],
        redo_action: Callable[[], None],
    ) -> None:
        self._history.record_applied(
            CallbackCommand(
                description=description,
                history_domain=self._HISTORY_DOMAIN,
                execute_action=redo_action,
                undo_action=undo_action,
            )
        )

    def _undo_add(
        self,
        interval: LithologyInterval,
        expected_interval: LithologyInterval,
        position: int,
        before_tracking: _LithologyTrackingSnapshot,
        after_tracking: _LithologyTrackingSnapshot,
    ) -> None:
        del position
        well = self._require_well()
        current = self._require_interval(interval.interval_id)
        if current is not interval or current != expected_interval:
            raise RuntimeError("Литологический интервал был изменён вне истории команд")
        self._assert_tracking(interval.interval_id, after_tracking)
        well.lithology.remove(interval)
        self._restore_tracking(interval.interval_id, before_tracking)
        self.session.dirty = True

    def _redo_add(
        self,
        interval: LithologyInterval,
        expected_interval: LithologyInterval,
        position: int,
        before_tracking: _LithologyTrackingSnapshot,
        after_tracking: _LithologyTrackingSnapshot,
    ) -> None:
        well = self._require_well()
        if any(item.interval_id == interval.interval_id for item in well.lithology):
            raise RuntimeError("Литологический интервал уже существует вне истории команд")
        self._assert_tracking(interval.interval_id, before_tracking)
        self._ensure_no_overlap(
            expected_interval.top_depth,
            expected_interval.bottom_depth,
        )
        self._commit_interval(interval, expected_interval)
        well.lithology.insert(min(position, len(well.lithology)), interval)
        self._restore_tracking(interval.interval_id, after_tracking)
        self.session.dirty = True

    def _restore_update(
        self,
        interval: LithologyInterval,
        expected_interval: LithologyInterval,
        replacement_interval: LithologyInterval,
        expected_tracking: _LithologyTrackingSnapshot,
        replacement_tracking: _LithologyTrackingSnapshot,
    ) -> None:
        current = self._require_interval(interval.interval_id)
        if current is not interval or current != expected_interval:
            raise RuntimeError("Литологический интервал был изменён вне истории команд")
        self._assert_tracking(interval.interval_id, expected_tracking)
        self._ensure_no_overlap(
            replacement_interval.top_depth,
            replacement_interval.bottom_depth,
            excluded_id=interval.interval_id,
        )
        self._commit_interval(interval, replacement_interval)
        self._restore_tracking(interval.interval_id, replacement_tracking)
        self.session.dirty = True

    def _undo_remove(
        self,
        interval: LithologyInterval,
        expected_interval: LithologyInterval,
        position: int,
        before_tracking: _LithologyTrackingSnapshot,
        after_tracking: _LithologyTrackingSnapshot,
    ) -> None:
        well = self._require_well()
        if any(item.interval_id == interval.interval_id for item in well.lithology):
            raise RuntimeError("Удалённый литологический интервал уже восстановлен вне истории")
        self._assert_tracking(interval.interval_id, after_tracking)
        self._ensure_no_overlap(
            expected_interval.top_depth,
            expected_interval.bottom_depth,
        )
        self._commit_interval(interval, expected_interval)
        well.lithology.insert(min(position, len(well.lithology)), interval)
        self._restore_tracking(interval.interval_id, before_tracking)
        self.session.dirty = True

    def _redo_remove(
        self,
        interval: LithologyInterval,
        expected_interval: LithologyInterval,
        before_tracking: _LithologyTrackingSnapshot,
        after_tracking: _LithologyTrackingSnapshot,
    ) -> None:
        well = self._require_well()
        current = self._require_interval(interval.interval_id)
        if current is not interval or current != expected_interval:
            raise RuntimeError("Литологический интервал был изменён вне истории команд")
        self._assert_tracking(interval.interval_id, before_tracking)
        well.lithology.remove(interval)
        self._restore_tracking(interval.interval_id, after_tracking)
        self.session.dirty = True

    def _tracking_snapshot(self, interval_id: str) -> _LithologyTrackingSnapshot:
        well = self._require_well()
        field_ids = (
            self._description_field_id(interval_id),
            self._depth_dependency_id(interval_id),
            self._lithotype_dependency_id(interval_id),
        )
        description_id = field_ids[0]
        return _LithologyTrackingSnapshot(
            translation_statuses=(
                {description_id: deepcopy(well.translation_statuses[description_id])}
                if description_id in well.translation_statuses
                else {}
            ),
            authored_field_revisions={
                key: well.authored_field_revisions[key]
                for key in field_ids
                if key in well.authored_field_revisions
            },
            authored_field_source_languages=(
                {
                    description_id: well.authored_field_source_languages[description_id]
                }
                if description_id in well.authored_field_source_languages
                else {}
            ),
            language_revisions=dict(well.language_revisions),
            content_revision=well.content_revision,
        )

    def _assert_tracking(
        self,
        interval_id: str,
        expected: _LithologyTrackingSnapshot,
    ) -> None:
        if self._tracking_snapshot(interval_id) != expected:
            raise RuntimeError("Метаданные перевода литологии изменены вне истории команд")

    def _restore_tracking(
        self,
        interval_id: str,
        snapshot: _LithologyTrackingSnapshot,
    ) -> None:
        well = self._require_well()
        field_ids = (
            self._description_field_id(interval_id),
            self._depth_dependency_id(interval_id),
            self._lithotype_dependency_id(interval_id),
        )
        description_id = field_ids[0]
        well.translation_statuses.pop(description_id, None)
        well.translation_statuses.update(deepcopy(snapshot.translation_statuses))
        well.authored_field_source_languages.pop(description_id, None)
        well.authored_field_source_languages.update(
            snapshot.authored_field_source_languages
        )
        for key in field_ids:
            well.authored_field_revisions.pop(key, None)
        well.authored_field_revisions.update(snapshot.authored_field_revisions)
        well.language_revisions = dict(snapshot.language_revisions)
        well.content_revision = snapshot.content_revision

    @staticmethod
    def _commit_interval(
        target: LithologyInterval,
        source: LithologyInterval,
    ) -> None:
        for model_field in fields(LithologyInterval):
            setattr(target, model_field.name, deepcopy(getattr(source, model_field.name)))

    def _tracked_descriptions(
        self,
        interval: LithologyInterval,
        *,
        localized_descriptions: dict[str, str] | None,
        normalized_description: str | None,
        content_language: object | None,
        source_language: object,
    ) -> dict[str, str]:
        if localized_descriptions is not None:
            return dict(localized_descriptions)
        descriptions = dict(interval.description_i18n)
        if content_language is not None:
            set_localized_text(
                descriptions,
                content_language,
                normalized_description,
                maximum=4_000,
            )
            return descriptions
        if normalized_description is None:
            return descriptions
        normalized_source_language = normalize_content_language(source_language)
        if normalized_source_language != "ru":
            raise ValueError(
                "Для отслеживаемого поля с нерусским оригиналом укажите content_language "
                "или description_i18n"
            )
        set_localized_text(
            descriptions,
            "ru",
            normalized_description,
            maximum=4_000,
        )
        return descriptions

    def _translation_plan(
        self,
        interval_id: str,
        *,
        previous_texts: dict[str, str],
        current_texts: dict[str, str],
        source_language: object,
        top_depth: float,
        bottom_depth: float,
        lithotype_id: str,
        previous_interval: LithologyInterval | None,
    ) -> AuthoredTranslationPlan:
        well = self._require_well()
        revisions = dict(well.authored_field_revisions)
        depth_id = self._depth_dependency_id(interval_id)
        lithotype_dependency_id = self._lithotype_dependency_id(interval_id)

        depth_changed = (
            previous_interval is None
            or previous_interval.top_depth != top_depth
            or previous_interval.bottom_depth != bottom_depth
        )
        lithotype_changed = (
            previous_interval is None or previous_interval.lithotype_id != lithotype_id
        )
        if depth_changed or revisions.get(depth_id, 0) == 0:
            revisions[depth_id] = revisions.get(depth_id, 0) + 1
        if lithotype_changed or revisions.get(lithotype_dependency_id, 0) == 0:
            revisions[lithotype_dependency_id] = revisions.get(lithotype_dependency_id, 0) + 1

        dependencies = {
            depth_id: revisions[depth_id],
            lithotype_dependency_id: revisions[lithotype_dependency_id],
        }
        return AuthoredTranslationWorkflow.plan(
            well.translation_statuses,
            revisions,
            well.authored_field_source_languages,
            field_id=self._description_field_id(interval_id),
            previous_texts=previous_texts,
            current_texts=current_texts,
            source_language=source_language,
            dependency_revisions=dependencies,
        )

    def _language_revisions_after(
        self,
        previous_texts: dict[str, str],
        current_texts: dict[str, str],
    ) -> dict[str, int]:
        revisions = dict(self._require_well().language_revisions)
        for language in SUPPORTED_CONTENT_LANGUAGES:
            if previous_texts.get(language) != current_texts.get(language):
                bump_language_revision(revisions, language)
        return revisions

    def _apply_translation_plan(
        self,
        well: Well,
        plan: AuthoredTranslationPlan,
        *,
        after_language_revisions: dict[str, int],
    ) -> None:
        well.translation_statuses = plan.translation_statuses
        well.authored_field_revisions = plan.authored_field_revisions
        well.authored_field_source_languages = plan.authored_field_source_languages
        well.language_revisions = after_language_revisions
        well.content_revision += 1

    @staticmethod
    def _description_field_id(interval_id: str) -> str:
        return f"lithology/{interval_id}/description"

    @staticmethod
    def _depth_dependency_id(interval_id: str) -> str:
        return f"lithology/{interval_id}/depth"

    @staticmethod
    def _lithotype_dependency_id(interval_id: str) -> str:
        return f"lithology/{interval_id}/lithotype"

    def _validate(
        self,
        top_depth: float,
        bottom_depth: float,
        lithotype_id: str,
        description: str | None,
    ) -> tuple[float, float, str, str | None]:
        top = float(top_depth)
        bottom = float(bottom_depth)
        if not np.isfinite(top) or not np.isfinite(bottom):
            raise ValueError("Границы литологического интервала должны быть конечными")
        if top >= bottom:
            raise ValueError("Кровля интервала должна быть меньше подошвы")
        lithotype = lithotype_id.strip()
        if not lithotype:
            raise ValueError("Идентификатор литотипа не может быть пустым")
        if len(lithotype) > 100:
            raise ValueError("Идентификатор литотипа не должен превышать 100 символов")
        normalized_description = description.strip() if description else None
        if normalized_description and len(normalized_description) > 4000:
            raise ValueError("Описание литологии не должно превышать 4000 символов")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size and (
                top < float(np.min(finite_depth)) or bottom > float(np.max(finite_depth))
            ):
                raise ValueError("Литологический интервал выходит за диапазон dataset")
        return top, bottom, lithotype, normalized_description

    @staticmethod
    def _validate_descriptions(value: object | None) -> dict[str, str] | None:
        if value is None:
            return None
        return validate_localized_texts(
            value,  # type: ignore[arg-type]
            maximum=4_000,
            allow_undetermined=True,
        )

    def _ensure_no_overlap(
        self,
        top: float,
        bottom: float,
        *,
        excluded_id: str | None = None,
    ) -> None:
        for interval in self._require_well().lithology:
            if interval.interval_id == excluded_id:
                continue
            if top < interval.bottom_depth and bottom > interval.top_depth:
                raise ValueError(
                    f"Интервал пересекается с существующим: "
                    f"{interval.top_depth:g}–{interval.bottom_depth:g}"
                )

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _bump_content(self, language: object) -> None:
        well = self._require_well()
        well.content_revision += 1
        bump_language_revision(well.language_revisions, language)

    def _require_interval(self, interval_id: str) -> LithologyInterval:
        for interval in self._require_well().lithology:
            if interval.interval_id == interval_id:
                return interval
        raise KeyError(f"Литологический интервал не найден: {interval_id}")
