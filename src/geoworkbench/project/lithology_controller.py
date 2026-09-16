from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(slots=True)
class LithologyController:
    session: ProjectSession

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
        top, bottom, lithotype, normalized_description = self._validate(
            top_depth,
            bottom_depth,
            lithotype_id,
            description,
        )
        localized_descriptions = self._validate_descriptions(description_i18n)
        self._ensure_no_overlap(top, bottom, excluded_id=interval_id)

        if source_language is not None:
            if localized_descriptions is None:
                raise ValueError("Для языка оригинала требуется многоязычное описание")
            well = self._require_well()
            previous_descriptions = dict(interval.description_i18n)
            tracking_plan = self._translation_plan(
                interval.interval_id,
                previous_texts=previous_descriptions,
                current_texts=localized_descriptions,
                source_language=source_language,
                top_depth=top,
                bottom_depth=bottom,
                lithotype_id=lithotype,
                previous_interval=interval,
            )
            after_language_revisions = self._language_revisions_after(
                previous_descriptions,
                localized_descriptions,
            )
            changed = (
                interval.top_depth != top
                or interval.bottom_depth != bottom
                or interval.lithotype_id != lithotype
                or previous_descriptions != localized_descriptions
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
            interval.description_i18n.update(localized_descriptions)
            if "ru" in localized_descriptions:
                interval.description = localized_descriptions["ru"]
            elif "ru" in previous_descriptions:
                interval.description = None
            self._apply_translation_plan(
                well,
                tracking_plan,
                after_language_revisions=after_language_revisions,
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
        self.session.dirty = True
        return interval

    def remove(self, interval_id: str) -> LithologyInterval:
        well = self._require_well()
        interval = self._require_interval(interval_id)
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
        self.session.dirty = True
        return interval

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
