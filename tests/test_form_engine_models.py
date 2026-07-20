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
    form_from_dict,
    form_to_dict,
)
from geoworkbench.tablet.models import TrackKind


def test_form_round_trip_preserves_binding() -> None:
    binding = ParameterBinding.create("TOTAL_GAS", "Total Gas", source_mnemonic="TGAS", unit="%")
    track = FormTrack.create("Газ", TrackKind.CURVE, bindings=[binding])
    column = FormColumn.create("Газ", tracks=[track])
    form = FormDocument.create("Моя форма", FormAxisKind.DEPTH)
    form.add_column(column)

    restored = form_from_dict(form_to_dict(form))

    assert restored.name == "Моя форма"
    assert restored.columns[0].tracks[0].bindings[0].canonical_parameter_id == "TOTAL_GAS"
    assert restored.columns[0].tracks[0].bindings[0].source_mnemonic == "TGAS"


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
    assert len(templates) == 10
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
    assert raw["schema_version"] == 1


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


def test_unknown_schema_is_rejected() -> None:
    with pytest.raises(FormFormatError, match="Неподдерживаемая"):
        form_from_dict({"schema_version": 99})


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
