from __future__ import annotations

import json

import pytest

from geoworkbench.forms import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormFormatError,
    FormRepository,
    FormTrack,
    ParameterBinding,
    factory_templates,
    build_masterlog_from_form,
    form_from_dict,
    form_to_dict,
)
from geoworkbench.tablet.models import TrackKind


def test_form_round_trip_preserves_binding() -> None:
    binding = ParameterBinding.create("TOTAL_GAS", "Total Gas", source_mnemonic="TGAS", unit="%")
    track = FormTrack.create(
        "Газ",
        TrackKind.CURVE,
        bindings=[binding],
        grid_major_divisions=4,
        grid_minor_divisions=10,
        grid_print=False,
        title_orientation="vertical_bottom_to_top",
        title_position="bottom",
    )
    column = FormColumn.create(
        "Газ",
        tracks=[track],
        title_orientation="vertical_top_to_bottom",
        title_position="top",
    )
    form = FormDocument.create("Моя форма", FormAxisKind.DEPTH)
    form.add_column(column)

    restored = form_from_dict(form_to_dict(form))

    assert restored.name == "Моя форма"
    assert restored.columns[0].tracks[0].bindings[0].canonical_parameter_id == "TOTAL_GAS"
    assert restored.columns[0].tracks[0].bindings[0].source_mnemonic == "TGAS"
    assert restored.columns[0].title_orientation == "vertical_top_to_bottom"
    assert restored.columns[0].title_position == "top"
    assert restored.columns[0].tracks[0].title_orientation == "vertical_bottom_to_top"
    assert restored.columns[0].tracks[0].title_position == "bottom"
    assert restored.columns[0].tracks[0].grid_major_divisions == 4
    assert restored.columns[0].tracks[0].grid_minor_divisions == 10
    assert restored.columns[0].tracks[0].grid_print is False


def test_form_grid_settings_control_linked_masterlog_print_grid() -> None:
    binding = ParameterBinding.create("ROP", "ROP", source_mnemonic="ROP", unit="m/h")
    track = FormTrack.create(
        "ROP",
        TrackKind.CURVE,
        bindings=[binding],
        grid_x=True,
        grid_y=True,
        grid_major_divisions=4,
        grid_minor_divisions=10,
        grid_alpha=0.35,
        grid_print=False,
    )
    form = FormDocument.create("Print grid", FormAxisKind.DEPTH)
    form.add_column(FormColumn.create("ROP", tracks=[track]))

    report = build_masterlog_from_form(form, template_id="print-grid")
    column = report.template.columns[0]

    assert column.grid_x is False
    assert column.grid_y is False
    assert column.grid_major_divisions == 4
    assert column.grid_minor_divisions == 10
    assert column.grid_alpha == 0.35


def test_factory_templates_are_read_only_and_copy_is_editable() -> None:
    template = factory_templates()["factory-gas-ratio"]

    assert template.read_only is True
    with pytest.raises(PermissionError):
        template.add_column(FormColumn.create("Новая"))

    copy = template.editable_copy(name="Моя Gas Ratio")
    copy.add_column(FormColumn.create("Дополнительная"))
    assert copy.read_only is False
    assert copy.name == "Моя Gas Ratio"


def test_factory_templates_have_unique_ids() -> None:
    templates = factory_templates()
    assert len(templates) == 19
    assert len({item.form_id for item in templates.values()}) == len(templates)
    for form in templates.values():
        form.validate()


def test_duplicate_binding_ids_are_rejected() -> None:
    binding = ParameterBinding.create("C1", "Метан")
    with pytest.raises(ValueError, match="binding_id"):
        FormTrack.create("Газ", TrackKind.CURVE, bindings=[binding, binding])


