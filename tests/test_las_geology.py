import base64
import json
from pathlib import Path
import zlib

from geoworkbench.data.las_adapter import import_las, import_las_with_report
from geoworkbench.domain.models import CuttingsSample, LithologyInterval
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.interpretation_report import build_interpretation_report
from geoworkbench.services.las_geology import (
    dataset_with_well_geology,
    import_las_geology,
    las_code_id,
)
from geoworkbench.services.las_geology_metadata import geology_metadata_from_las_bytes
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


def _enriched_cp1251_las() -> bytes:
    metadata = {
        "schema_version": 1,
        "source": "unit test",
        "descriptions": {
            "1": {
                "top": 1000.0,
                "bottom": 1002.0,
                "text_ru": "Песчаник серый, мелкозернистый.",
            }
        },
        "stratigraphy": [
            {
                "top": 1000.0,
                "bottom": 1002.0,
                "short": "K",
                "name_ru": "Меловая система",
            }
        ],
        "lba_type_codes": {"2": "МБ"},
        "lba_color_codes": {"3": "БЖ"},
    }
    compressed = zlib.compress(
        json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
        9,
    )
    encoded = base64.b64encode(compressed).decode("ascii")
    other = [
        "~Other information",
        "# GEOWORKBENCH_GEOLOGY_METADATA schema=1",
    ]
    for offset in range(0, len(encoded), 72):
        prefix = (
            "# GEOLOGY_ZLIB_BASE64="
            if offset == 0
            else "# GEOLOGY_ZLIB_BASE64_CONT="
        )
        other.append(prefix + encoded[offset : offset + 72])

    text = "\n".join(
        [
            "~Version Information",
            " VERS. 2.0 : LAS 2.0",
            " WRAP. NO : One row per depth",
            "~Well Information",
            " STRT.M 1000.0 : Start",
            " STOP.M 1001.0 : Stop",
            " STEP.M 1.0 : Step",
            " NULL. -999.25 : Null",
            " WELL. Тест : Well",
            "~Curve Information",
            " DEPT.M : Глубина",
            " КОД_ПОРОДЫ.CODE : Основная порода",
            " ПОРОДА1_КОД.CODE : Код компонента",
            " ПОРОДА1_КОЛИЧ.PCT : Содержание компонента",
            " CACO3.% : Кальцит",
            " CAMG_CO3_2.% : Доломит",
            " LBA_GROUP.CODE : Группа ЛБА",
            " INTENSITY_LBA.CODE : Интенсивность ЛБА",
            " ZVET_LBA.CODE : Цвет ЛБА",
            " GEO_DESC_ID.CODE : Описание",
            " STRAT_CODE.CODE : Стратиграфия",
            *other,
            "~ASCII Log Data",
            "1000 5 5 100 30 10 2 3 3 1 1",
            "1001 5 5 100 30 10 2 3 3 1 1",
            "",
        ]
    )
    return text.encode("cp1251")


def test_enriched_las_materializes_calcimetry_lba_description_and_stratigraphy(
    tmp_path: Path,
) -> None:
    source = tmp_path / "enriched-geology.las"
    source.write_bytes(_enriched_cp1251_las())

    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Тест",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )

    assert len(well.lithology) == 1
    assert len(well.cuttings) == 1
    sample = well.cuttings[0]
    assert sample.calcite_percent == 30.0
    assert sample.dolomite_percent == 10.0
    assert sample.insoluble_residue_percent == 60.0
    assert sample.lba_group == 2
    assert sample.lba_type_id == "oily"
    assert sample.lba_intensity == 3
    assert sample.lba_color == "БЖ"
    assert sample.description == "Песчаник серый, мелкозернистый."

    assert len(well.stratigraphy) == 1
    stratigraphy = well.stratigraphy[0]
    assert stratigraphy.top_depth == 1000.0
    assert stratigraphy.bottom_depth == 1001.0
    assert stratigraphy.code == "K"
    assert stratigraphy.name == "Меловая система"


def test_invalid_optional_geology_metadata_never_blocks_las_opening() -> None:
    raw = (
        b"~Other information\n"
        b"# GEOWORKBENCH_GEOLOGY_METADATA schema=1\n"
        b"# GEOLOGY_ZLIB_BASE64=not-base64!\n"
    )

    assert geology_metadata_from_las_bytes(raw) is None


