from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from geoworkbench.data.las_adapter import export_las
from geoworkbench.data.dataset_json_export import export_dataset_json
from geoworkbench.data.dataset_parquet_export import export_dataset_parquet
from geoworkbench.data.las_export_plan import (
    LasExportAnalysis,
    LasExportPlan,
    LasExportVersion,
    analyze_las_export,
)
from geoworkbench.data.selection_export import (
    export_selection_excel,
    export_selection_text,
)
from geoworkbench.domain.models import Dataset, ExportProfile, new_id
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class DatasetExportController:
    session: ProjectSession

    def save_selection_profile(self, name: str, curve_ids: list[str]) -> ExportProfile:
        dataset = self._require_current_dataset()
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Имя профиля экспорта не может быть пустым")
        if any(
            profile.name.casefold() == normalized_name.casefold()
            for profile in self.session.project.export_profiles.values()
        ):
            raise ValueError(f"Профиль экспорта уже существует: {normalized_name}")
        missing = [curve_id for curve_id in curve_ids if curve_id not in dataset.curves]
        if missing:
            raise KeyError(f"Кривые не найдены: {', '.join(missing)}")
        mnemonics = tuple(
            dict.fromkeys(
                dataset.curves[curve_id].metadata.original_mnemonic
                for curve_id in curve_ids
            )
        )
        profile = ExportProfile(new_id(), normalized_name, mnemonics)
        self.session.project.export_profiles[profile.profile_id] = profile
        self.session.dirty = True
        return profile

    def resolve_profile_curve_ids(self, profile_id: str) -> tuple[str, ...]:
        try:
            profile = self.session.project.export_profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"Профиль экспорта не найден: {profile_id}") from exc
        dataset = self._require_current_dataset()
        resolved: list[str] = []
        missing: list[str] = []
        for mnemonic in profile.curve_mnemonics:
            curve = dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                missing.append(mnemonic)
            else:
                resolved.append(curve.metadata.curve_id)
        if missing:
            raise ValueError("В текущем наборе отсутствуют кривые: " + ", ".join(missing))
        return tuple(resolved)

    def delete_selection_profile(self, profile_id: str) -> None:
        if profile_id not in self.session.project.export_profiles:
            raise KeyError(f"Профиль экспорта не найден: {profile_id}")
        del self.session.project.export_profiles[profile_id]
        self.session.dirty = True

    def default_las_plan(self) -> LasExportPlan:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        null_value: float | None = None
        raw_null = dataset.headers.get("NULL")
        if raw_null is not None:
            try:
                candidate = float(raw_null.strip().replace(",", "."))
                if isfinite(candidate):
                    null_value = candidate
            except ValueError:
                pass
        report = self.session.import_reports.get(dataset.dataset_id)
        if null_value is None and report is not None:
            null_value = report.source.null_value
        version = LasExportVersion.V2_0
        wrap = False
        declared_version = dataset.version_headers.get("VERS", "").strip()
        if declared_version.startswith("1.2"):
            version = LasExportVersion.V1_2
        elif declared_version.startswith("2"):
            version = LasExportVersion.V2_0
        wrap = dataset.version_headers.get("WRAP", "").strip().casefold() in {
            "yes",
            "y",
            "true",
            "1",
        }
        if report is not None:
            source_version = (report.source.las_version or "").strip()
            if source_version.startswith("1.2"):
                version = LasExportVersion.V1_2
            elif source_version.startswith("2"):
                version = LasExportVersion.V2_0
            wrap = (report.source.wrap or "").strip().casefold() in {"yes", "y", "true", "1"}
        return LasExportPlan(
            version=version,
            wrap=wrap,
            null_value=null_value if null_value is not None else -9999.25,
        )

    def analyze_current_las_export(
        self,
        plan: LasExportPlan,
    ) -> LasExportAnalysis:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return analyze_las_export(
            dataset,
            plan,
            self.session.source_documents.get(dataset.dataset_id),
        )

    def export_current_las(
        self,
        target: Path,
        *,
        overwrite: bool = False,
        plan: LasExportPlan | None = None,
    ) -> Path:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return export_las(
            dataset,
            target,
            overwrite=overwrite,
            source_document=self.session.source_documents.get(dataset.dataset_id),
            plan=plan,
        )

    def export_current_selection_text(
        self,
        target: Path,
        curve_ids: list[str],
        depth_top: float,
        depth_bottom: float,
        *,
        delimiter: str = ",",
        overwrite: bool = False,
    ) -> Path:
        dataset = self._require_current_dataset()
        return export_selection_text(
            dataset,
            target,
            curve_ids,
            depth_top,
            depth_bottom,
            delimiter=delimiter,
            overwrite=overwrite,
        )

    def export_current_selection_excel(
        self,
        target: Path,
        curve_ids: list[str],
        depth_top: float,
        depth_bottom: float,
        *,
        overwrite: bool = False,
    ) -> Path:
        dataset = self._require_current_dataset()
        return export_selection_excel(
            dataset,
            target,
            curve_ids,
            depth_top,
            depth_bottom,
            overwrite=overwrite,
        )

    def export_current_json(self, target: Path, *, overwrite: bool = False) -> Path:
        return export_dataset_json(
            self._require_current_dataset(), target, overwrite=overwrite
        )

    def export_current_parquet(
        self, target: Path, *, overwrite: bool = False
    ) -> Path:
        return export_dataset_parquet(
            self._require_current_dataset(), target, overwrite=overwrite
        )

    def _require_current_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset
