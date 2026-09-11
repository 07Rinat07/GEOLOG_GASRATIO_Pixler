from dataclasses import asdict, replace
from copy import deepcopy
from hashlib import sha256
import json

import numpy as np
import pytest

from test_daily_las_growth import _dataset, _add_curve
from geoworkbench.domain.models import Project, Well, LithologyInterval, CuttingsSample
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import DailyLasGrowthError, dataset_append_state_sha256
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary, RockCodeEntry, dictionary_from_session
from geoworkbench.services.well_geology_update import analyze_well_geology_update, prepare_well_geology_update


def encoded(value):
    return json.dumps(value, default=lambda item: item.tolist() if isinstance(item, np.ndarray) else str(item), sort_keys=True)


def profile(name="Vendor A", rock_name="Sand"):
    return RockCodeDictionary(name, name, (
        RockCodeEntry(1, "sand", "1", rock_name, rock_name, rock_name, "rock", "#aabbcc", "sand_dots"),
        RockCodeEntry(2, "clay", "2", "Clay", "Clay", "Clay", "rock", "#ddeeff", "clay_dash"),
    ))


def session_and_source(axis=(0, 1, 2, 3, 4)):
    target = _dataset("target", list(axis), [1] * len(axis))
    source = _dataset("source", list(axis), [1] * len(axis))
    _add_curve(source, "КОД_ПОРОДЫ", [1] * len(axis))
    _add_curve(source, "ПОРОДА1_КОД", [1] * len(axis))
    _add_curve(source, "ПОРОДА1_КОЛИЧ", [100] * len(axis))
    well = Well("w", "Well", datasets={target.dataset_id: target})
    session = ProjectSession(project=Project("p", "Project", wells={well.well_id: well}), current_well_id=well.well_id, current_dataset_id=target.dataset_id)
    return session, target, source


def review(session, target, source, dictionary=None):
    return analyze_well_geology_update(session, target, source, dictionary or profile(), source_name="daily.las", source_sha256="a" * 64)


def prepare(session, target, source, plan):
    return prepare_well_geology_update(session, target, source, plan, source_name="daily.las", source_sha256="a" * 64, append_rows=False)


def commit_prepared(session, target, result):
    well = session.current_well
    well.lithology, well.cuttings = result.lithology, result.cuttings
    well.content_revision = result.revision
    session.project.lithotypes = result.catalog
    target.geology_update_history.append(result.record)


@pytest.mark.parametrize("descending", [False, True])
def test_fill_only_gaps_preserves_manual_layers_texts_and_source(descending):
    session, target, source = session_and_source((4, 3, 2, 1, 0) if descending else (0, 1, 2, 3, 4))
    well = session.current_well
    lithology = LithologyInterval("manual", 1, 3, "manual-rock", "Authored", {"ru": "Ручное", "kk": "Мәтін", "en": "Authored"})
    cuttings = CuttingsSample("sample", 0.5, 3.5, description="<b>Keep</b>", calcite_percent=25)
    well.lithology.append(lithology)
    well.cuttings.append(cuttings)
    before = deepcopy(asdict(well))
    source_digest = dataset_append_state_sha256(source)
    plan = review(session, target, source)
    assert [(c.top, c.bottom) for c in plan.additions if c.layer == "lithology"] == [(0, 1), (3, 4)]
    assert [(c.top, c.bottom) for c in plan.additions if c.layer == "cuttings"] == [(0, 0.5), (3.5, 4)]
    prepared = prepare(session, target, source, plan)
    assert encoded(asdict(well)) == encoded(before)
    commit_prepared(session, target, prepared)
    assert well.lithology[0] is lithology and well.cuttings[0] is cuttings
    assert asdict(lithology) == before["lithology"][0]
    assert asdict(cuttings) == before["cuttings"][0]
    assert dataset_append_state_sha256(source) == source_digest
    fresh = review(session, target, source)
    assert not fresh.additions
    assert prepare(session, target, source, fresh) is None