def _metadata_payload_section(metadata: dict, *, compressed: bytes | None = None) -> bytes:
    payload = compressed
    if payload is None:
        payload = zlib.compress(
            json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            9,
        )
    encoded = base64.b64encode(payload).decode("ascii")
    lines = [
        "~Other information",
        "# GEOWORKBENCH_GEOLOGY_METADATA schema=1",
    ]
    for offset in range(0, len(encoded), 72):
        prefix = (
            "# GEOLOGY_ZLIB_BASE64="
            if offset == 0
            else "# GEOLOGY_ZLIB_BASE64_CONT="
        )
        lines.append(prefix + encoded[offset : offset + 72])
    return ("\n".join(lines) + "\n").encode("ascii")


def _small_geology_las(
    curves: tuple[str, ...],
    rows: tuple[str, ...],
    *,
    metadata: dict | None = None,
) -> bytes:
    parts = [
        "~Version Information",
        " VERS. 2.0 : LAS 2.0",
        " WRAP. NO : One row per depth",
        "~Well Information",
        " STRT.M 0 : Start",
        " STOP.M 101 : Stop",
        " STEP.M 1 : Step",
        " NULL. -999.25 : Null",
        " WELL. Test : Well",
        "~Curve Information",
        " DEPT.M : Depth",
        *curves,
    ]
    raw = ("\n".join(parts) + "\n").encode("utf-8")
    if metadata is not None:
        raw += _metadata_payload_section(metadata)
    raw += ("~ASCII Log Data\n" + "\n".join(rows) + "\n").encode("utf-8")
    return raw


def _base_metadata(**overrides) -> dict:
    metadata = {
        "schema_version": 1,
        "source": "unit test",
        "descriptions": {},
        "stratigraphy": [],
        "lba_type_codes": {},
        "lba_color_codes": {},
    }
    metadata.update(overrides)
    return metadata


def test_metadata_without_usable_stratigraphy_falls_back_to_strat_code(tmp_path: Path) -> None:
    source = tmp_path / "strat-fallback.las"
    source.write_bytes(
        _small_geology_las(
            (" STRAT_CODE.CODE : Stratigraphy",),
            ("0 7", "1 7"),
            metadata=_base_metadata(),
        )
    )
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Test",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )

    assert len(well.stratigraphy) == 1
    assert well.stratigraphy[0].code == "7"


def test_metadata_stratigraphy_requires_retained_strat_code_channel(tmp_path: Path) -> None:
    source = tmp_path / "strat-channel-gate.las"
    metadata = _base_metadata(
        stratigraphy=[
            {
                "top": 0.0,
                "bottom": 1.0,
                "short": "K",
                "name_ru": "Меловая система",
            }
        ],
    )
    source.write_bytes(
        _small_geology_las(
            (" LBA_GROUP.CODE : LBA group",),
            ("0 2", "1 2"),
            metadata=metadata,
        )
    )
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Test",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )

    assert well.stratigraphy == []


def test_strat_code_does_not_bridge_unsampled_depth_gap(tmp_path: Path) -> None:
    source = tmp_path / "strat-gap.las"
    source.write_bytes(
        _small_geology_las(
            (" STRAT_CODE.CODE : Stratigraphy",),
            ("0 1", "1 1", "100 1", "101 1"),
        )
    )
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Test",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )

    assert [(item.top_depth, item.bottom_depth) for item in well.stratigraphy] == [
        (0.0, 1.0),
        (100.0, 101.0),
    ]


def test_calcimetry_total_above_one_hundred_is_not_materialized(tmp_path: Path) -> None:
    source = tmp_path / "invalid-calcimetry.las"
    source.write_bytes(
        _small_geology_las(
            (
                " CACO3.% : Calcite",
                " CAMG_CO3_2.% : Dolomite",
            ),
            ("0 80 40", "1 80 40"),
        )
    )
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Test",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )

    assert well.cuttings == []


