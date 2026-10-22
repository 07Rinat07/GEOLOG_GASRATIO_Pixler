from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from geoworkbench.services.gis_gti_lithology_screening import (
    ObservationQuality, RockFamily, review_gis_gti_lithology_intervals,
)
from geoworkbench.services.lithology_source_mapping import (
    create_lithology_mapping, evaluate_lithology_mapping, review_lithology_source,
)
from test_report_geology_snapshot import _session


def _mapping(session, **changes):
    args = dict(mapping_id="review-1", reviewer="Geologist",
                applicability_reference="Synthetic acceptance only",
                rock_family=RockFamily.HALITE, quality=ObservationQuality.VALIDATED)
    args.update(changes)
    return create_lithology_mapping(
        session, review_lithology_source(session, interval_id="lith-in"), **args,
    )


def test_explicit_mapping_overrides_name_without_source_mutations():
    session = _session()
    before = repr(session.project)
    mapping = _mapping(session)
    observation = evaluate_lithology_mapping(session, mapping)
    assert mapping.source.lithotype_id == "sandstone"
    assert observation.rock_family is RockFamily.HALITE
    assert observation.source_id == "lith-in"
    assert (observation.top_md_m, observation.bottom_md_m) == (1000, 1008)
    cells = review_gis_gti_lithology_intervals(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=observation.depth_axis_id,
        observations=(), lithology=(observation,),
    )
    assert cells[0].review.rock_family is RockFamily.HALITE
    assert cells[1].lithology_issues == ("no_validated_lithology",)
    assert repr(session.project) == before
    with pytest.raises(FrozenInstanceError):
        mapping.reviewer = "changed"


@pytest.mark.parametrize("field,value", [
    ("top_depth", 1001), ("bottom_depth", 1007), ("lithotype_id", "limestone"),
    ("description", "Changed"), ("description_i18n", {"kk": "Changed"}),
])
def test_source_edits_block_stale_mapping(field, value):
    session = _session()
    mapping = _mapping(session)
    setattr(session.current_well.lithology[0], field, value)
    with pytest.raises(ValueError, match="changed"):
        evaluate_lithology_mapping(session, mapping)


@pytest.mark.parametrize("change", ["axis", "delete", "duplicate", "unit", "lag"])
def test_changed_axis_or_identity_blocks_review(change):
    session = _session()
    mapping = _mapping(session)
    if change == "axis":
        session.current_dataset.active_index.values[1] += 0.5
    elif change == "delete":
        session.current_well.lithology.clear()
    elif change == "duplicate":
        session.current_well.lithology.append(session.current_well.lithology[0])
    elif change == "unit":
        session.current_dataset.active_index.unit = "ft"
    else:
        session.current_dataset.headers["LAG_PROFILE_ID"] = "unreviewed"
    with pytest.raises(ValueError):
        evaluate_lithology_mapping(session, mapping)


@pytest.mark.parametrize("depth", [
    [1000, 1005, np.nan, 1015], [1000, 1005, 1005, 1015], [1015, 1010, 1005, 1000],
])
def test_invalid_axis_refused(depth):
    session = _session()
    session.current_dataset.active_index.values = np.array(depth)
    with pytest.raises(ValueError, match="strictly increasing"):
        _mapping(session)


@pytest.mark.parametrize("field,value", [
    ("mapping_id", ""), ("reviewer", " "), ("applicability_reference", None),
    ("rock_family", "clastic"), ("quality", "validated"),
])
def test_review_requires_explicit_metadata(field, value):
    with pytest.raises((ValueError, TypeError)):
        _mapping(_session(), **{field: value})


@pytest.mark.parametrize("quality", list(ObservationQuality))
def test_quality_and_unknown_are_preserved(quality):
    session = _session()
    mapping = _mapping(session, rock_family=RockFamily.UNKNOWN_OR_MIXED, quality=quality)
    observation = evaluate_lithology_mapping(session, mapping)
    assert observation.quality is quality
    assert observation.rock_family is RockFamily.UNKNOWN_OR_MIXED


@pytest.mark.parametrize("top,bottom", [(1008, 1000), (True, 1008), (-1, 1008), (1000, 1016)])
def test_bad_source_bounds_refused(top, bottom):
    session = _session()
    interval = session.current_well.lithology[0]
    interval.top_depth, interval.bottom_depth = top, bottom
    with pytest.raises(ValueError):
        _mapping(session)


def test_modified_review_metadata_is_revalidated():
    session = _session()
    mapping = _mapping(session)
    with pytest.raises(ValueError):
        evaluate_lithology_mapping(session, replace(mapping, reviewer=""))


def test_catalog_edit_invalidates_source_review():
    from geoworkbench.domain.models import ProjectLithotype

    session = _session()
    mapping = _mapping(session)
    session.project.lithotypes["sandstone"] = ProjectLithotype(
        "sandstone", "SS", "Changed", "Changed", "rock", "#ffffff", "sandstone",
    )
    with pytest.raises(ValueError, match="changed"):
        evaluate_lithology_mapping(session, mapping)


def test_switching_dataset_does_not_reuse_review():
    session = _session()
    mapping = _mapping(session)
    session.current_dataset.dataset_id = "different-run"
    with pytest.raises(ValueError, match="changed"):
        evaluate_lithology_mapping(session, mapping)