def test_vendor_code_conflicts_create_independent_lithotypes_and_unambiguous_export():
    session, target, source = session_and_source()
    first = prepare(session, target, source, review(session, target, source))
    commit_prepared(session, target, first)
    first_record = session.project.lithotypes[next(iter(session.project.lithotypes))]
    # A second well of another vendor uses source code 1 for a different rock.
    other = Well("other", "Other", datasets={target.dataset_id: target})
    session.project.wells[other.well_id] = other
    session.current_well_id = other.well_id
    plan = review(session, target, source, profile("Vendor B", "Limestone"))
    assert plan.code_remaps == ((1, "2"),)
    second = prepare(session, target, source, plan)
    commit_prepared(session, target, second)
    names = {r.name_en for r in session.project.lithotypes.values()}
    assert names == {"Sand", "Limestone"}
    assert session.project.lithotypes[first_record.lithotype_id] is first_record
    exported = dictionary_from_session(session)
    assert len({entry.source_code for entry in exported.entries}) == 2
    assert all(len(entry.lithotype_id) <= 80 for entry in exported.entries)


def test_unknown_code_and_invalid_composition_never_invent_or_normalize():
    session, target, source = session_and_source()
    source.curve_by_mnemonic("КОД_ПОРОДЫ").values[:] = 999
    source.curve_by_mnemonic("ПОРОДА1_КОЛИЧ").values[:] = 90
    plan = review(session, target, source)
    assert plan.unknown_codes == (999,)
    assert plan.invalid_composition_rows == 5
    assert not plan.additions and not plan.lithotypes
    assert not session.project.lithotypes


def test_large_depth_gap_is_not_filled():
    session, target, source = session_and_source((0, 1, 2, 100, 101, 102))
    plan = review(session, target, source)
    assert [(c.top, c.bottom) for c in plan.additions if c.layer == "lithology"] == [(0, 2), (100, 102)]


@pytest.mark.parametrize("edit", ["description", "translation", "source", "profile", "target"])
def test_stale_plan_fails_before_any_changes(edit):
    session, target, source = session_and_source()
    session.current_well.lithology.append(LithologyInterval("manual", 1, 2, "rock", "before"))
    plan = review(session, target, source)
    if edit == "description":
        session.current_well.lithology[0].description = "after"
    elif edit == "translation":
        session.current_well.lithology[0].description_i18n["en"] = "changed"
    elif edit == "source":
        source.curve_by_mnemonic("КОД_ПОРОДЫ").values[0] = 2
    elif edit == "profile":
        raw = profile("different").to_json()
        plan = replace(plan, profile_json=raw, profile_sha256=sha256(raw.encode()).hexdigest())
    else:
        target.curve_by_mnemonic("ROP").values[0] = 9
    before = deepcopy(asdict(session.current_well))
    with pytest.raises(DailyLasGrowthError):
        prepare(session, target, source, plan)
    # Use JSON-normalization for NumPy values in the nested Dataset structure.
    assert encoded(asdict(session.current_well)) == encoded(before)


@pytest.mark.parametrize("failure", ["time", "feet", "duplicate", "composition_pair"])
def test_geology_axis_and_channel_validation(failure):
    session, target, source = session_and_source()
    if failure == "time":
        from geoworkbench.domain.models import IndexRole
        source.active_index.role = IndexRole.TIME
    elif failure == "feet":
        source.active_index.unit = "ft"
    elif failure == "duplicate":
        _add_curve(source, "КОД ПОРОДЫ", [1] * 5)
    else:
        del source.curves[source.curve_by_mnemonic("ПОРОДА1_КОЛИЧ").metadata.curve_id]
        assert review(session, target, source).invalid_composition_rows == 5
        return
    with pytest.raises(DailyLasGrowthError):
        review(session, target, source)