def test_localized_calcite_alias_passes_early_geology_gate(tmp_path: Path) -> None:
    source = tmp_path / "localized-calcite.las"
    source.write_bytes(
        _small_geology_las(
            (" CACO3_(КАЛЬЦИТ).% : Calcite",),
            ("0 30", "1 30"),
        )
    )
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Test",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )

    assert len(well.cuttings) == 1
    assert well.cuttings[0].calcite_percent == 30.0


def test_unknown_metadata_lba_type_falls_back_to_lba_group(tmp_path: Path) -> None:
    source = tmp_path / "lba-fallback.las"
    source.write_bytes(
        _small_geology_las(
            (
                " LBA_GROUP.CODE : LBA group",
                " LBA_TYPE.CODE : LBA type",
            ),
            ("0 3 2", "1 3 2"),
            metadata=_base_metadata(lba_type_codes={"2": "VENDOR_UNKNOWN"}),
        )
    )
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Test",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )

    assert len(well.cuttings) == 1
    assert well.cuttings[0].lba_group == 3
    assert well.cuttings[0].lba_type_id == "oily_resinous"


def test_optional_metadata_rejects_recursion_truncation_trailing_and_overlap() -> None:
    recursive_json = ("[" * 2000 + "0" + "]" * 2000).encode("ascii")
    recursive_raw = (
        b"~Other information\n"
        b"# GEOWORKBENCH_GEOLOGY_METADATA schema=1\n"
        + b"# GEOLOGY_ZLIB_BASE64="
        + base64.b64encode(zlib.compress(recursive_json))
        + b"\n"
    )
    assert geology_metadata_from_las_bytes(recursive_raw) is None

    valid = _base_metadata()
    compressed = zlib.compress(
        json.dumps(valid, separators=(",", ":")).encode("utf-8"),
        9,
    )
    assert geology_metadata_from_las_bytes(
        _metadata_payload_section(valid, compressed=compressed[:-4])
    ) is None
    assert geology_metadata_from_las_bytes(
        _metadata_payload_section(valid, compressed=compressed + b"junk")
    ) is None

    overlap = _base_metadata(
        stratigraphy=[
            {
                "top": 0.0,
                "bottom": 10.0,
                "short": "K1",
                "name_ru": "A",
                "rank": "system",
            },
            {
                "top": 5.0,
                "bottom": 12.0,
                "short": "K2",
                "name_ru": "B",
                "rank": "SYSTEM",
            },
        ],
    )
    assert geology_metadata_from_las_bytes(_metadata_payload_section(overlap)) is None


def test_optional_metadata_rejects_oversized_base64_before_materialization() -> None:
    raw = (
        b"~Other information\n"
        b"# GEOWORKBENCH_GEOLOGY_METADATA schema=1\n"
        b"# GEOLOGY_ZLIB_BASE64="
        + b"A" * (3 * 1024 * 1024)
        + b"\n"
    )
    assert geology_metadata_from_las_bytes(raw) is None


def test_export_projects_edited_calcimetry_and_lba_back_to_curves(tmp_path: Path) -> None:
    source = tmp_path / "enriched-roundtrip.las"
    source.write_bytes(_enriched_cp1251_las())
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset,
        "Тест",
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )
    sample = well.cuttings[0]
    sample.calcite_percent = 45.0
    sample.dolomite_percent = 15.0
    sample.lba_group = 2
    sample.lba_type_id = "oily"
    sample.lba_intensity = 4
    sample.lba_color = "БЖ"

    exported = dataset_with_well_geology(session)
    assert exported is not None
    assert exported.curve_by_mnemonic("CACO3").values.tolist() == [45.0, 45.0]
    assert exported.curve_by_mnemonic("CAMG_CO3_2").values.tolist() == [15.0, 15.0]
    assert exported.curve_by_mnemonic("LBA_GROUP").values.tolist() == [2.0, 2.0]
    assert exported.curve_by_mnemonic("INTENSITY_LBA").values.tolist() == [4.0, 4.0]
    assert exported.curve_by_mnemonic("ZVET_LBA").values.tolist() == [3.0, 3.0]


