from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import DailyLasGrowthError
from geoworkbench.services.persisted_rock_code_profile_assignment import (
    assign_persisted_rock_code_profile,
)
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary


def _dataset(dataset_id: str) -> Dataset:
    return Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([100.0, 101.0], dtype=float),
    )


def _session() -> tuple[ProjectSession, Dataset]:
    target = _dataset("target")
    well = Well("well-1", "Well", datasets={target.dataset_id: target})
    session = ProjectSession(
        project=Project("project-1", "Daily project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=target.dataset_id,
    )
    return session, target


def _write_source(path: Path) -> str:
    path.write_bytes(b"daily-las-source")
    return sha256(path.read_bytes()).hexdigest()


def _write_profile(path: Path, *, name: str = "Profile v1") -> RockCodeDictionary:
    dictionary = RockCodeDictionary(name=name, source="Supplier A", entries=())
    path.write_text(dictionary.to_json(), encoding="utf-8")
    return dictionary


def _patch_import(monkeypatch, *, source_sha256: str, source: Dataset) -> None:
    imported = SimpleNamespace(
        dataset=source,
        report=SimpleNamespace(source=SimpleNamespace(sha256=source_sha256)),
        source_document=SimpleNamespace(size_bytes=len(b"daily-las-source")),
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.import_las_with_report",
        lambda *_args, **_kwargs: imported,
    )


def test_numerical_preview_persists_exact_profile_binding_and_uses_persisted_boundary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session, target = _session()
    source = _dataset("source")
    source_path = tmp_path / "daily.las"
    source_sha256 = _write_source(source_path)
    profile_path = tmp_path / "supplier-profile.json"
    dictionary = _write_profile(profile_path)
    _patch_import(monkeypatch, source_sha256=source_sha256, source=source)

    numerical_plan = SimpleNamespace(
        target_dataset_id=target.dataset_id,
        start_value=100.0,
        stop_value=101.0,
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.analyze_well_numerical_update",
        lambda *_args, **_kwargs: numerical_plan,
    )
    persisted_calls: list[tuple[ProjectSession, Dataset, Dataset, str, str]] = []

    def _analyze_persisted(
        actual_session: ProjectSession,
        actual_target: Dataset,
        actual_source: Dataset,
        *,
        source_name: str,
        source_sha256: str,
    ) -> SimpleNamespace:
        persisted_calls.append(
            (actual_session, actual_target, actual_source, source_name, source_sha256)
        )
        binding = actual_session.rock_code_source_bindings[source_sha256]
        return SimpleNamespace(profile_sha256=binding.profile_sha256)

    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller."
        "analyze_persisted_well_geology_update",
        _analyze_persisted,
    )

    controller = DailyLasGrowthController(session)
    result = controller.analyze_numerical(
        source_path,
        target.dataset_id,
        geology_profile_path=profile_path,
    )

    expected_profile_sha256 = sha256(dictionary.to_json().encode("utf-8")).hexdigest()
    binding = session.rock_code_source_bindings[source_sha256]
    assert result is numerical_plan
    assert binding.profile_sha256 == expected_profile_sha256
    assert binding.supplier_name == "Supplier A"
    assert session.rock_code_profiles[expected_profile_sha256].profile_json == dictionary.to_json()
    assert controller.geology_plan is not None
    assert controller.geology_plan.profile_sha256 == expected_profile_sha256
    assert persisted_calls == [(session, target, source, source_path.name, source_sha256)]


def test_numerical_apply_rejects_profile_reassignment_after_preview(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session, target = _session()
    source = _dataset("source")
    source_path = tmp_path / "daily.las"
    source_sha256 = _write_source(source_path)
    profile_path = tmp_path / "supplier-profile.json"
    _write_profile(profile_path)
    _patch_import(monkeypatch, source_sha256=source_sha256, source=source)

    numerical_plan = SimpleNamespace(
        target_dataset_id=target.dataset_id,
        start_value=100.0,
        stop_value=101.0,
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.analyze_well_numerical_update",
        lambda *_args, **_kwargs: numerical_plan,
    )

    def _analyze_persisted(
        actual_session: ProjectSession,
        _target: Dataset,
        _source: Dataset,
        *,
        source_name: str,
        source_sha256: str,
    ) -> SimpleNamespace:
        del source_name
        binding = actual_session.rock_code_source_bindings[source_sha256]
        return SimpleNamespace(profile_sha256=binding.profile_sha256)

    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller."
        "analyze_persisted_well_geology_update",
        _analyze_persisted,
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.apply_well_numerical_update",
        lambda *_args, **_kwargs: pytest.fail("numerical apply must not run for stale geology"),
    )

    controller = DailyLasGrowthController(session)
    controller.analyze_numerical(
        source_path,
        target.dataset_id,
        geology_profile_path=profile_path,
    )
    geology_plan = controller.geology_plan
    assert geology_plan is not None

    assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name="Supplier A",
        dictionary=RockCodeDictionary(name="Profile v2", source="Supplier A", entries=()),
    )

    with pytest.raises(
        DailyLasGrowthError,
        match="Привязка источника к профилю пород изменилась",
    ):
        controller.apply_numerical(
            numerical_plan,
            geology_plan=geology_plan,
        )