def test_repository_saves_utf8_atomically(tmp_path) -> None:
    form = FormDocument.create("Глубинная форма", FormAxisKind.DEPTH)
    form.add_column(FormColumn.create("Глубина"))
    repository = FormRepository(tmp_path)

    target = repository.save(form)
    restored = repository.load(form.form_id)

    assert target.exists()
    assert restored.name == "Глубинная форма"
    raw = json.loads(target.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 4


def test_repository_lists_and_deletes(tmp_path) -> None:
    repository = FormRepository(tmp_path)
    first = FormDocument.create("A", FormAxisKind.DEPTH)
    second = FormDocument.create("B", FormAxisKind.TIME)
    repository.save(first)
    repository.save(second)

    assert {item.name for item in repository.list_forms()} == {"A", "B"}
    repository.delete(first.form_id)
    assert [item.name for item in repository.list_forms()] == ["B"]


def test_schema_zero_is_migrated() -> None:
    restored = form_from_dict(
        {
            "form_id": "legacy-form",
            "name": "Legacy",
            "axis_kind": "depth",
            "columns": [],
        }
    )
    assert restored.style_id == "default-screen"


def test_schema_one_adds_default_title_presentation() -> None:
    restored = form_from_dict(
        {
            "schema_version": 1,
            "form_id": "legacy-form-v1",
            "name": "Legacy v1",
            "axis_kind": "depth",
            "style_id": "default-screen",
            "columns": [
                {
                    "column_id": "column-1",
                    "title": "Колонка",
                    "width": 320,
                    "tracks": [
                        {
                            "track_id": "track-1",
                            "title": "Дорожка",
                            "kind": "curve",
                            "width": 280,
                            "bindings": [],
                        }
                    ],
                }
            ],
        }
    )

    assert restored.columns[0].title_orientation == "horizontal"
    assert restored.columns[0].title_position == "center"
    assert restored.columns[0].tracks[0].title_orientation == "horizontal"
    assert restored.columns[0].tracks[0].title_position == "center"


def test_unknown_schema_is_rejected() -> None:
    with pytest.raises(FormFormatError, match="Неподдерживаемая"):
        form_from_dict({"schema_version": 99})


@pytest.mark.parametrize("field", ["grid_major_divisions", "grid_minor_divisions"])
def test_form_grid_divisions_reject_fractional_values(field: str) -> None:
    form = FormDocument.create("Grid", FormAxisKind.DEPTH)
    form.add_column(
        FormColumn.create("Curve", tracks=[FormTrack.create("Curve", TrackKind.CURVE)])
    )
    payload = form_to_dict(form)
    payload["columns"][0]["tracks"][0][field] = 2.5

    with pytest.raises(FormFormatError, match="Некорректная структура"):
        form_from_dict(payload)


def test_factory_templates_include_specialized_gas_ratio_pixler_workflows() -> None:
    templates = factory_templates()

    assert {
        "factory-gas-ratio-pixler-depth",
        "factory-gas-ratio-pixler-time",
        "factory-normalized-gas-qc",
        "factory-c1-c5-detailed",
    }.issubset(templates)

    depth_form = templates["factory-gas-ratio-pixler-depth"]
    assert depth_form.axis_kind is FormAxisKind.DEPTH
    assert [column.column_id for column in depth_form.columns] == [
        "column-depth-axis",
        "column-drilling",
        "column-mud",
        "column-raw-normalized-gas",
        "column-components",
        "column-ratios",
        "column-pixler-ratios",
        "column-lithology",
        "column-interpretation",
    ]
    canonical = {
        binding.canonical_parameter_id
        for column in depth_form.columns
        for track in column.tracks
        for binding in track.bindings
    }
    assert {
        "ROP",
        "TOTAL_GAS",
        "NORMALIZED_TOTAL_GAS",
        "C1",
        "C2",
        "C3",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
        "PIXLER_C1_C2",
        "PIXLER_C1_C3",
        "PIXLER_C1_C4",
        "PIXLER_C1_C5",
    }.issubset(canonical)


def test_factory_templates_are_localized_without_changing_stable_ids() -> None:
    ru = factory_templates("ru")
    kk = factory_templates("kk")
    en = factory_templates("en")

    form_id = "factory-gas-ratio-pixler-depth"
    assert ru[form_id].form_id == kk[form_id].form_id == en[form_id].form_id
    assert ru[form_id].name == "Gas Ratio & Pixler — глубинная интерпретация"
    assert kk[form_id].name == "Gas Ratio & Pixler — тереңдік интерпретациясы"
    assert en[form_id].name == "Gas Ratio & Pixler — depth interpretation"
    assert ru[form_id].columns[0].title == "Глубина"
    assert kk[form_id].columns[0].title == "Тереңдік"
    assert en[form_id].columns[0].title == "Depth"


def test_legacy_form_invalid_ranges_are_repaired_to_autoscale() -> None:
    form = FormDocument.create("Legacy", FormAxisKind.DEPTH)
    binding = ParameterBinding.create("ROP", "ROP", source_mnemonic="ROP")
    track = FormTrack.create("ROP", TrackKind.CURVE, bindings=[binding])
    form.add_column(FormColumn.create("ROP", tracks=[track]))
    payload = form_to_dict(form)
    raw_binding = payload["columns"][0]["tracks"][0]["bindings"][0]
    raw_binding["x_min"] = 0.0
    raw_binding["x_max"] = 0.0

    restored = form_from_dict(payload)
    restored_binding = restored.columns[0].tracks[0].bindings[0]

    assert restored_binding.x_min is None
    assert restored_binding.x_max is None


def test_legacy_form_reversed_range_is_ordered() -> None:
    form = FormDocument.create("Legacy", FormAxisKind.DEPTH)
    binding = ParameterBinding.create("ROP", "ROP", source_mnemonic="ROP")
    track = FormTrack.create("ROP", TrackKind.CURVE, bindings=[binding])
    form.add_column(FormColumn.create("ROP", tracks=[track]))
    payload = form_to_dict(form)
    raw_binding = payload["columns"][0]["tracks"][0]["bindings"][0]
    raw_binding["x_min"] = 100.0
    raw_binding["x_max"] = 0.0

    restored = form_from_dict(payload)
    restored_binding = restored.columns[0].tracks[0].bindings[0]

    assert restored_binding.x_min == 0.0
    assert restored_binding.x_max == 100.0


def test_repository_skips_damaged_form_without_blocking_manager(tmp_path) -> None:
    repository = FormRepository(tmp_path)
    good = FormDocument.create("Good", FormAxisKind.DEPTH)
    repository.save(good)
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")

    forms = repository.list_forms()

    assert [item.name for item in forms] == ["Good"]
    assert len(repository.load_errors) == 1
    assert repository.load_errors[0][0].name == "broken.json"


def test_factory_templates_include_engineering_form_library() -> None:
    templates = factory_templates("ru")
    expected = {
        "factory-d-exponent",
        "factory-drilling-technology",
        "factory-lithology-cuttings",
        "factory-calcimetry",
        "factory-lba",
        "factory-geotech-integrated",
        "factory-engineering-control-time",
    }
    assert expected.issubset(templates)
    assert all(templates[item].read_only for item in expected)

    lithology = templates["factory-lithology-cuttings"]
    kinds = {track.kind for column in lithology.columns for track in column.tracks}
    assert {
        TrackKind.LITHOLOGY,
        TrackKind.CUTTINGS,
        TrackKind.STRATIGRAPHY,
        TrackKind.TEXT,
    }.issubset(kinds)

    geotech = templates["factory-geotech-integrated"]
    canonical = {
        binding.canonical_parameter_id
        for column in geotech.columns
        for track in column.tracks
        for binding in track.bindings
    }
    assert {"ROP", "TOTAL_GAS", "C1", "C2", "C3", "DEXP", "D_EXP_CORR"}.issubset(canonical)

    engineering_time = templates["factory-engineering-control-time"]
    assert engineering_time.axis_kind is FormAxisKind.TIME
    engineering_canonical = {
        binding.canonical_parameter_id
        for column in engineering_time.columns
        for track in column.tracks
        for binding in track.bindings
    }
    assert {"WOB", "ROP", "SPP", "TOTAL_GAS", "PIT_VOL", "MW_IN", "MW_OUT"}.issubset(
        engineering_canonical
    )


def test_engineering_form_library_is_localized_with_stable_ids() -> None:
    ru = factory_templates("ru")
    kk = factory_templates("kk")
    en = factory_templates("en")
    form_id = "factory-lithology-cuttings"
    assert ru[form_id].form_id == kk[form_id].form_id == en[form_id].form_id
    assert ru[form_id].name == "Литология и шламограмма"
    assert kk[form_id].name == "Литология және шламограмма"
    assert en[form_id].name == "Lithology and cuttings log"


def test_masterlog_screen_form_matches_reference_column_order() -> None:
    form = factory_templates()["factory-masterlog-geological-geochemical"]

    assert form.axis_kind is FormAxisKind.DEPTH
    assert form.print_header_template_id == "kazgeology_blank"
    assert [column.column_id for column in form.columns] == [
        "column-masterlog-stratigraphy",
        "column-masterlog-drilling",
        "column-depth-axis",
        "column-masterlog-cuttings",
        "column-masterlog-lba",
        "column-masterlog-calcimetry",
        "column-masterlog-lithology",
        "column-masterlog-gas",
        "column-masterlog-description",
    ]
    drilling_bindings = form.columns[1].tracks[0].bindings
    assert [item.canonical_parameter_id for item in drilling_bindings] == [
        "WOB",
        "ROP",
        "DMC",
        "DEXP",
    ]
    calc_track = form.columns[5].tracks[0]
    assert calc_track.kind is TrackKind.CALCIMETRY
    assert [item.canonical_parameter_id for item in calc_track.bindings] == [
        "CACO3",
        "CAMG_CO3_2",
    ]
    gas_bindings = form.columns[7].tracks[0].bindings
    assert [item.canonical_parameter_id for item in gas_bindings] == [
        "C1",
        "C2",
        "C3",
        "C4",
        "IC4",
        "C5",
        "IC5",
        "TG",
    ]
    assert all(item.x_scale.value == "logarithmic" for item in gas_bindings)
