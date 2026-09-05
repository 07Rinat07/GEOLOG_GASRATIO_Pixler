from pathlib import Path

import numpy as np

from geoworkbench.data.las_adapter import import_las, import_las_with_report
from geoworkbench.domain.models import (
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    Project,
    Well,
)
from geoworkbench.project.dataset_export_controller import DatasetExportController
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.las_geology import unmapped_las_lithotype
from geoworkbench.services.rock_code_dictionary import (
    RockCodeDictionary,
    RockCodeEntry,
    RockCodeDictionaryError,
    apply_dictionary,
    dictionary_from_session,
    dictionary_from_las_bytes,
    load_dictionary,
    render_las_dictionary_section,
    save_dictionary,
)


def test_dictionary_round_trip_preserves_visual_mapping(tmp_path: Path) -> None:
    session = ProjectSession()
    session.project.lithotypes["las-code-5"] = unmapped_las_lithotype(5)
    dictionary = dictionary_from_session(session, name="Firm A", source="Wellsite program")
    target = tmp_path / "firm-a.rock-codes.json"

    save_dictionary(target, dictionary)
    restored = load_dictionary(target)

    assert restored.name == "Firm A"
    assert restored.source == "Wellsite program"
    assert restored.entries[0].source_code == 5
    assert restored.entries[0].pattern_key == dictionary.entries[0].pattern_key


def test_dictionary_import_merges_without_rewriting_intervals() -> None:
    source = ProjectSession()
    source.project.lithotypes["las-code-5"] = unmapped_las_lithotype(5)
    dictionary = dictionary_from_session(source)
    destination = ProjectSession()
    well = Well("well", "Well")
    well.lithology.append(LithologyInterval("interval", 100.0, 101.0, "las-code-5"))
    destination.project.wells[well.well_id] = well

    created, updated = apply_dictionary(destination, dictionary)

    assert (created, updated) == (1, 0)
    assert destination.project.wells[well.well_id].lithology[0].lithotype_id == "las-code-5"
    assert destination.project.lithotypes["las-code-5"].name_ru.startswith("Неопознанная")


def test_dictionary_rejects_duplicate_external_codes() -> None:
    raw = {
        "schema_version": 1,
        "name": "bad",
        "source": "test",
        "entries": [
            {
                "source_code": 5,
                "lithotype_id": "las-code-5",
                "code": "5",
                "name_ru": "Песчаник",
                "name_kk": "Құмтас",
                "name_en": "Sandstone",
                "category": "clastic",
                "color": "#c9a66b",
                "pattern_key": "sand_dots",
            },
            {
                "source_code": 5,
                "lithotype_id": "las-code-5-alt",
                "code": "5",
                "name_ru": "Известняк",
                "name_kk": "Әктас",
                "name_en": "Limestone",
                "category": "carbonate",
                "color": "#dbeafe",
                "pattern_key": "carbonate",
            },
        ],
    }

    try:
        RockCodeDictionary.from_dict(raw)
    except RockCodeDictionaryError as exc:
        assert "уникальны" in str(exc)
    else:  # pragma: no cover - the assertion documents the safety contract
        raise AssertionError("duplicate source codes must be rejected")


def test_embedded_dictionary_reader_uses_latest_custom_section() -> None:
    first = RockCodeDictionary(
        "first",
        "supplier-a",
        (RockCodeEntry.from_project_lithotype(unmapped_las_lithotype(5), 5),),
    )
    second = RockCodeDictionary(
        "second",
        "supplier-b",
        (RockCodeEntry.from_project_lithotype(unmapped_las_lithotype(6), 6),),
    )

    raw = b"~V\nVERS. 2.0\n~Other legacy dictionary\n" + render_las_dictionary_section(first)
    raw += render_las_dictionary_section(second)

    embedded = dictionary_from_las_bytes(raw)

    assert embedded is not None
    assert embedded.name == "second"
    assert [entry.source_code for entry in embedded.entries] == [6]


def test_las_export_contains_project_geology_and_embedded_dictionary(tmp_path: Path) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    well.lithology = [LithologyInterval("lithology-1", 100.0, 102.0, "las-code-5")]
    well.cuttings = [
        CuttingsSample(
            "cuttings-1",
            100.0,
            102.0,
            [CuttingsComponent("las-code-5", 70.0), CuttingsComponent("las-code-6", 30.0)],
        )
    ]
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )
    session.project.lithotypes["las-code-5"] = unmapped_las_lithotype(5)
    session.project.lithotypes["las-code-6"] = unmapped_las_lithotype(6)
    selected = LithotypeCatalogController(session).get("sandstone")
    LithotypeCatalogController(session).adapt_las_code(5, selected.lithotype_id)
    target = tmp_path / "geology.las"

    DatasetExportController(session).export_current_las(target, overwrite=True)
    exported = import_las(target)

    assert exported.curve_by_mnemonic("КОД_ПОРОДЫ") is not None
    assert exported.curve_by_mnemonic("ПОРОДА1_КОД") is not None
    assert exported.curve_by_mnemonic("ПОРОДА1_КОЛИЧ") is not None
    raw = target.read_bytes()
    assert b"GEOWORKBENCH_ROCK_DICTIONARY" in raw
    embedded = dictionary_from_las_bytes(raw)
    assert embedded is not None
    assert {entry.source_code for entry in embedded.entries} == {5, 6}

    imported = import_las_with_report(target)
    reopened = ProjectSession()
    reopened.add_dataset(imported.dataset, source_document=imported.source_document)
    assert reopened.project.lithotypes["las-code-5"].name_ru == selected.name_ru
