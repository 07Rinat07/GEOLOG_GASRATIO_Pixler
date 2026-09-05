from pathlib import Path

from geoworkbench.data.las_adapter import import_las
from geoworkbench.domain.models import CuttingsSample, LithologyInterval
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.las_geology import import_las_geology, las_code_id
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import load_project
from geoworkbench.tablet.lithology_legend import build_lithology_legend


LAS_FIXTURE = Path(__file__).parent / "fixtures" / "las_geology" / "portable_codes.las"


def test_las_code_id_is_stable_and_validated() -> None:
    assert las_code_id(5) == "las-code-5"


def test_import_las_geology_materializes_codes_and_compositions() -> None:
    session = ProjectSession()
    dataset = import_las(LAS_FIXTURE)
    well = session.add_dataset(dataset, "494")

    assert len(well.lithology) > 0
    assert len(well.cuttings) > 0
    assert {5, 6, 16, 19, 20, 25, 27, 39, 40, 59, 60, 61, 62} <= {
        int(record.code)
        for record in session.project.lithotypes.values()
        if record.lithotype_id.startswith("las-code-")
    }
    assert all(interval.lithotype_id.startswith("las-code-") for interval in well.lithology)
    assert all(
        component.lithotype_id.startswith("las-code-")
        for sample in well.cuttings
        for component in sample.components
    )


def test_import_las_geology_does_not_overwrite_manual_layers() -> None:
    session = ProjectSession()
    dataset = import_las(LAS_FIXTURE)
    well = session.add_dataset(dataset, "494")
    before = (len(well.lithology), len(well.cuttings))
    result = import_las_geology(session)
    assert result.lithology_intervals == 0
    assert result.cuttings_intervals == 0
    assert (len(well.lithology), len(well.cuttings)) == before


def test_reading_codes_refreshes_catalog_when_layers_already_exist() -> None:
    session = ProjectSession()
    well = session.add_dataset(import_las(LAS_FIXTURE), "494")
    well.lithology = [LithologyInterval("manual", 47.0, 48.0, "manual-rock")]
    well.cuttings = [CuttingsSample("manual-cuttings", 47.0, 48.0, [])]
    for identity in tuple(session.project.lithotypes):
        if identity.startswith("las-code-"):
            del session.project.lithotypes[identity]

    result = import_las_geology(session)

    assert result.lithology_intervals == 0
    assert result.cuttings_intervals == 0
    assert "las-code-5" in session.project.lithotypes
    assert len(well.lithology) == 1
    assert len(well.cuttings) == 1


def test_las_code_mapping_can_be_reset_to_neutral_record() -> None:
    session = ProjectSession()
    well = session.add_dataset(import_las(LAS_FIXTURE), "494")
    controller = LithotypeCatalogController(session)

    controller.adapt_las_code(5, "sandstone")
    controller.reset_las_code(5)

    record = session.project.lithotypes["las-code-5"]
    assert record.category == "LAS: unmapped"
    assert record.name_ru == "Неопознанная порода, код 5"
    assert any(item.lithotype_id == "las-code-5" for item in well.lithology)


def test_las_code_mapping_survives_project_round_trip(tmp_path) -> None:
    session = ProjectSession()
    session.add_dataset(import_las(LAS_FIXTURE), "494")
    controller = LithotypeCatalogController(session)
    selected = controller.get("sandstone")
    controller.adapt_las_code(5, selected.lithotype_id)
    target = tmp_path / "mapped-codes.json"

    save_project(session.project, target)
    restored = load_project(target)

    record = restored.lithotypes["las-code-5"]
    assert record.name_ru == selected.name_ru
    assert record.color == selected.color
    assert record.pattern_key == selected.pattern_key


def test_las_code_mapping_changes_visual_contract_without_rewriting_source_id() -> None:
    session = ProjectSession()
    well = session.add_dataset(import_las(LAS_FIXTURE), "494")
    controller = LithotypeCatalogController(session)
    selected = controller.get("sandstone")

    controller.adapt_las_code(5, selected.lithotype_id)

    interval = next(item for item in well.lithology if item.lithotype_id == "las-code-5")
    legend = build_lithology_legend(well.lithology, controller.available())
    mapped = next(item for item in legend if item.lithotype_id == "las-code-5")

    assert interval.lithotype_id == "las-code-5"
    assert mapped.name == selected.name_ru
    assert mapped.color == selected.color
    assert mapped.pattern_key == selected.pattern_key
