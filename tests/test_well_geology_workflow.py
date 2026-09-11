from dataclasses import asdict
from pathlib import Path

import pytest

from test_well_geology_update import encoded, profile
from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.models import Project
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import DailyLasGrowthError
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.storage.project_migrations import migrate_project_payload


def setup_update(tmp_path):
    source = tmp_path / "daily.las"
    fixture = Path(__file__).parent / "fixtures/las_geology/portable_codes.las"
    source.write_bytes(fixture.read_bytes())
    imported = import_las_with_report(source)
    session = ProjectSession(project=Project("p", "Project"))
    session.add_dataset(imported.dataset, source_document=imported.source_document,
                        import_report=imported.report, create_new_well=True)
    # Model an existing project whose geological gaps have not been interpreted.
    session.current_well.lithology.clear()
    session.current_well.cuttings.clear()
    from dataclasses import replace
    dictionary = profile()
    codes = (5, 6, 16, 19, 20, 25, 27, 39, 40, 59, 60, 61, 62)
    dictionary = replace(dictionary, entries=tuple(
        replace(dictionary.entries[0], source_code=code, lithotype_id=f"rock-{code}", code=str(code))
        for code in codes
    ))
    supplier = tmp_path / "supplier.json"
    supplier.write_text(dictionary.to_json(), encoding="utf-8")
    session.dirty = False
    return DailyLasGrowthController(session), source, supplier


def test_geology_only_roundtrip_retains_profile_and_raw_source(tmp_path):
    controller, source, supplier = setup_update(tmp_path)
    target = controller.session.current_dataset
    plan = controller.analyze_numerical(source, target.dataset_id, geology_profile_path=supplier)
    outcome = controller.apply_numerical(plan, geology_plan=controller.geology_plan)
    assert outcome.record is None
    assert outcome.geology_record is not None
    assert controller.session.dirty
    assert target.geology_update_history == [outcome.geology_record]
    assert len(target.source_revisions) == 2
    assert outcome.geology_record.profile_json == supplier.read_text(encoding="utf-8")
    repository = PackageProjectRepository()
    path = tmp_path / "well.geologpkg"
    repository.save(ProjectDocument(controller.session.project, source_documents=controller.session.source_documents), path)
    loaded = repository.load(path)
    well = loaded.project.wells[controller.session.current_well_id]
    assert well.datasets[target.dataset_id].geology_update_history == target.geology_update_history
    assert well.lithology == controller.session.current_well.lithology
    assert well.cuttings == controller.session.current_well.cuttings
    assert loaded.source_documents == controller.session.source_documents
    fresh = controller.analyze_numerical(source, target.dataset_id, geology_profile_path=supplier)
    assert controller.apply_numerical(fresh, geology_plan=controller.geology_plan).geology_record is None


@pytest.mark.parametrize("failure", ["profile", "artifact"])
def test_geology_failure_restores_entire_project(tmp_path, monkeypatch, failure):
    controller, source, supplier = setup_update(tmp_path)
    target = controller.session.current_dataset
    plan = controller.analyze_numerical(source, target.dataset_id, geology_profile_path=supplier)
    geology = controller.geology_plan
    before = encoded(asdict(controller.session.project))
    documents = dict(controller.session.source_documents)
    if failure == "profile":
        supplier.write_text(supplier.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    else:
        def fail(*args, **kwargs):
            raise OSError("injected artifact failure")
        monkeypatch.setattr(controller, "_preserve_initial_source", fail)
    with pytest.raises((DailyLasGrowthError, OSError)):
        controller.apply_numerical(plan, geology_plan=geology)
    assert encoded(asdict(controller.session.project)) == before
    assert controller.session.source_documents == documents
    assert not controller.session.dirty
    assert controller.geology_plan is None


def test_v26_migration_only_adds_empty_geological_history():
    payload = {"format_version": 26, "project": {"wells": {"w": {"datasets": {
        "d": {"numerical_update_history": [{"legacy": True}]},
    }, "lithology": [{"interval_id": "legacy", "description": "manual"}]}}}}
    before = encoded(payload)
    result = migrate_project_payload(payload, 27)
    assert result["format_version"] == 27
    dataset = result["project"]["wells"]["w"]["datasets"]["d"]
    assert dataset.pop("geology_update_history") == []
    result["format_version"] = 26
    assert result == payload
    assert encoded(payload) == before
