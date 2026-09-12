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


def _numerical_plan(target: Dataset) -> SimpleNamespace:
    return SimpleNamespace(
        target_dataset_id=target.dataset_id,
        start_value=100.0,
        stop_value=101.0,
    )


def _patch_numerical_analysis(monkeypatch, plan: SimpleNamespace) -> None:
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.analyze_well_numerical_update",
        lambda *_args, **_kwargs: plan,
    )


def _patch_persisted_preview(monkeypatch, calls: list[tuple[str, str]]) -> None:
    def _analyze_persisted(
        actual_session: ProjectSession,
        _target: Dataset,
        _source: Dataset,
        *,
        source_name: str,
        source_sha256: str,
    ) -> SimpleNamespace:
        binding = actual_session.rock_code_source_bindings[source_sha256]
        calls.append((source_name, binding.profile_sha256))
        return SimpleNamespace(profile_sha256=binding.profile_sha256)

    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller."
        "analyze_persisted_well_geology_update",
        _analyze_persisted,
    )


def test_numerical_preview_uses_temporary_persisted_binding_without_dirtying_session(
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

    numerical_plan = _numerical_plan(target)
    _patch_numerical_analysis(monkeypatch, numerical_plan)
    persisted_calls: list[tuple[str, str]] = []
    _patch_persisted_preview(monkeypatch, persisted_calls)

    controller = DailyLasGrowthController(session)
    result = controller.analyze_numerical(
        source_path,
        target.dataset_id,
        geology_profile_path=profile_path,
    )

    expected_profile_sha256 = sha256(dictionary.to_json().encode("utf-8")).hexdigest()
    assert result is numerical_plan
    assert controller.geology_plan is not None
    assert controller.geology_plan.profile_sha256 == expected_profile_sha256
    assert persisted_calls == [(source_path.name, expected_profile_sha256)]
    assert session.rock_code_profiles == {}
    assert session.rock_code_source_bindings == {}
    assert session.dirty is False


def test_numerical_apply_persists_profile_assignment_only_on_success(
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

    numerical_plan = _numerical_plan(target)
    _patch_numerical_analysis(monkeypatch, numerical_plan)
    persisted_calls: list[tuple[str, str]] = []
    _patch_persisted_preview(monkeypatch, persisted_calls)

    controller = DailyLasGrowthController(session)
    controller.analyze_numerical(
        source_path,
        target.dataset_id,
        geology_profile_path=profile_path,
    )
    geology_plan = controller.geology_plan
    assert geology_plan is not None
    expected_profile_sha256 = geology_plan.profile_sha256

    def _prepare_persisted(
        actual_session: ProjectSession,
        *_args,
        source_sha256: str,
        **_kwargs,
    ) -> None:
        binding = actual_session.rock_code_source_bindings[source_sha256]
        assert binding.profile_sha256 == expected_profile_sha256
        return None

    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller."
        "prepare_persisted_well_geology_update",
        _prepare_persisted,
    )
    outcome = SimpleNamespace(record=None, geology_record=None)
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.apply_well_numerical_update",
        lambda *_args, **_kwargs: outcome,
    )

    result = controller.apply_numerical(
        numerical_plan,
        geology_plan=geology_plan,
    )

    assert result is outcome
    binding = session.rock_code_source_bindings[source_sha256]
    assert binding.profile_sha256 == expected_profile_sha256
    assert binding.supplier_name == dictionary.source
    assert session.rock_code_profiles[expected_profile_sha256].profile_json == dictionary.to_json()
    assert session.dirty is True


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

    numerical_plan = _numerical_plan(target)
    _patch_numerical_analysis(monkeypatch, numerical_plan)
    persisted_calls: list[tuple[str, str]] = []
    _patch_persisted_preview(monkeypatch, persisted_calls)

    controller = DailyLasGrowthController(session)
    controller.analyze_numerical(
        source_path,
        target.dataset_id,
        geology_profile_path=profile_path,
    )
    geology_plan = controller.geology_plan
    assert geology_plan is not None
    assert session.rock_code_source_bindings == {}

    assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name="Supplier A",
        dictionary=RockCodeDictionary(name="Profile v2", source="Supplier A", entries=()),
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.apply_well_numerical_update",
        lambda *_args, **_kwargs: pytest.fail("numerical apply must not run for stale geology"),
    )

    with pytest.raises(
        DailyLasGrowthError,
        match="Привязка источника к профилю пород изменилась",
    ):
        controller.apply_numerical(
            numerical_plan,
            geology_plan=geology_plan,
        )
