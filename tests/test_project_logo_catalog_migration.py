from __future__ import annotations

from geoworkbench.storage.project_codec import PROJECT_FORMAT_VERSION, project_document_from_dict
from geoworkbench.storage.project_migrations import migrate_project_payload


def test_project_v21_migrates_empty_logo_catalog_to_v22() -> None:
    raw = {
        "format_version": 21,
        "project": {
            "project_id": "project-1",
            "name": "Project",
            "wells": {},
            "lithotypes": {},
            "stratigraphy_units": {},
            "description_templates": {},
            "masterlog_templates": {},
            "custom_formulas": {},
            "export_profiles": {},
            "time_depth_mapping_profiles": {},
        },
        "tablet_layouts": {},
        "tablet_presets": {},
        "source_artifacts": {},
        "import_reports": {},
        "image_assets": {},
    }
    migrated = migrate_project_payload(raw, PROJECT_FORMAT_VERSION)
    assert migrated["format_version"] == 22
    assert migrated["project"]["logo_catalog"] == {}

    document = project_document_from_dict(migrated)
    assert document.project.logo_catalog == {}
