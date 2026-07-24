from __future__ import annotations

import json

import pytest

from geoworkbench.forms.codec import form_from_dict, form_to_dict
from geoworkbench.forms.models import FormAxisKind, FormColumn, FormDocument, FormTrack
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.templates import curated_factory_templates, factory_templates
from geoworkbench.tablet.layout_codec import layout_from_dict, layout_to_dict
from geoworkbench.tablet.models import (
    COMPACT_MIN_TRACK_WIDTH,
    TabletLayout,
    TrackDefinition,
    TrackKind,
)


COMPACT_KINDS = {
    TrackKind.DEPTH,
    TrackKind.STRATIGRAPHY,
    TrackKind.LITHOLOGY,
    TrackKind.CUTTINGS,
    TrackKind.CALCIMETRY,
    TrackKind.LBA,
}


def test_compact_track_kinds_accept_48_px_but_curve_keeps_80_px_minimum() -> None:
    for kind in COMPACT_KINDS:
        assert TrackDefinition(kind.value, kind.value, kind, width=48).width == 48
        with pytest.raises(ValueError):
            TrackDefinition(f"{kind.value}-bad", kind.value, kind, width=47)

    with pytest.raises(ValueError):
        TrackDefinition("curve", "Curve", TrackKind.CURVE, width=79)


def test_layout_v17_migration_applies_stable_target_widths() -> None:
    restored = layout_from_dict(
        {
            "version": 17,
            "tracks": [
                {"track_id": "depth", "title": "Depth", "kind": "depth", "width": 120},
                {
                    "track_id": "lithology",
                    "title": "Lithology",
                    "kind": "lithology",
                    "width": 220,
                },
                {"track_id": "curve", "title": "Curve", "kind": "curve", "width": 300},
            ],
        }
    )

    assert restored.track_by_id("depth").width == 60
    assert restored.track_by_id("lithology").width == 110
    assert restored.track_by_id("curve").width == 300
    assert layout_to_dict(restored)["version"] == 18


def test_form_v7_migration_reduces_user_columns_to_stable_targets_once() -> None:
    payload = {
        "schema_version": 7,
        "form_id": "legacy-user-form",
        "name": "Legacy user form",
        "axis_kind": "depth",
        "origin": "user",
        "read_only": False,
        "columns": [
            {
                "column_id": "depth-column",
                "title": "Depth",
                "width": 120,
                "tracks": [
                    {"track_id": "depth-track", "title": "Depth", "kind": "depth"}
                ],
            },
            {
                "column_id": "curve-column",
                "title": "Curve",
                "width": 300,
                "tracks": [
                    {"track_id": "curve-track", "title": "Curve", "kind": "curve"}
                ],
            },
        ],
    }

    restored = form_from_dict(payload)
    encoded = form_to_dict(restored)
    restored_again = form_from_dict(encoded)

    assert restored.columns[0].width == 60
    assert restored.columns[1].width == 300
    assert encoded["schema_version"] == 8
    assert restored_again.columns[0].width == 60


def test_repository_reads_legacy_user_form_with_compact_widths(tmp_path) -> None:
    root = tmp_path / "forms" / "depth"
    root.mkdir(parents=True)
    path = root / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 6,
                "form_id": "legacy",
                "name": "Legacy",
                "axis_kind": "depth",
                "columns": [
                    {
                        "column_id": "cuttings-column",
                        "title": "Cuttings",
                        "width": 80,
                        "tracks": [
                            {
                                "track_id": "cuttings-track",
                                "title": "Cuttings",
                                "kind": "cuttings",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    form = FormRepository(tmp_path / "forms").load("legacy")

    assert form.columns[0].width == COMPACT_MIN_TRACK_WIDTH


def test_all_factory_forms_use_compact_widths_for_requested_column_kinds() -> None:
    for form in factory_templates("ru").values():
        for column in form.columns:
            kinds = {track.kind for track in column.tracks}
            if kinds and kinds.issubset(COMPACT_KINDS):
                assert column.width >= COMPACT_MIN_TRACK_WIDTH
                assert column.width < 220


def test_ready_forms_are_built_in_with_compact_geology_columns() -> None:
    forms = curated_factory_templates("ru")

    assert tuple(forms) == (
        "factory-geodata-depth-workspace",
        "factory-engineering-control-time",
    )
    assert forms["factory-geodata-depth-workspace"].name == (
        "Комплексная ГТИ-форма — геология, технология и газ"
    )
    assert forms["factory-engineering-control-time"].name == (
        "Инженерно-технологический мониторинг — временная форма"
    )

    for form in forms.values():
        assert form.read_only is True
        for column in form.columns:
            kinds = {track.kind for track in column.tracks}
            if kinds and kinds.issubset(COMPACT_KINDS):
                assert column.width >= COMPACT_MIN_TRACK_WIDTH
                assert column.width < 220


def test_form_column_minimum_follows_its_track_kind() -> None:
    compact = FormColumn.create(
        "Lithology",
        width=48,
        tracks=[FormTrack.create("Lithology", TrackKind.LITHOLOGY)],
    )
    assert compact.width == 48

    with pytest.raises(ValueError):
        FormColumn.create(
            "Curve",
            width=48,
            tracks=[FormTrack.create("Curve", TrackKind.CURVE)],
        )

    form = FormDocument.create("Compact", FormAxisKind.DEPTH)
    form.add_column(compact)
    form.validate()


def test_layout_v17_migration_compacts_every_requested_kind() -> None:
    tracks = [
        {
            "track_id": kind.value,
            "title": kind.value,
            "kind": kind.value,
            "width": 200,
        }
        for kind in sorted(COMPACT_KINDS, key=lambda item: item.value)
    ]
    tracks.append(
        {"track_id": "text", "title": "Text", "kind": "text", "width": 200}
    )

    restored = layout_from_dict({"version": 17, "tracks": tracks})

    expected = {
        kind: 100
        for kind in COMPACT_KINDS
    }
    for kind, width in expected.items():
        assert restored.track_by_id(kind.value).width == width
    assert restored.track_by_id("text").width == 200


def test_ready_form_names_are_localized_and_polished() -> None:
    expected = {
        "ru": {
            "factory-geodata-depth-workspace": "Комплексная ГТИ-форма — геология, технология и газ",
            "factory-engineering-control-time": "Инженерно-технологический мониторинг — временная форма",
        },
        "kk": {
            "factory-geodata-depth-workspace": "Кешенді ГТИ пішіні — геология, технология және газ",
            "factory-engineering-control-time": "Инженерлік-технологиялық мониторинг — уақыттық пішін",
        },
        "en": {
            "factory-geodata-depth-workspace": "Integrated mud logging form — geology, drilling and gas",
            "factory-engineering-control-time": "Engineering and drilling monitoring — time form",
        },
    }
    for language, names in expected.items():
        forms = curated_factory_templates(language)
        assert {form_id: form.name for form_id, form in forms.items()} == names
