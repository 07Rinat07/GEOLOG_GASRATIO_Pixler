from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
import re

import numpy as np

from geoworkbench.domain.authored_translation_tracking import AuthoredTranslationPlan
from geoworkbench.domain.localized_content import (
    SUPPORTED_CONTENT_LANGUAGES,
    bump_language_revision,
    normalize_content_language,
    set_localized_text,
    validate_localized_texts,
)
from geoworkbench.domain.models import StratigraphyInterval, Well, new_id
from geoworkbench.domain.stratigraphy_description_tracking import (
    StratigraphyDescriptionTrackingWorkflow,
)
from geoworkbench.domain.stratigraphy_presentation import (
    STRATIGRAPHY_TEXT_ORIENTATIONS,
    STRATIGRAPHY_TEXT_POSITIONS,
    normalize_stratigraphy_text_orientation,
    normalize_stratigraphy_text_position,
    stratigraphy_text_anchor,
    stratigraphy_text_angle,
    stratigraphy_text_position_fraction,
)
from geoworkbench.project.session import ProjectSession


__all__ = [
    "STRATIGRAPHY_RANKS",
    "STRATIGRAPHY_TEXT_ORIENTATIONS",
    "STRATIGRAPHY_TEXT_POSITIONS",
    "StratigraphyController",
    "normalize_stratigraphy_text_orientation",
    "normalize_stratigraphy_text_position",
    "stratigraphy_rank_order",
    "stratigraphy_text_anchor",
    "stratigraphy_text_angle",
    "stratigraphy_text_position_fraction",
]

STRATIGRAPHY_RANKS = (
    "Eonothem / Eon",
    "Erathem / Era",
    "System / Period",
    "Series / Epoch",
    "Stage / Age",
    "Formation",
    "Member",
    "Bed",
)


def stratigraphy_rank_order(rank: str | None) -> tuple[int, str]:
    normalized = (rank or "").strip()
    try:
        return STRATIGRAPHY_RANKS.index(normalized), normalized.casefold()
    except ValueError:
        return len(STRATIGRAPHY_RANKS), normalized.casefold()


