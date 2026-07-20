from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    IndexRole,
    TimeDepthAggregationPolicy,
    TimeDepthMappingProfile,
    new_id,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.time_depth_mapping import TimeDepthMatch, resolve_time_to_depth


@dataclass(slots=True)
class TimeDepthMappingController:
    session: ProjectSession

    def save_profile(
        self,
        name: str,
        time_index_id: str,
        depth_index_id: str,
        policy: TimeDepthAggregationPolicy,
    ) -> TimeDepthMappingProfile:
        dataset = self._require_current_dataset()
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Имя TIME↔DEPTH профиля не может быть пустым")
        if any(
            profile.name.casefold() == normalized_name.casefold()
            for profile in self.session.project.time_depth_mapping_profiles.values()
        ):
            raise ValueError(f"TIME↔DEPTH профиль уже существует: {normalized_name}")
        self._require_index(dataset.indexes, time_index_id, IndexRole.TIME)
        self._require_index(dataset.indexes, depth_index_id, IndexRole.DEPTH)
        if not isinstance(policy, TimeDepthAggregationPolicy):
            raise ValueError("Неизвестная политика TIME↔DEPTH mapping")
        profile = TimeDepthMappingProfile(
            new_id(),
            normalized_name,
            dataset.dataset_id,
            time_index_id,
            depth_index_id,
            policy,
        )
        self.session.project.time_depth_mapping_profiles[profile.profile_id] = profile
        self.session.dirty = True
        return profile

    def resolve(self, profile_id: str, time_value: str) -> TimeDepthMatch:
        try:
            profile = self.session.project.time_depth_mapping_profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"TIME↔DEPTH профиль не найден: {profile_id}") from exc
        dataset = self._require_current_dataset()
        if dataset.dataset_id != profile.dataset_id:
            raise ValueError("TIME↔DEPTH профиль относится к другому набору данных")
        return resolve_time_to_depth(
            dataset,
            time_value,
            time_index_id=profile.time_index_id,
            depth_index_id=profile.depth_index_id,
            policy=profile.aggregation_policy,
        )

    def delete_profile(self, profile_id: str) -> None:
        if profile_id not in self.session.project.time_depth_mapping_profiles:
            raise KeyError(f"TIME↔DEPTH профиль не найден: {profile_id}")
        del self.session.project.time_depth_mapping_profiles[profile_id]
        self.session.dirty = True

    def _require_current_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset

    @staticmethod
    def _require_index(indexes: dict[str, DatasetIndex], index_id: str, role: IndexRole) -> None:
        index = indexes.get(index_id)
        if index is None or index.role is not role:
            raise ValueError(f"Индекс {index_id} не имеет роль {role.value}")
