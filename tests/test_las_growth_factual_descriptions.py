"""Explicit geology updates carry source descriptions, never invented text."""

from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.models import CuttingsSample, LithologyInterval
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import DailyLasGrowthError
from geoworkbench.services.well_geology_update import analyze_well_geology_update, prepare_well_geology_update
from test_daily_las_growth import _dataset, _add_curve
from test_las_geology import _base_metadata, _small_geology_las
from test_well_geology_update import profile, session_and_source


def _metadata():
    return _base_metadata(descriptions={
        "1": {"top": 2, "bottom": 4, "text_ru": "Известняк.",
              "text_i18n": {"ru": "Известняк.", "kk": "Әктас.", "en": "Limestone."}},
        "2": {"top": 2, "bottom": 4, "text_ru": "Слой известняка."},
    })


def _raw():
    return _small_geology_las((" GEO_DESC_ID.CODE : Description",),
                             ("0 1", "1 1", "2 1", "3 1", "4 1"),
                             metadata=_metadata())


def _review(session, target, source, raw):
    return analyze_well_geology_update(
        session, target, source, profile(), source_name="daily.las",
        source_sha256=sha256(raw).hexdigest(), source_raw_bytes=raw,
    )


def _prepare(session, target, source, raw, plan, *, append_rows=False):
    return prepare_well_geology_update(
        session, target, source, plan, source_name="daily.las",
        source_sha256=sha256(raw).hexdigest(), source_raw_bytes=raw,
        append_rows=append_rows,
    )


def test_metadata_text_is_bound_to_source_id_and_interval_preserves_manual_text():
    session, target, source = session_and_source()
    _add_curve(source, "GEO_DESC_ID", [1] * 5, unit="CODE")
    _add_curve(source, "LITH_DESC_ID", [2] * 5, unit="CODE")
    old = CuttingsSample("manual", 0, 2.5, description="Ручная запись", calcite_percent=77)
    old_layer = LithologyInterval("manual-layer", 0, 2.5, "rock", "Ручной слой")
    well = session.current_well
    well.cuttings = [old]
    well.lithology = [old_layer]
    before = deepcopy((old, old_layer))
    raw = _raw()
    plan = _review(session, target, source, raw)
    cuttings = [item for item in plan.additions if item.layer == "cuttings"]
    layers = [item for item in plan.additions if item.layer == "lithology"]
    assert [(a.top, a.bottom, a.description) for a in cuttings] == [(2.5, 4, "Известняк.")]
    assert [(a.top, a.bottom, a.description) for a in layers] == [(2.5, 4, "Слой известняка.")]
    prepared = _prepare(session, target, source, raw, plan)
    assert prepared is not None
    assert prepared.cuttings[0] is old and prepared.lithology[0] is old_layer
    assert (old, old_layer) == before
    assert prepared.cuttings[1].description_i18n == {"ru": "Известняк.", "kk": "Әктас.", "en": "Limestone."}
    assert prepared.cuttings[1].calcite_percent is None
    assert prepared.lithology[1].description == "Слой известняка."


@pytest.mark.parametrize("missing", ("no_metadata", "unknown_id", "no_id"))
def test_missing_description_never_generates_free_text(missing):
    session, target, source = session_and_source()
    raw = _raw() if missing != "no_metadata" else b"no portable metadata"
    if missing != "no_id":
        _add_curve(source, "GEO_DESC_ID", [999 if missing == "unknown_id" else 1] * 5, unit="CODE")
    plan = _review(session, target, source, raw)
    assert plan.additions
    assert all(item.description is None and not item.description_i18n for item in plan.additions)