@dataclass(slots=True)
class StratigraphyController:
    session: ProjectSession

    def available(self) -> tuple[StratigraphyInterval, ...]:
        return tuple(
            sorted(
                self._require_well().stratigraphy,
                key=lambda item: (
                    stratigraphy_rank_order(item.rank),
                    item.top_depth,
                    item.bottom_depth,
                    item.interval_id,
                ),
            )
        )

    def get(self, interval_id: str) -> StratigraphyInterval:
        """Return one editable stratigraphic interval by stable project ID."""

        return self._require_interval(interval_id)

    def description_source_language(self, interval_id: str) -> str | None:
        interval = self._require_interval(interval_id)
        field_id = StratigraphyDescriptionTrackingWorkflow.field_id(interval.interval_id)
        return self._require_well().authored_field_source_languages.get(field_id)

    def add(
        self,
        top_depth: float,
        bottom_depth: float,
        code: str,
        *,
        name: str | None = None,
        rank: str | None = None,
        color: str = "#dbeafe",
        description: str | None = None,
        text_orientation: str = "horizontal",
        text_position: str = "center",
        content_language: object | None = None,
        name_i18n: object | None = None,
        description_i18n: object | None = None,
        description_source_language: object | None = None,
    ) -> StratigraphyInterval:
        values = self._validate(
            top_depth,
            bottom_depth,
            code,
            name,
            rank,
            color,
            description,
            text_orientation,
            text_position,
        )
        localized_names = self._validate_localized(name_i18n, 300)
        localized_descriptions = self._validate_localized(description_i18n, 4_000)
        self._ensure_no_overlap(values[0], values[1], values[4])
        interval_id = new_id()
        well = self._require_well()

        if description_source_language is not None:
            if localized_descriptions is None:
                raise ValueError("Для языка оригинала требуется многоязычное описание стратиграфии")
            interval = StratigraphyInterval(interval_id, *values)
            self._apply_initial_localized_content(
                interval,
                values=values,
                content_language=content_language,
                localized_names=localized_names,
                localized_descriptions=localized_descriptions,
            )
            plan = self._description_tracking_plan(
                interval_id,
                previous_interval=None,
                current_interval=interval,
                previous_texts={},
                current_texts=dict(interval.description_i18n),
                source_language=description_source_language,
            )
            after_language_revisions = self._language_revisions_after(
                previous_name_texts={},
                current_name_texts=interval.name_i18n,
                previous_description_texts={},
                current_description_texts=interval.description_i18n,
            )
            well.stratigraphy.append(interval)
            self._apply_tracking_plan(
                well,
                plan,
                after_language_revisions=after_language_revisions,
            )
            self.session.dirty = True
            return interval

        interval = StratigraphyInterval(interval_id, *values)
        if content_language is not None:
            language = normalize_content_language(content_language)
            set_localized_text(interval.name_i18n, language, values[3], maximum=300)
            set_localized_text(interval.description_i18n, language, values[6], maximum=4_000)
            if language != "ru":
                interval.name = None
                interval.description = None
            self._bump_content(language)
        if localized_names is not None:
            interval.name_i18n.update(localized_names)
            if "ru" in localized_names:
                interval.name = localized_names["ru"]
        if localized_descriptions is not None:
            interval.description_i18n.update(localized_descriptions)
            if "ru" in localized_descriptions:
                interval.description = localized_descriptions["ru"]
        for language in set(localized_names or ()) | set(localized_descriptions or ()):
            if language != "und":
                self._bump_content(language)
        well.stratigraphy.append(interval)
        self.session.dirty = True
        return interval

    def update(
        self,
        interval_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        code: str,
        name: str | None = None,
        rank: str | None = None,
        color: str = "#dbeafe",
        description: str | None = None,
        text_orientation: str = "horizontal",
        text_position: str = "center",
        content_language: object | None = None,
        name_i18n: object | None = None,
        description_i18n: object | None = None,
        description_source_language: object | None = None,
    ) -> StratigraphyInterval:
        interval = self._require_interval(interval_id)
        values = self._validate(
            top_depth,
            bottom_depth,
            code,
            name,
            rank,
            color,
            description,
            text_orientation,
            text_position,
        )
        localized_names = self._validate_localized(name_i18n, 300)
        localized_descriptions = self._validate_localized(description_i18n, 4_000)
        self._ensure_no_overlap(values[0], values[1], values[4], excluded_id=interval_id)

        well = self._require_well()
        persisted_source_language = self.description_source_language(interval_id)
        effective_source_language = (
            description_source_language
            if description_source_language is not None
            else persisted_source_language
        )
        if effective_source_language is not None:
            previous = deepcopy(interval)
            staged = deepcopy(interval)
            self._apply_structural_values(staged, values)
            self._apply_tracked_name_values(
                staged,
                values=values,
                content_language=content_language,
                localized_names=localized_names,
            )
            current_descriptions = self._tracked_descriptions(
                interval,
                localized_descriptions=localized_descriptions,
                normalized_description=values[6],
                content_language=content_language,
                source_language=effective_source_language,
            )
            staged.description_i18n.clear()
            staged.description_i18n.update(current_descriptions)
            staged.description = current_descriptions.get("ru")

            plan = self._description_tracking_plan(
                interval.interval_id,
                previous_interval=previous,
                current_interval=staged,
                previous_texts=dict(previous.description_i18n),
                current_texts=current_descriptions,
                source_language=effective_source_language,
            )
            after_language_revisions = self._language_revisions_after(
                previous_name_texts=previous.name_i18n,
                current_name_texts=staged.name_i18n,
                previous_description_texts=previous.description_i18n,
                current_description_texts=staged.description_i18n,
            )
            changed = (
                previous != staged
                or well.translation_statuses != plan.translation_statuses
                or well.authored_field_revisions != plan.authored_field_revisions
                or well.authored_field_source_languages
                != plan.authored_field_source_languages
            )
            if not changed:
                return interval

            self._commit_interval(interval, staged)
            self._apply_tracking_plan(
                well,
                plan,
                after_language_revisions=after_language_revisions,
            )
            self.session.dirty = True
            return interval

        interval.top_depth = values[0]
        interval.bottom_depth = values[1]
        interval.code = values[2]
        interval.rank = values[4]
        interval.color = values[5]
        interval.text_orientation = values[7]
        interval.text_position = values[8]
        if content_language is None and name_i18n is None:
            interval.name = values[3]
        if content_language is None and description_i18n is None:
            interval.description = values[6]
        if content_language is not None:
            language = normalize_content_language(content_language)
            set_localized_text(interval.name_i18n, language, values[3], maximum=300)
            set_localized_text(interval.description_i18n, language, values[6], maximum=4_000)
            if language == "ru":
                interval.name = values[3]
                interval.description = values[6]
            self._bump_content(language)
        changed_languages: set[str] = set()
        if localized_names is not None:
            previous_languages = set(interval.name_i18n)
            interval.name_i18n.clear()
            interval.name_i18n.update(localized_names)
            if "ru" in localized_names:
                interval.name = localized_names["ru"]
            elif "ru" in previous_languages:
                interval.name = None
            changed_languages |= previous_languages | set(localized_names)
        if localized_descriptions is not None:
            previous_languages = set(interval.description_i18n)
            interval.description_i18n.clear()
            interval.description_i18n.update(localized_descriptions)
            if "ru" in localized_descriptions:
                interval.description = localized_descriptions["ru"]
            elif "ru" in previous_languages:
                interval.description = None
            changed_languages |= previous_languages | set(localized_descriptions)
        for language in changed_languages:
            if language != "und":
                self._bump_content(language)
        self.session.dirty = True
        return interval

    def remove(self, interval_id: str) -> StratigraphyInterval:
        well = self._require_well()
        interval = self._require_interval(interval_id)
        well.stratigraphy.remove(interval)
        field_id = StratigraphyDescriptionTrackingWorkflow.field_id(interval.interval_id)
        well.translation_statuses.pop(field_id, None)
        well.authored_field_source_languages.pop(field_id, None)
        for revision_id in (
            field_id,
            StratigraphyDescriptionTrackingWorkflow.depth_dependency_id(interval.interval_id),
            StratigraphyDescriptionTrackingWorkflow.classification_dependency_id(
                interval.interval_id
            ),
        ):
            well.authored_field_revisions.pop(revision_id, None)
        self.session.dirty = True
        return interval

    @staticmethod
    def _validate_localized(value: object | None, maximum: int) -> dict[str, str] | None:
        if value is None:
            return None
        return validate_localized_texts(
            value,  # type: ignore[arg-type]
            maximum=maximum,
            allow_undetermined=True,
        )

    def _apply_initial_localized_content(
        self,
        interval: StratigraphyInterval,
        *,
        values: tuple[
            float,
            float,
            str,
            str | None,
            str | None,
            str,
            str | None,
            str,
            str,
        ],
        content_language: object | None,
        localized_names: dict[str, str] | None,
        localized_descriptions: dict[str, str],
    ) -> None:
        if content_language is not None:
            language = normalize_content_language(content_language)
            set_localized_text(interval.name_i18n, language, values[3], maximum=300)
            set_localized_text(interval.description_i18n, language, values[6], maximum=4_000)
            if language != "ru":
                interval.name = None
                interval.description = None
        if localized_names is not None:
            interval.name_i18n.clear()
            interval.name_i18n.update(localized_names)
            interval.name = localized_names.get("ru")
        interval.description_i18n.clear()
        interval.description_i18n.update(localized_descriptions)
        interval.description = localized_descriptions.get("ru")

    @staticmethod
    def _apply_structural_values(
        interval: StratigraphyInterval,
        values: tuple[
            float,
            float,
            str,
            str | None,
            str | None,
            str,
            str | None,
            str,
            str,
        ],
    ) -> None:
        interval.top_depth = values[0]
        interval.bottom_depth = values[1]
        interval.code = values[2]
        interval.rank = values[4]
        interval.color = values[5]
        interval.text_orientation = values[7]
        interval.text_position = values[8]

    def _apply_tracked_name_values(
        self,
        interval: StratigraphyInterval,
        *,
        values: tuple[
            float,
            float,
            str,
            str | None,
            str | None,
            str,
            str | None,
            str,
            str,
        ],
        content_language: object | None,
        localized_names: dict[str, str] | None,
    ) -> None:
        if content_language is None and localized_names is None:
            interval.name = values[3]
            return
        if content_language is not None:
            language = normalize_content_language(content_language)
            set_localized_text(interval.name_i18n, language, values[3], maximum=300)
            if language == "ru":
                interval.name = values[3]
        if localized_names is not None:
            previous_languages = set(interval.name_i18n)
            interval.name_i18n.clear()
            interval.name_i18n.update(localized_names)
            if "ru" in localized_names:
                interval.name = localized_names["ru"]
            elif "ru" in previous_languages:
                interval.name = None

    def _tracked_descriptions(
        self,
        interval: StratigraphyInterval,
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
                "Для отслеживаемого стратиграфического описания с нерусским оригиналом "
                "укажите content_language или description_i18n"
            )
        set_localized_text(descriptions, "ru", normalized_description, maximum=4_000)
        return descriptions

    def _description_tracking_plan(
        self,
        interval_id: str,
        *,
        previous_interval: StratigraphyInterval | None,
        current_interval: StratigraphyInterval,
        previous_texts: dict[str, str],
        current_texts: dict[str, str],
        source_language: object,
    ) -> AuthoredTranslationPlan:
        well = self._require_well()
        return StratigraphyDescriptionTrackingWorkflow.plan(
            well.translation_statuses,
            well.authored_field_revisions,
            well.authored_field_source_languages,
            interval_id=interval_id,
            previous_depth=(
                (previous_interval.top_depth, previous_interval.bottom_depth)
                if previous_interval is not None
                else None
            ),
            current_depth=(current_interval.top_depth, current_interval.bottom_depth),
            previous_classification=(
                (previous_interval.code, previous_interval.rank)
                if previous_interval is not None
                else None
            ),
            current_classification=(current_interval.code, current_interval.rank),
            previous_texts=previous_texts,
            current_texts=current_texts,
            source_language=source_language,
        )

    def _language_revisions_after(
        self,
        *,
        previous_name_texts: dict[str, str],
        current_name_texts: dict[str, str],
        previous_description_texts: dict[str, str],
        current_description_texts: dict[str, str],
    ) -> dict[str, int]:
        revisions = dict(self._require_well().language_revisions)
        for language in SUPPORTED_CONTENT_LANGUAGES:
            name_changed = previous_name_texts.get(language) != current_name_texts.get(language)
            description_changed = (
                previous_description_texts.get(language)
                != current_description_texts.get(language)
            )
            if name_changed or description_changed:
                bump_language_revision(revisions, language)
        return revisions

    @staticmethod
    def _commit_interval(target: StratigraphyInterval, staged: StratigraphyInterval) -> None:
        for field_info in fields(StratigraphyInterval):
            setattr(target, field_info.name, deepcopy(getattr(staged, field_info.name)))

    @staticmethod
    def _apply_tracking_plan(
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

    def _validate(
        self,
        top_depth: float,
        bottom_depth: float,
        code: str,
        name: str | None,
        rank: str | None,
        color: str,
        description: str | None,
        text_orientation: str,
        text_position: str,
    ) -> tuple[
        float,
        float,
        str,
        str | None,
        str | None,
        str,
        str | None,
        str,
        str,
    ]:
        top, bottom = float(top_depth), float(bottom_depth)
        if not np.isfinite(top) or not np.isfinite(bottom) or top >= bottom:
            raise ValueError("Кровля стратиграфического интервала должна быть меньше подошвы")
        normalized_code = code.strip()
        if not normalized_code or len(normalized_code) > 100:
            raise ValueError(
                "Код стратиграфического интервала обязателен и не длиннее 100 символов"
            )
        normalized_name = self._optional_text(name, 300, "Название")
        normalized_rank = self._optional_text(rank, 100, "Ранг")
        normalized_color = color.strip().lower()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", normalized_color):
            raise ValueError("Цвет стратиграфии должен быть в формате #RRGGBB")
        normalized_description = self._optional_text(description, 4000, "Описание")
        normalized_orientation = normalize_stratigraphy_text_orientation(text_orientation)
        normalized_position = normalize_stratigraphy_text_position(text_position)
        dataset = self.session.current_dataset
        if dataset is not None:
            finite = dataset.depth[np.isfinite(dataset.depth)]
            if finite.size and (top < float(np.min(finite)) or bottom > float(np.max(finite))):
                raise ValueError("Стратиграфический интервал выходит за диапазон dataset")
        return (
            top,
            bottom,
            normalized_code,
            normalized_name,
            normalized_rank,
            normalized_color,
            normalized_description,
            normalized_orientation,
            normalized_position,
        )

    @staticmethod
    def _optional_text(value: str | None, maximum: int, label: str) -> str | None:
        normalized = value.strip() if value else None
        if normalized and len(normalized) > maximum:
            raise ValueError(f"{label} не должно превышать {maximum} символов")
        return normalized

    def _ensure_no_overlap(
        self,
        top: float,
        bottom: float,
        rank: str | None,
        *,
        excluded_id: str | None = None,
    ) -> None:
        rank_key = (rank or "").strip().casefold()
        for interval in self._require_well().stratigraphy:
            existing_rank_key = (interval.rank or "").strip().casefold()
            if interval.interval_id == excluded_id or existing_rank_key != rank_key:
                continue
            if top < interval.bottom_depth and bottom > interval.top_depth:
                raise ValueError(
                    f"Интервал пересекается с {interval.code} того же ранга: "
                    f"{interval.top_depth:g}–{interval.bottom_depth:g} м"
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

    def _require_interval(self, interval_id: str) -> StratigraphyInterval:
        for interval in self._require_well().stratigraphy:
            if interval.interval_id == interval_id:
                return interval
        raise KeyError(f"Стратиграфический интервал не найден: {interval_id}")
