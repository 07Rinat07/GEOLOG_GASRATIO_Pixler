from __future__ import annotations

from geoworkbench.domain.models import Project, new_id
from geoworkbench.project.logo_catalog_controller import LogoCatalogController
from geoworkbench.project.session import ProjectSession


def _session() -> ProjectSession:
    return ProjectSession(Project(new_id(), "Logo catalog test"))


def test_factory_logo_can_be_installed_and_copied_without_mutating_factory() -> None:
    session = _session()
    controller = LogoCatalogController(session)

    factory = controller.item("factory-bpservices")
    assert factory.read_only is True
    assert factory.name == "BPServices"

    preview_asset = controller.resolve_asset(factory.logo_id, install=False)
    assert preview_asset.asset_id not in session.image_assets

    asset = controller.resolve_asset(factory.logo_id)
    assert asset.asset_id in session.image_assets
    assert asset.payload.startswith(b"\x89PNG\r\n\x1a\n")

    copied = controller.copy_factory(factory.logo_id, name="BPServices — проект")
    assert copied.logo_id in session.project.logo_catalog
    assert copied.asset_id == asset.asset_id
    assert session.dirty is True


def test_user_logo_metadata_duplicate_replace_and_delete_contract() -> None:
    session = _session()
    controller = LogoCatalogController(session)
    source = controller.copy_factory("factory-bpservices", name="Исполнитель")

    updated = controller.update_metadata(
        source.logo_id,
        name="Исполнитель основной",
        category="Исполнитель",
        notes="Для титульной шапки",
    )
    assert updated.version == 2
    assert updated.category == "Исполнитель"

    duplicate = controller.duplicate(updated.logo_id, "Исполнитель резервный")
    assert duplicate.logo_id != updated.logo_id
    assert duplicate.asset_id == updated.asset_id

    removed = controller.delete(updated.logo_id)
    assert removed.logo_id not in session.project.logo_catalog
    assert duplicate.logo_id in session.project.logo_catalog
    assert duplicate.asset_id in session.image_assets


def test_logo_catalog_round_trips_with_content_addressed_asset(tmp_path) -> None:
    from geoworkbench.storage.atomic_json import save_project
    from geoworkbench.storage.project_codec import load_project_document

    session = _session()
    controller = LogoCatalogController(session)
    entry = controller.copy_factory("factory-bpservices", name="BPServices project")
    target = tmp_path / "logos.geolog.json"

    save_project(session.project, target, image_assets=session.image_assets)
    loaded = load_project_document(target)

    restored = loaded.project.logo_catalog[entry.logo_id]
    assert restored.name == entry.name
    assert restored.asset_id == entry.asset_id
    assert restored.asset_id in loaded.image_assets