def test_description_only_addition_does_not_guess_rock_or_fill_missing_depth():
    session, target, source = session_and_source()
    for key in list(source.curves):
        if source.curves[key].metadata.original_mnemonic != "ROP":
            del source.curves[key]
    _add_curve(source, "GEO_DESC_ID", [1, 1, 1, np.nan, 1], unit="CODE")
    raw = _raw()
    plan = _review(session, target, source, raw)
    assert [(a.top, a.bottom, a.components, a.description) for a in plan.additions] == [
        (2, 2.5, (), "Известняк."), (3.5, 4, (), "Известняк."),
    ]
    assert not plan.lithotypes
    prepared = _prepare(session, target, source, raw, plan)
    assert prepared is not None
    assert all(not item.components and item.description == "Известняк." for item in prepared.cuttings)


def test_changed_source_bytes_and_existing_text_reject_old_preview():
    session, target, source = session_and_source()
    _add_curve(source, "GEO_DESC_ID", [1] * 5, unit="CODE")
    raw = _raw()
    plan = _review(session, target, source, raw)
    with pytest.raises(DailyLasGrowthError, match="метаданные"):
        prepare_well_geology_update(
            session, target, source, plan, source_name="daily.las",
            source_sha256=sha256(raw).hexdigest(), source_raw_bytes=raw+b" ",
            append_rows=False,
        )
    session.current_well.cuttings.append(CuttingsSample("manual", 2, 4, description="New manual"))
    with pytest.raises(DailyLasGrowthError, match="изменились"):
        _prepare(session, target, source, raw, plan)


def test_controller_appends_real_las_descriptions_only_in_confirmed_geology_update(tmp_path):
    initial = tmp_path / "initial.las"
    incoming = tmp_path / "incoming.las"
    initial.write_bytes(_small_geology_las(
        (" ROP.M/H : Rate", " GEO_DESC_ID.CODE : Description"),
        ("0 1 1", "1 1 1", "2 1 1"),
        metadata=_base_metadata(descriptions={
            "1": {"top": 0, "bottom": 2, "text_ru": "Старый текст."},
        }),
    ))
    incoming.write_bytes(_small_geology_las(
        (" ROP.M/H : Rate", " GEO_DESC_ID.CODE : Description"),
        ("0 1 1", "1 1 1", "2 1 1", "3 1 2", "4 1 2"),
        metadata=_base_metadata(descriptions={
            "1": {"top": 0, "bottom": 2, "text_ru": "Не перезаписывать"},
            "2": {"top": 2, "bottom": 4, "text_ru": "Новый текст."},
        }),
    ))
    imported = import_las_with_report(initial)
    session = ProjectSession()
    well = session.add_dataset(imported.dataset, "Test", create_new_well=True,
                               source_document=imported.source_document, import_report=imported.report)
    target = imported.dataset
    old, = well.cuttings
    CuttingsController(session).update_description(old.sample_id, top_depth=old.top_depth,
        bottom_depth=old.bottom_depth, description="Уточнённый старый текст.")
    saved = deepcopy(old)
    dictionary = tmp_path / "profile.json"
    dictionary.write_text(profile().to_json(), encoding="utf-8")
    controller = DailyLasGrowthController(session)
    plan = controller.analyze_numerical(incoming, target.dataset_id, geology_profile_path=dictionary)
    geology = controller.geology_plan
    assert geology is not None
    assert [(a.top, a.bottom, a.description) for a in geology.additions] == [(2.5, 4, "Новый текст.")]
    outcome = controller.apply_numerical(plan, append_rows=True, geology_plan=geology)
    assert outcome.geology_record is not None
    assert well.cuttings[0] is old and old == saved
    assert target.depth.tolist() == [0, 1, 2, 3, 4]
    new = well.cuttings[1]
    assert new.description == "Новый текст." and not new.components
    CuttingsController(session).update_description(new.sample_id, top_depth=new.top_depth,
        bottom_depth=new.bottom_depth, description="Исправлено геологом.")
    assert new.description == "Исправлено геологом." and old == saved
    fresh = controller.analyze_numerical(incoming, target.dataset_id, geology_profile_path=dictionary)
    assert not controller.geology_plan.additions
    assert controller.apply_numerical(fresh, geology_plan=controller.geology_plan).geology_record is None
