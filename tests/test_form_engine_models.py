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
    assert len(templates) == 6
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