def _legacy_maksat_geology_las() -> bytes:
    text = "\n".join(
        [
            "~Version Information",
            " VERS. 2.0 : LAS 2.0",
            " WRAP. NO : One row per depth",
            "~Well Information",
            " STRT.M 780.0 : Start",
            " STOP.M 781.0 : Stop",
            " STEP.M 1.0 : Step",
            " NULL. -999.25 : Null",
            " WELL. М-1 : Well",
            "~Curve Information",
            " DEPT.M : Глубина",
            " КОД_ПОРОДЫ.CODE : Основная порода",
            " ПОРОДА1_КОД.CODE : Код компонента шлама",
            " ПОРОДА1_КОЛИЧ.PCT : Содержание компонента",
            " КАРБОНАТНОСТЬ.% : Суммарная карбонатность",
            " ЛБА_ГРУППА.CODE : Группа ЛБА",
            " СТРАТ_КОД.CODE : Стратиграфический код",
            " ОПИСАНИЕ_ID.CODE : ID описания породы",
            "~Other information",
            "# GEOLOGY_SOURCE=Мастерлог_Максат-1_51-5549м(1).pdf",
            "# STRAT id=1; top=780; bottom=782; code=K; rank=Система; name=Меловая система",
            (
                "# DESC id=1; top=780; bottom=782; text="
                "Мергель серый, плотный, глинистый."
            ),
            "~ASCII Log Data",
            "780 3 3 100 43 1 1 1",
            "781 3 3 100 43 1 1 1",
            "",
        ]
    )
    return text.encode("cp1251")


def test_legacy_maksat_cyrillic_geology_materializes_all_available_layers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "geology of Maksat M1 from to 5549m.las"
    source.write_bytes(_legacy_maksat_geology_las())

    imported = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        imported.dataset,
        "М-1",
        source_document=imported.source_document,
        import_report=imported.report,
        create_new_well=True,
    )

    assert len(well.lithology) == 1
    assert len(well.cuttings) == 1
    sample = well.cuttings[0]
    assert sample.components[0].percentage == 100.0
    assert sample.total_carbonate_percent == 43.0
    assert sample.calcite_percent is None
    assert sample.dolomite_percent is None
    assert sample.insoluble_residue_percent == 57.0
    assert sample.lba_group == 1
    assert sample.lba_type_id == "light"
    assert sample.description == "Мергель серый, плотный, глинистый."

    assert len(well.stratigraphy) == 1
    stratigraphy = well.stratigraphy[0]
    assert stratigraphy.code == "K"
    assert stratigraphy.name == "Меловая система"
    assert stratigraphy.rank == "Система"

    report = build_interpretation_report(session)
    assert report.sample_count == 1
    assert report.calcimetry_count == 1
    assert report.lba_count == 1
    assert len(report.stratigraphy) == 1
    assert report.entries[0].rock_description == "Мергель серый, плотный, глинистый."
    assert report.entries[0].total_carbonate_percent == 43.0


def test_legacy_total_carbonate_survives_project_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "legacy-maksat.las"
    source.write_bytes(_legacy_maksat_geology_las())
    imported = import_las_with_report(source)
    session = ProjectSession()
    session.add_dataset(
        imported.dataset,
        "М-1",
        source_document=imported.source_document,
        import_report=imported.report,
        create_new_well=True,
    )
    project_path = tmp_path / "maksat.geoworkbench.json"
    save_project(session.project, project_path)

    reopened = load_project(project_path)
    sample = next(iter(reopened.wells.values())).cuttings[0]
    assert sample.total_carbonate_percent == 43.0
    assert sample.insoluble_residue_percent == 57.0


def test_legacy_total_carbonate_exports_without_becoming_calcite(tmp_path: Path) -> None:
    source = tmp_path / "legacy-maksat-export.las"
    source.write_bytes(_legacy_maksat_geology_las())
    imported = import_las_with_report(source)
    session = ProjectSession()
    session.add_dataset(
        imported.dataset,
        "М-1",
        source_document=imported.source_document,
        import_report=imported.report,
        create_new_well=True,
    )

    exported = dataset_with_well_geology(session)

    assert exported is not None
    carbonate = exported.curve_by_mnemonic("КАРБОНАТНОСТЬ")
    assert carbonate is not None
    assert carbonate.values.tolist() == [43.0, 43.0]
    assert exported.curve_by_mnemonic("CACO3") is None
