from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.models import CuttingsComponent, CuttingsSample, Well, new_id
from geoworkbench.domain.localized_content import (
    bump_language_revision,
    localized_text,
    normalize_content_language,
    set_localized_text,
)
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class CuttingsController:
    session: ProjectSession

    def available(self) -> tuple[CuttingsSample, ...]:
        """Return samples in stable depth order for editors and hit-testing."""
        return tuple(
            sorted(
                self._require_well().cuttings,
                key=lambda item: (item.top_depth, item.bottom_depth, item.sample_id),
            )
        )

    def get(self, sample_id: str) -> CuttingsSample:
        return self._require_sample(sample_id)

    def update_composition(
        self,
        sample_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        components: dict[str, float],
    ) -> CuttingsSample:
        """Edit an existing cuttings interval without losing analysis or description.

        LBA, calcimetry, rich description and interpretation belong to the same
        sample object.  Changing the interval or rock percentages must therefore
        update that object in place rather than create a second sample.
        """
        sample = self._require_sample(sample_id)
        top, bottom = self._validate_interval(top_depth, bottom_depth)
        normalized = self._validate_components(components)
        self._ensure_no_overlap(top, bottom, excluded_id=sample_id)
        sample.top_depth = top
        sample.bottom_depth = bottom
        sample.components = [
            CuttingsComponent(name, percentage) for name, percentage in normalized.items()
        ]
        self.session.dirty = True
        return sample

    def create_full_sample(
        self,
        top_depth: float,
        bottom_depth: float,
        components: dict[str, float],
        **values: object,
    ) -> CuttingsSample:
        """Create one complete geological sample shared by all related tracks."""

        top, bottom = self._validate_interval(top_depth, bottom_depth)
        normalized = self._validate_components(components)
        self._ensure_no_overlap(top, bottom)
        sample = CuttingsSample(
            new_id(),
            top,
            bottom,
            [CuttingsComponent(name, percentage) for name, percentage in normalized.items()],
        )
        self._apply_full_values(sample, values)
        self._require_well().cuttings.append(sample)
        self.session.dirty = True
        return sample

    def update_full_sample(
        self,
        sample_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        components: dict[str, float],
        **values: object,
    ) -> CuttingsSample:
        """Atomically edit interval, rocks, LBA, calcimetry and rich description."""

        sample = self._require_sample(sample_id)
        top, bottom = self._validate_interval(top_depth, bottom_depth)
        normalized = self._validate_components(components)
        self._ensure_no_overlap(top, bottom, excluded_id=sample_id)
        sample.top_depth = top
        sample.bottom_depth = bottom
        sample.components = [
            CuttingsComponent(name, percentage) for name, percentage in normalized.items()
        ]
        self._apply_full_values(sample, values)
        self.session.dirty = True
        return sample

    def _apply_full_values(self, sample: CuttingsSample, values: dict[str, object]) -> None:
        content_language = values.get("content_language")
        calcite, dolomite = self._validate_calcimetry(
            values.get("calcite_percent"), values.get("dolomite_percent")
        )
        sample.calcite_percent = calcite
        sample.dolomite_percent = dolomite
        sample.lba_group = self._validate_lba_scale(values.get("lba_group"), "Группа ЛБА")
        sample.lba_intensity = self._validate_lba_scale(
            values.get("lba_intensity"), "Интенсивность ЛБА"
        )
        sample.lba_type_id = self._normalize_text(values.get("lba_type_id"), 100)
        sample.lba_color = self._normalize_text(values.get("lba_color"), 100)
        sample.lba_distribution = self._normalize_text(values.get("lba_distribution"), 100)
        sample.lba_cut = self._normalize_text(values.get("lba_cut"), 100)
        sample.lba_cut_speed = self._normalize_text(values.get("lba_cut_speed"), 100)
        sample.lba_cut_color = self._normalize_text(values.get("lba_cut_color"), 100)
        sample.lba_residue_type = self._normalize_text(values.get("lba_residue_type"), 100)
        sample.lba_residue_color = self._normalize_text(values.get("lba_residue_color"), 100)
        sample.lba_odour = self._normalize_text(values.get("lba_odour"), 100)
        sample.lba_stain = self._normalize_text(values.get("lba_stain"), 100)
        lba_description = self._normalize_text(values.get("lba_description"), 2000)
        interpretation = self._normalize_text(
            values.get("analysis_interpretation"), 20_000, "Текст интерпретации"
        )
        # Rich HTML may contain embedded image data, therefore its safe storage
        # limit is intentionally much larger than a plain LAS comment field.
        description = self._normalize_text(
            values.get("description"), 2_000_000, "Описание шлама"
        )
        if content_language is None:
            sample.lba_description = lba_description
            sample.analysis_interpretation = interpretation
            sample.description = description
        else:
            language = normalize_content_language(content_language)
            set_localized_text(
                sample.lba_description_i18n, language, lba_description, maximum=2_000
            )
            set_localized_text(
                sample.analysis_interpretation_i18n,
                language,
                interpretation,
                maximum=20_000,
            )
            set_localized_text(
                sample.description_i18n, language, description, maximum=2_000_000
            )
            if language == "ru":
                sample.lba_description = lba_description
                sample.analysis_interpretation = interpretation
                sample.description = description
            self._bump_content(language)
        if "description_word_wrap" in values:
            sample.description_word_wrap = self._validate_word_wrap(
                values["description_word_wrap"]
            )

    def update_description(
        self,
        sample_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        description: str | None,
        description_word_wrap: bool | None = None,
        language: object | None = None,
    ) -> CuttingsSample:
        """Edit one rich-text description without losing sample analysis.

        The interval may be corrected in the same dialog.  Composition, LBA and
        calcimetry remain attached to the same sample ID.  Clearing text is
        allowed for an existing laboratory/sample record.
        """

        sample = self._require_sample(sample_id)
        top, bottom = self._validate_interval(top_depth, bottom_depth)
        normalized = self._normalize_text(description, 2_000_000, "Описание шлама")
        if self._has_non_description_data(sample):
            self._ensure_no_overlap(top, bottom, excluded_id=sample_id)
        sample.top_depth = top
        sample.bottom_depth = bottom
        if language is None:
            sample.description = normalized
        else:
            code = normalize_content_language(language)
            set_localized_text(
                sample.description_i18n, code, normalized, maximum=2_000_000
            )
            if code == "ru":
                sample.description = normalized
            self._bump_content(code)
        if description_word_wrap is not None:
            sample.description_word_wrap = self._validate_word_wrap(
                description_word_wrap
            )
        self.session.dirty = True
        return sample

    def delete_description(
        self, sample_id: str, *, language: object | None = None
    ) -> CuttingsSample:
        """Delete only the description and preserve any analysis on the sample.

        A description-only interval is removed completely so it cannot remain
        as an invisible record that blocks a future overlapping interval.
        """

        well = self._require_well()
        sample = self._require_sample(sample_id)
        if language is None:
            sample.description = None
            sample.description_i18n.clear()
        else:
            code = normalize_content_language(language)
            sample.description_i18n.pop(code, None)
            if code == "ru":
                sample.description = None
            self._bump_content(code)
        if not self._has_non_description_data(sample) and not self._has_description_data(sample):
            well.cuttings.remove(sample)
        self.session.dirty = True
        return sample

    @staticmethod
    def _has_non_description_data(sample: CuttingsSample) -> bool:
        if sample.components:
            return True
        values = (
            sample.lba_group,
            sample.lba_type_id,
            sample.lba_intensity,
            sample.lba_color,
            sample.lba_distribution,
            sample.lba_cut,
            sample.lba_cut_speed,
            sample.lba_cut_color,
            sample.lba_residue_type,
            sample.lba_residue_color,
            sample.lba_odour,
            sample.lba_stain,
            sample.lba_description,
            sample.calcite_percent,
            sample.dolomite_percent,
            sample.analysis_interpretation,
            sample.lba_description_i18n,
            sample.analysis_interpretation_i18n,
        )
        return any(bool(value) for value in values)

    @staticmethod
    def _has_description_data(sample: CuttingsSample) -> bool:
        return bool(sample.description or sample.description_i18n)

    def remove(self, sample_id: str) -> CuttingsSample:
        well = self._require_well()
        sample = self._require_sample(sample_id)
        well.cuttings.remove(sample)
        self.session.dirty = True
        return sample

    def add(
        self,
        top_depth: float,
        bottom_depth: float,
        components: dict[str, float],
        *,
        description: str | None = None,
        description_word_wrap: bool = True,
    ) -> CuttingsSample:
        top, bottom = self._validate_interval(top_depth, bottom_depth)
        normalized = self._validate_components(components)
        normalized_description = self._normalize_text(description, 4000, "Описание шлама")
        existing = self._find_exact_sample(top, bottom)
        if existing is not None:
            if existing.components:
                raise ValueError(f"Проба {top:g}–{bottom:g} м уже заполнена")
            existing.components = [
                CuttingsComponent(name, percentage) for name, percentage in normalized.items()
            ]
            if description is not None:
                existing.description = normalized_description
            self.session.dirty = True
            return existing
        self._ensure_no_overlap(top, bottom)
        sample = CuttingsSample(
            new_id(),
            top,
            bottom,
            [CuttingsComponent(name, percentage) for name, percentage in normalized.items()],
            description=normalized_description,
            description_word_wrap=self._validate_word_wrap(description_word_wrap),
        )
        self._require_well().cuttings.append(sample)
        self.session.dirty = True
        return sample

    def set_description(
        self,
        top_depth: float,
        bottom_depth: float,
        description: str | None,
        *,
        description_word_wrap: bool | None = None,
        language: object | None = None,
    ) -> CuttingsSample:
        """Create or update free-text cuttings description for an exact sample interval."""
        top, bottom = self._validate_interval(top_depth, bottom_depth)
        normalized = self._normalize_text(description, 2_000_000, "Описание шлама")
        sample = self._find_exact_sample(top, bottom)
        if sample is None:
            if normalized is None:
                raise ValueError("Введите описание шлама")
            # A description is an independent interpretation track.  LAS files
            # commonly contain cuttings intervals already, so a manually
            # entered description may legitimately cover part of one of them.
            # Composition-bearing samples still use the strict overlap guard.
            word_wrap = (
                True
                if description_word_wrap is None
                else self._validate_word_wrap(description_word_wrap)
            )
            sample = CuttingsSample(
                new_id(),
                top,
                bottom,
                description=normalized,
                description_word_wrap=word_wrap,
            )
            if language is not None:
                code = normalize_content_language(language)
                set_localized_text(
                    sample.description_i18n, code, normalized, maximum=2_000_000
                )
                if code != "ru":
                    sample.description = None
                self._bump_content(code)
            self._require_well().cuttings.append(sample)
        else:
            if language is None:
                sample.description = normalized
            else:
                code = normalize_content_language(language)
                set_localized_text(
                    sample.description_i18n, code, normalized, maximum=2_000_000
                )
                if code == "ru":
                    sample.description = normalized
                self._bump_content(code)
            if description_word_wrap is not None:
                sample.description_word_wrap = self._validate_word_wrap(
                    description_word_wrap
                )
        self.session.dirty = True
        return sample

    def _validate_interval(self, top_depth: float, bottom_depth: float) -> tuple[float, float]:
        top, bottom = float(top_depth), float(bottom_depth)
        if not np.isfinite(top) or not np.isfinite(bottom) or top >= bottom:
            raise ValueError("Кровля шламового интервала должна быть меньше подошвы")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite = dataset.depth[np.isfinite(dataset.depth)]
            if finite.size and (top < float(np.min(finite)) or bottom > float(np.max(finite))):
                raise ValueError("Шламовый интервал выходит за диапазон dataset")
        return top, bottom

    @staticmethod
    def _validate_word_wrap(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError("Настройка переноса слов должна быть логическим значением")
        return value

    def set_analysis(
        self,
        top_depth: float,
        bottom_depth: float,
        *,
        calcite_percent: float | None = None,
        dolomite_percent: float | None = None,
        lba_group: int | None = None,
        lba_type_id: str | None = None,
        lba_intensity: int | None = None,
        lba_color: str | None = None,
        lba_distribution: str | None = None,
        lba_cut: str | None = None,
        lba_cut_speed: str | None = None,
        lba_cut_color: str | None = None,
        lba_residue_type: str | None = None,
        lba_residue_color: str | None = None,
        lba_odour: str | None = None,
        lba_stain: str | None = None,
        lba_description: str | None = None,
        analysis_interpretation: str | None = None,
        content_language: object | None = None,
    ) -> CuttingsSample:
        top, bottom = self._validate_interval(top_depth, bottom_depth)
        calcite, dolomite = self._validate_calcimetry(calcite_percent, dolomite_percent)
        group = self._validate_lba_scale(lba_group, "Группа ЛБА")
        intensity = self._validate_lba_scale(lba_intensity, "Интенсивность ЛБА")
        strings = {
            "type": self._normalize_text(lba_type_id, 100),
            "color": self._normalize_text(lba_color, 100),
            "distribution": self._normalize_text(lba_distribution, 100),
            "cut": self._normalize_text(lba_cut, 100),
            "cut_speed": self._normalize_text(lba_cut_speed, 100),
            "cut_color": self._normalize_text(lba_cut_color, 100),
            "residue_type": self._normalize_text(lba_residue_type, 100),
            "residue_color": self._normalize_text(lba_residue_color, 100),
            "odour": self._normalize_text(lba_odour, 100),
            "stain": self._normalize_text(lba_stain, 100),
            "description": self._normalize_text(lba_description, 2000),
            "interpretation": self._normalize_text(
                analysis_interpretation, 4000, "Текст интерпретации"
            ),
        }
        if (
            calcite is None
            and dolomite is None
            and group is None
            and intensity is None
            and not any(strings.values())
        ):
            raise ValueError("Укажите хотя бы один результат кальциметрии или ЛБА")
        sample = self._find_exact_sample(top, bottom)
        if sample is None:
            # Calcimetry/LBA are independent laboratory tracks.  Keep their
            # interval separate from imported cuttings so an analyst can fill
            # a missing range without rewriting the LAS lithology.
            sample = CuttingsSample(new_id(), top, bottom)
            self._require_well().cuttings.append(sample)
        sample.calcite_percent = calcite
        sample.dolomite_percent = dolomite
        sample.lba_group = group
        sample.lba_type_id = strings["type"]
        sample.lba_intensity = intensity
        sample.lba_color = strings["color"]
        sample.lba_distribution = strings["distribution"]
        sample.lba_cut = strings["cut"]
        sample.lba_cut_speed = strings["cut_speed"]
        sample.lba_cut_color = strings["cut_color"]
        sample.lba_residue_type = strings["residue_type"]
        sample.lba_residue_color = strings["residue_color"]
        sample.lba_odour = strings["odour"]
        sample.lba_stain = strings["stain"]
        if content_language is None:
            sample.lba_description = strings["description"]
            sample.analysis_interpretation = strings["interpretation"]
        else:
            language = normalize_content_language(content_language)
            set_localized_text(
                sample.lba_description_i18n,
                language,
                strings["description"],
                maximum=2_000,
            )
            set_localized_text(
                sample.analysis_interpretation_i18n,
                language,
                strings["interpretation"],
                maximum=20_000,
            )
            if language == "ru":
                sample.lba_description = strings["description"]
                sample.analysis_interpretation = strings["interpretation"]
            self._bump_content(language)
        self.session.dirty = True
        return sample

    @staticmethod
    def localized_description(sample: CuttingsSample, language: object) -> str:
        return localized_text(
            sample.description_i18n, language, legacy=sample.description
        )

    @staticmethod
    def localized_lba_description(sample: CuttingsSample, language: object) -> str:
        return localized_text(
            sample.lba_description_i18n, language, legacy=sample.lba_description
        )

    @staticmethod
    def localized_analysis_interpretation(
        sample: CuttingsSample, language: object
    ) -> str:
        return localized_text(
            sample.analysis_interpretation_i18n,
            language,
            legacy=sample.analysis_interpretation,
        )

    def _bump_content(self, language: object) -> None:
        well = self._require_well()
        well.content_revision += 1
        bump_language_revision(well.language_revisions, language)

    @staticmethod
    def _validate_calcimetry(
        calcite_percent: object, dolomite_percent: object
    ) -> tuple[float | None, float | None]:
        values: list[float | None] = []
        for value in (calcite_percent, dolomite_percent):
            if value is None:
                values.append(None)
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError("Кальцит и доломит должны быть числами")
            normalized = float(value)
            if not np.isfinite(normalized) or not 0.0 <= normalized <= 100.0:
                raise ValueError("Кальцит и доломит должны быть в диапазоне 0–100%")
            values.append(normalized)
        total = sum(value for value in values if value is not None)
        if total > 100.01:
            raise ValueError("Сумма кальцита и доломита не должна превышать 100%")
        return values[0], values[1]

    @staticmethod
    def _validate_lba_scale(value: object, label: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError(f"{label} должна быть целым числом от 1 до 5")
        return value

    @staticmethod
    def _normalize_text(value: object, maximum: int, label: str = "Текст ЛБА") -> str | None:
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{label} должен быть текстом")
        normalized = (value.strip() if isinstance(value, str) else "") or None
        if normalized and len(normalized) > maximum:
            raise ValueError(f"{label} не должен превышать {maximum} символов")
        return normalized

    @staticmethod
    def _validate_components(components: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for lithotype_id, percentage in components.items():
            name = lithotype_id.strip()
            value = float(percentage)
            if not name or not np.isfinite(value) or value < 0 or value > 100:
                raise ValueError("Компоненты шлама должны иметь долю от 0 до 100%")
            if value > 0:
                normalized[name] = value
        if not normalized:
            raise ValueError("Укажите хотя бы один компонент шлама")
        if not np.isclose(sum(normalized.values()), 100.0, atol=0.01):
            raise ValueError("Сумма компонентов шлама должна быть равна 100%")
        return normalized

    def _ensure_no_overlap(
        self, top: float, bottom: float, *, excluded_id: str | None = None
    ) -> None:
        for sample in self._require_well().cuttings:
            if sample.sample_id == excluded_id:
                continue
            if top < sample.bottom_depth and bottom > sample.top_depth:
                raise ValueError(
                    f"Интервал пересекается с пробой {sample.top_depth:g}–{sample.bottom_depth:g} м"
                )

    def _find_exact_sample(self, top: float, bottom: float) -> CuttingsSample | None:
        return next(
            (
                item
                for item in self._require_well().cuttings
                if np.isclose(item.top_depth, top) and np.isclose(item.bottom_depth, bottom)
            ),
            None,
        )

    def _require_sample(self, sample_id: str) -> CuttingsSample:
        for sample in self._require_well().cuttings:
            if sample.sample_id == sample_id:
                return sample
        raise KeyError(f"Проба шлама не найдена: {sample_id}")

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well
