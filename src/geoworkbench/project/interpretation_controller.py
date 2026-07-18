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

    def select_interval(
        self, interpretation_id: str, interval_id: str
    ) -> InterpretationInterval:
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
    ) -> WellInterpretation:
        normalized_name, normalized_description = self._validate_interpretation(
            name, description
        )
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
        )
        well.interpretations[interpretation.interpretation_id] = interpretation
        self.selected_interpretation_id = interpretation.interpretation_id
        self.selected_interval_id = None
        self._record(well, before, "Добавление интерпретации")
        return interpretation

    def update_interpretation(
        self,
        interpretation_id: str,
        *,
        name: str,
        description: str | None = None,
    ) -> WellInterpretation:
        normalized_name, normalized_description = self._validate_interpretation(
            name, description
        )
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
        self._record(well, before, "Изменение интерпретации")
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
    ) -> InterpretationInterval:
        values = self._validate_interval(
            top_depth, bottom_depth, interval_type, label, color, comment
        )
        well = self._require_well()
        interpretation = self.current_interpretation()
        self._ensure_no_overlap(interpretation, values[0], values[1], values[2])
        before = deepcopy(well.interpretations)
        interval = InterpretationInterval(new_id(), *values)
        interpretation.intervals.append(interval)
        self.selected_interval_id = interval.interval_id
        self._record(well, before, "Добавление интервала интерпретации")
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
    ) -> InterpretationInterval:
        values = self._validate_interval(
            top_depth, bottom_depth, interval_type, label, color, comment
        )
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
        self.selected_interval_id = interval.interval_id
        self._record(well, before, "Изменение интервала интерпретации")
        return interval

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
