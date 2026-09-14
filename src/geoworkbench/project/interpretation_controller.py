from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import re

import numpy as np

from geoworkbench.data.interpretation_export import (
    export_interpretation_csv,
    export_interpretation_excel,
    export_interpretation_json,
)
from geoworkbench.domain.models import (
    InterpretationInterval,
    Well,
    WellInterpretation,
    new_id,
)
from geoworkbench.domain.localized_content import (
    bump_language_revision,
    validate_localized_texts,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.interpretation_history import InterpretationHistory


@dataclass(slots=True)
class InterpretationController:
    session: ProjectSession
    history: InterpretationHistory = field(default_factory=InterpretationHistory)
    selected_interpretation_id: str | None = None
    selected_interval_id: str | None = None

    @property
    def can_undo(self) -> bool:
        return self.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self.history.can_redo

    def available_interpretations(self) -> tuple[WellInterpretation, ...]:
        well = self._require_well()
        return tuple(sorted(well.interpretations.values(), key=lambda item: item.name.casefold()))

    def select_interpretation(self, interpretation_id: str) -> WellInterpretation:
        interpretation = self._require_interpretation(interpretation_id)
        self.selected_interpretation_id = interpretation.interpretation_id
        if not any(
            item.interval_id == self.selected_interval_id for item in interpretation.intervals
        ):
            self.selected_interval_id = None
        return interpretation

    def select_interval(self, interpretation_id: str, interval_id: str) -> InterpretationInterval:
        interpretation = self.select_interpretation(interpretation_id)
        for interval in interpretation.intervals:
            if interval.interval_id == interval_id:
                self.selected_interval_id = interval_id
                return interval
        raise KeyError(f"Интервал интерпретации не найден: {interval_id}")

    def selected_interval(self) -> InterpretationInterval | None:
        try:
            interpretation = self.current_interpretation()
        except RuntimeError:
            return None
        for interval in interpretation.intervals:
            if interval.interval_id == self.selected_interval_id:
                return interval
        return None

    def reset_state(self) -> None:
        self.history.clear()
        self.selected_interpretation_id = None
        self.selected_interval_id = None

    def normalize_selection(self) -> None:
        """Normalize selected IDs after switching the current project well."""
        if self.session.current_well is None:
            self.selected_interpretation_id = None
            self.selected_interval_id = None
            return
        self._normalize_selection()

    def current_interpretation(self) -> WellInterpretation:
        well = self._require_well()
        if self.selected_interpretation_id in well.interpretations:
            return well.interpretations[self.selected_interpretation_id]
        if not well.interpretations:
            raise RuntimeError("Сначала создайте интерпретацию")
        interpretation = min(well.interpretations.values(), key=lambda item: item.name.casefold())
        self.selected_interpretation_id = interpretation.interpretation_id
        return interpretation

    def add_interpretation(
        self,
        name: str,
        *,
        description: str | None = None,
        name_i18n: object | None = None,
        description_i18n: object | None = None,
    ) -> WellInterpretation:
        normalized_name, normalized_description = self._validate_interpretation(name, description)
        localized_names = self._validate_localized(name_i18n, maximum=200)
        localized_descriptions = self._validate_localized(description_i18n, maximum=4_000)
        if localized_names and "ru" in localized_names:
            normalized_name = localized_names["ru"]
        if localized_descriptions and "ru" in localized_descriptions:
            normalized_description = localized_descriptions["ru"]
        well = self._require_well()
        if any(
            item.name.casefold() == normalized_name.casefold()
            for item in well.interpretations.values()
        ):
            raise ValueError(f"Интерпретация уже существует: {normalized_name}")
        before = deepcopy(well.interpretations)
        interpretation = WellInterpretation(
            interpretation_id=new_id(),
            name=normalized_name,
            description=normalized_description,
            name_i18n=localized_names or {},
            description_i18n=localized_descriptions or {},
        )
        well.interpretations[interpretation.interpretation_id] = interpretation
        self.selected_interpretation_id = interpretation.interpretation_id
        self.selected_interval_id = None
        self._record(well, before, "Добавление интерпретации")
        self._bump_languages(set(localized_names or ()) | set(localized_descriptions or ()))
        return interpretation

    def update_interpretation(
        self,
        interpretation_id: str,
        *,
        name: str,
        description: str | None = None,
        name_i18n: object | None = None,
        description_i18n: object | None = None,
    ) -> WellInterpretation:
        normalized_name, normalized_description = self._validate_interpretation(name, description)
        localized_names = self._validate_localized(name_i18n, maximum=200)
        localized_descriptions = self._validate_localized(description_i18n, maximum=4_000)
        if localized_names and "ru" in localized_names:
            normalized_name = localized_names["ru"]
        if localized_descriptions and "ru" in localized_descriptions:
            normalized_description = localized_descriptions["ru"]
        well = self._require_well()
        interpretation = self._require_interpretation(interpretation_id)
        if any(
            item.interpretation_id != interpretation_id
            and item.name.casefold() == normalized_name.casefold()
            for item in well.interpretations.values()
        ):
            raise ValueError(f"Интерпретация уже существует: {normalized_name}")
        before = deepcopy(well.interpretations)
        interpretation.name = normalized_name
        interpretation.description = normalized_description
        changed_languages: set[str] = set()
        if localized_names is not None:
            changed_languages |= set(interpretation.name_i18n) | set(localized_names)
            interpretation.name_i18n = localized_names
        if localized_descriptions is not None:
            changed_languages |= set(interpretation.description_i18n) | set(localized_descriptions)
            interpretation.description_i18n = localized_descriptions
        self._record(well, before, "Изменение интерпретации")
        self._bump_languages(changed_languages)
        return interpretation

    def remove_interpretation(self, interpretation_id: str) -> WellInterpretation:
        well = self._require_well()
        self._require_interpretation(interpretation_id)
        before = deepcopy(well.interpretations)
        removed = well.interpretations.pop(interpretation_id)
        self.selected_interpretation_id = next(iter(well.interpretations), None)
        self.selected_interval_id = None
        self._record(well, before, "Удаление интерпретации")
        return removed

    def available_intervals(self) -> tuple[InterpretationInterval, ...]:
        return tuple(
            sorted(
                self.current_interpretation().intervals,
                key=lambda item: (
                    item.top_depth,
                    item.bottom_depth,
                    item.interval_type.casefold(),
                    item.label.casefold(),
                ),
            )
        )

    def add_interval(
        self,
        top_depth: float,
        bottom_depth: float,
        interval_type: str,
        label: str,
        *,
        color: str = "#fde68a",
        comment: str | None = None,
        label_i18n: object | None = None,
        comment_i18n: object | None = None,
    ) -> InterpretationInterval:
        values = self._validate_interval(
            top_depth, bottom_depth, interval_type, label, color, comment
        )
        localized_labels = self._validate_localized(label_i18n, maximum=300)
        localized_comments = self._validate_localized(comment_i18n, maximum=4_000)
        well = self._require_well()
        interpretation = self.current_interpretation()
        self._ensure_no_overlap(interpretation, values[0], values[1], values[2])
        before = deepcopy(well.interpretations)
        interval = InterpretationInterval(new_id(), *values)
        interval.label_i18n.update(localized_labels or {})
        interval.comment_i18n.update(localized_comments or {})
        if localized_labels and "ru" in localized_labels:
            interval.label = localized_labels["ru"]
        if localized_comments and "ru" in localized_comments:
            interval.comment = localized_comments["ru"]
        interpretation.intervals.append(interval)
        self.selected_interval_id = interval.interval_id
        self._record(well, before, "Добавление интервала интерпретации")
        self._bump_languages(set(localized_labels or ()) | set(localized_comments or ()))
        return interval

    def update_interval(
        self,
        interval_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        interval_type: str,
        label: str,
        color: str = "#fde68a",
        comment: str | None = None,
        label_i18n: object | None = None,
        comment_i18n: object | None = None,
    ) -> InterpretationInterval:
        values = self._validate_interval(
            top_depth, bottom_depth, interval_type, label, color, comment
        )
        localized_labels = self._validate_localized(label_i18n, maximum=300)
        localized_comments = self._validate_localized(comment_i18n, maximum=4_000)
        well = self._require_well()
        interpretation = self.current_interpretation()
        interval = self._require_interval(interval_id)
        self._ensure_no_overlap(
            interpretation,
            values[0],
            values[1],
            values[2],
            excluded_id=interval_id,
        )
        before = deepcopy(well.interpretations)
        (
            interval.top_depth,
            interval.bottom_depth,
            interval.interval_type,
            interval.label,
            interval.color,
            interval.comment,
        ) = values
        changed_languages: set[str] = set()
        if localized_labels is not None:
            changed_languages |= set(interval.label_i18n) | set(localized_labels)
            interval.label_i18n = localized_labels
            if "ru" in localized_labels:
                interval.label = localized_labels["ru"]
        if localized_comments is not None:
            changed_languages |= set(interval.comment_i18n) | set(localized_comments)
            interval.comment_i18n = localized_comments
            if "ru" in localized_comments:
                interval.comment = localized_comments["ru"]
        self.selected_interval_id = interval.interval_id
        self._record(well, before, "Изменение интервала интерпретации")
        self._bump_languages(changed_languages)
        return interval

    @staticmethod
    def _validate_localized(value: object | None, *, maximum: int) -> dict[str, str] | None:
        if value is None:
            return None
        return validate_localized_texts(
            value,  # type: ignore[arg-type]
            maximum=maximum,
            allow_undetermined=True,
        )

    def _bump_languages(self, languages: set[str]) -> None:
        well = self._require_well()
        for language in languages:
            if language == "und":
                continue
            well.content_revision += 1
            bump_language_revision(well.language_revisions, language)

    def remove_interval(self, interval_id: str) -> InterpretationInterval:
        well = self._require_well()
        interpretation = self.current_interpretation()
        interval = self._require_interval(interval_id)
        before = deepcopy(well.interpretations)
        interpretation.intervals.remove(interval)
        if self.selected_interval_id == interval_id:
            self.selected_interval_id = None
        self._record(well, before, "Удаление интервала интерпретации")
        return interval

    def undo(self) -> str:
        command = self.history.undo()
        self._normalize_selection()
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        command = self.history.redo()
        self._normalize_selection()
        self.session.dirty = True
        return command.description

    def export_current(
        self,
        target: str | Path,
        export_format: str,
        *,
        overwrite: bool = False,
    ) -> Path:
        interpretation = self.current_interpretation()
        well = self._require_well()
        normalized = export_format.casefold()
        if normalized == "json":
            return export_interpretation_json(
                interpretation, target, well_name=well.name, overwrite=overwrite
            )
        if normalized == "csv":
            return export_interpretation_csv(interpretation, target, overwrite=overwrite)
        if normalized in {"xlsx", "excel"}:
            return export_interpretation_excel(
                interpretation, target, well_name=well.name, overwrite=overwrite
            )
        raise ValueError(f"Неподдерживаемый формат экспорта: {export_format}")

    def _record(
        self,
        well: Well,
        before: dict[str, WellInterpretation],
        description: str,
    ) -> None:
        self.history.record(well, before, description=description)
        self.session.dirty = True

    @staticmethod
    def _validate_interpretation(
        name: str,
        description: str | None,
    ) -> tuple[str, str | None]:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Название интерпретации не может быть пустым")
        if len(normalized_name) > 200:
            raise ValueError("Название интерпретации не должно превышать 200 символов")
        normalized_description = description.strip() if description else None
        if normalized_description and len(normalized_description) > 4000:
            raise ValueError("Описание интерпретации не должно превышать 4000 символов")
        return normalized_name, normalized_description

    def _validate_interval(
        self,
        top_depth: float,
        bottom_depth: float,
        interval_type: str,
        label: str,
        color: str,
        comment: str | None,
    ) -> tuple[float, float, str, str, str, str | None]:
        top, bottom = float(top_depth), float(bottom_depth)
        if not np.isfinite(top) or not np.isfinite(bottom) or top >= bottom:
            raise ValueError("Кровля интервала должна быть меньше подошвы")
        normalized_type = interval_type.strip()
        if not normalized_type or len(normalized_type) > 100:
            raise ValueError("Тип интервала обязателен и не длиннее 100 символов")
        normalized_label = label.strip()
        if not normalized_label or len(normalized_label) > 300:
            raise ValueError("Подпись интервала обязательна и не длиннее 300 символов")
        normalized_color = color.strip().lower()
        if not re.fullmatch(r"#[0-9a-f]{6}", normalized_color):
            raise ValueError("Цвет интервала должен быть в формате #RRGGBB")
        normalized_comment = comment.strip() if comment else None
        if normalized_comment and len(normalized_comment) > 4000:
            raise ValueError("Комментарий интервала не должен превышать 4000 символов")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite = dataset.depth[np.isfinite(dataset.depth)]
            if finite.size and (top < float(np.min(finite)) or bottom > float(np.max(finite))):
                raise ValueError("Интервал выходит за диапазон текущего dataset")
        return (
            top,
            bottom,
            normalized_type,
            normalized_label,
            normalized_color,
            normalized_comment,
        )

    @staticmethod
    def _ensure_no_overlap(
        interpretation: WellInterpretation,
        top: float,
        bottom: float,
        interval_type: str,
        *,
        excluded_id: str | None = None,
    ) -> None:
        type_key = interval_type.casefold()
        for interval in interpretation.intervals:
            if interval.interval_id == excluded_id:
                continue
            if interval.interval_type.casefold() != type_key:
                continue
            if top < interval.bottom_depth and bottom > interval.top_depth:
                raise ValueError(
                    f"Интервал пересекается с '{interval.label}' того же типа: "
                    f"{interval.top_depth:g}–{interval.bottom_depth:g} м"
                )

    def _normalize_selection(self) -> None:
        well = self._require_well()
        if self.selected_interpretation_id not in well.interpretations:
            self.selected_interpretation_id = next(iter(well.interpretations), None)
        interpretation = well.interpretations.get(self.selected_interpretation_id or "")
        if interpretation is None or not any(
            item.interval_id == self.selected_interval_id for item in interpretation.intervals
        ):
            self.selected_interval_id = None

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _require_interpretation(self, interpretation_id: str) -> WellInterpretation:
        try:
            return self._require_well().interpretations[interpretation_id]
        except KeyError as exc:
            raise KeyError(f"Интерпретация не найдена: {interpretation_id}") from exc

    def _require_interval(self, interval_id: str) -> InterpretationInterval:
        for interval in self.current_interpretation().intervals:
            if interval.interval_id == interval_id:
                return interval
        raise KeyError(f"Интервал интерпретации не найден: {interval_id}")
