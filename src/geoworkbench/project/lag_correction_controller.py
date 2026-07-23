from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.lag_correction import (
    LagCorrectionAxisMode,
    LagCorrectionMethod,
    LagCorrectionParameters,
    LagCorrectionProfile,
    LagCorrectionTarget,
)
from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    TimeDepthAggregationPolicy,
    Well,
    new_id,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.lag_correction import (
    LagCorrectionAxisSelection,
    LagCorrectionController,
    LagCorrectionCreateRequest,
    LagCorrectionPreview,
)


@dataclass(slots=True)
class LagCorrectionProjectController:
    session: ProjectSession

    def create_profile(
        self,
        *,
        name: str,
        target: LagCorrectionTarget,
        source_time_index_id: str | None,
        source_depth_index_id: str,
        target_curve_ids: tuple[str, ...],
        method: LagCorrectionMethod,
        parameters: LagCorrectionParameters,
        aggregation_policy: TimeDepthAggregationPolicy,
        created_at: str,
        created_by: str,
        comment: str = "",
    ) -> LagCorrectionProfile:
        well, dataset = self._current()
        profile_id = new_id()
        request = self._request(
            profile_id=profile_id,
            name=name,
            target=target,
            source_dataset_id=dataset.dataset_id,
            source_time_index_id=source_time_index_id,
            source_depth_index_id=source_depth_index_id,
            target_curve_ids=target_curve_ids,
            method=method,
            parameters=parameters,
            aggregation_policy=aggregation_policy,
            created_at=created_at,
            created_by=created_by,
            comment=comment,
        )
        profile = LagCorrectionController(well).create_profile(request)
        self.session.dirty = True
        return profile

    def add_revision(
        self,
        profile_id: str,
        *,
        source_time_index_id: str | None,
        source_depth_index_id: str,
        target_curve_ids: tuple[str, ...],
        method: LagCorrectionMethod,
        parameters: LagCorrectionParameters,
        aggregation_policy: TimeDepthAggregationPolicy,
        created_at: str,
        created_by: str,
        comment: str = "",
        expected_latest_revision: int,
    ) -> LagCorrectionProfile:
        well = self._well()
        profile = well.lag_correction_profiles[profile_id]
        request = self._request(
            profile_id=profile.profile_id,
            name=profile.name,
            target=profile.target,
            source_dataset_id=profile.source_dataset_id,
            source_time_index_id=source_time_index_id,
            source_depth_index_id=source_depth_index_id,
            target_curve_ids=target_curve_ids,
            method=method,
            parameters=parameters,
            aggregation_policy=aggregation_policy,
            created_at=created_at,
            created_by=created_by,
            comment=comment,
        )
        updated = LagCorrectionController(well).add_revision(
            profile_id,
            request,
            expected_latest_revision=expected_latest_revision,
        )
        self.session.dirty = True
        return updated

    def activate_revision(
        self,
        profile_id: str,
        revision: int,
        *,
        expected_active_revision: int | None = None,
    ) -> LagCorrectionProfile:
        updated = LagCorrectionController(self._well()).activate_revision(
            profile_id,
            revision,
            expected_active_revision=expected_active_revision,
        )
        self.session.dirty = True
        return updated

    def delete_profile(self, profile_id: str) -> None:
        well = self._well()
        profile = well.lag_correction_profiles[profile_id]
        output_ids = {item.output_dataset_id for item in profile.revisions}
        LagCorrectionController(well).delete_profile(profile_id)
        if self.session.current_dataset_id in output_ids:
            self.session.current_dataset_id = profile.source_dataset_id
        self.session.dirty = True

    def preview(
        self,
        profile_id: str,
        revision: int | None = None,
    ) -> LagCorrectionPreview:
        return LagCorrectionController(self._well()).preview(profile_id, revision)

    def select_projection(
        self,
        profile_id: str,
        mode: LagCorrectionAxisMode,
        revision: int | None = None,
    ) -> LagCorrectionAxisSelection:
        selection = LagCorrectionController(self._well()).select_axis(
            profile_id,
            mode,
            revision,
        )
        active_changed = selection.dataset.active_index_id != selection.index_id
        selection.dataset.set_active_index(selection.index_id)
        self.session.current_dataset_id = selection.dataset.dataset_id
        if active_changed:
            self.session.dirty = True
        return selection

    def _request(
        self,
        *,
        profile_id: str,
        name: str,
        target: LagCorrectionTarget,
        source_dataset_id: str,
        source_time_index_id: str | None,
        source_depth_index_id: str,
        target_curve_ids: tuple[str, ...],
        method: LagCorrectionMethod,
        parameters: LagCorrectionParameters,
        aggregation_policy: TimeDepthAggregationPolicy,
        created_at: str,
        created_by: str,
        comment: str,
    ) -> LagCorrectionCreateRequest:
        output_dataset_id = new_id()
        return LagCorrectionCreateRequest(
            profile_id=profile_id,
            name=name,
            target=target,
            source_dataset_id=source_dataset_id,
            source_time_index_id=source_time_index_id,
            source_depth_index_id=source_depth_index_id,
            target_curve_ids=target_curve_ids,
            method=method,
            parameters=parameters,
            aggregation_policy=aggregation_policy,
            output_dataset_id=output_dataset_id,
            output_source_index_id=f"{output_dataset_id}:source-depth",
            output_index_id=f"{output_dataset_id}:corrected-depth",
            created_at=created_at,
            created_by=created_by,
            comment=comment,
        )

    def _current(self) -> tuple[Well, Dataset]:
        well = self._well()
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите source dataset")
        if dataset.kind is DatasetKind.DERIVED and dataset.headers.get("LAG_PROFILE_ID"):
            raise ValueError("Новая correction должна использовать исходный, а не derived dataset")
        return well, dataset

    def _well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well
