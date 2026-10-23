"""Regression contract for non-authoritative archival lithology revision proposals."""

from dataclasses import FrozenInstanceError, replace

import pytest

from geoworkbench.services.lithology_review_reader import load_lithology_review
from geoworkbench.services.lithology_revision_proposal import (
    MAX_PROPOSAL_ID_LENGTH,
    MAX_PROPOSAL_TEXT_LENGTH,
    prepare_lithology_revision_proposal,
)
from test_lithology_review_history import _history_files


def _two_records(tmp_path):
    session, first_path, second_path = _history_files(tmp_path)
    return session, load_lithology_review(first_path), load_lithology_review(second_path)


def _prepare(first, second, **overrides):
    options = {
        "proposal_id": "proposal-1",
        "proposed_by": "Иванов И.",
        "justification": "Оператор предлагает проверить классификацию.",
    }
    options.update(overrides)
    return prepare_lithology_revision_proposal(first, second, **options)


def test_proposal_is_immutable_and_never_activates_archived_mapping(tmp_path):
    session, first, second = _two_records(tmp_path)
    session.dirty = False
    before = repr(session.project)

    proposal = _prepare(first, second)

    assert proposal.review_state == "proposal_not_geological_approval"
    assert proposal.comparison.first is first
    assert proposal.comparison.second is second
    assert [difference.field_name for difference in proposal.comparison.differences] == [
        "mapping_id"
    ]
    assert proposal.proposed_by == "Иванов И."
    with pytest.raises(FrozenInstanceError):
        proposal.justification = "Approved"
    with pytest.raises(AttributeError):
        proposal.review_state = "approved"
    assert not session.dirty and repr(session.project) == before


def test_archival_timestamp_is_not_assumed_to_be_revision_order(tmp_path):
    _session, first, second = _two_records(tmp_path)

    reversed_proposal = _prepare(second, first)

    assert reversed_proposal.comparison.first.mapping_id == "review-2"
    assert reversed_proposal.comparison.second.mapping_id == "review-1"
    assert reversed_proposal.review_state == "proposal_not_geological_approval"


def test_recording_time_only_does_not_constitute_a_revision(tmp_path):
    _session, first, _second = _two_records(tmp_path)
    later = replace(first, recorded_at_utc="2026-10-22T23:00:00Z")

    with pytest.raises(ValueError, match="changed archival assertion"):
        _prepare(first, later)


def test_explicit_source_fingerprint_change_can_only_be_proposed(tmp_path):
    _session, first, _second = _two_records(tmp_path)
    candidate = replace(first, source=replace(first.source, source_sha256="a" * 64))

    proposal = _prepare(first, candidate)

    assert [difference.field_name for difference in proposal.comparison.differences] == [
        "source_sha256"
    ]
    assert proposal.review_state == "proposal_not_geological_approval"


@pytest.mark.parametrize("field", [
    "project_id", "well_id", "dataset_id", "depth_axis_id", "interval_id",
])
def test_mixed_project_well_dataset_axis_or_interval_is_rejected(tmp_path, field):
    _session, first, _second = _two_records(tmp_path)
    if field == "project_id":
        candidate = replace(first, project_id="other")
    else:
        candidate = replace(first, source=replace(first.source, **{field: "other"}))

    with pytest.raises(ValueError, match="one project"):
        _prepare(first, candidate)


@pytest.mark.parametrize("field,invalid", [
    ("proposal_id", ""), ("proposal_id", "   "), ("proposal_id", "x" * (MAX_PROPOSAL_ID_LENGTH + 1)),
    ("proposal_id", 123),
    ("proposed_by", ""), ("proposed_by", " \t "), ("proposed_by", False),
    ("proposed_by", "x" * (MAX_PROPOSAL_ID_LENGTH + 1)),
    ("justification", ""), ("justification", "\n"),
    ("justification", "x" * (MAX_PROPOSAL_TEXT_LENGTH + 1)),
    ("justification", None),
])
def test_proposal_requires_bounded_explicit_identity_and_justification(tmp_path, field, invalid):
    _session, first, second = _two_records(tmp_path)

    with pytest.raises(ValueError, match=field):
        _prepare(first, second, **{field: invalid})


def test_proposal_requires_two_archival_review_objects(tmp_path):
    _session, first, second = _two_records(tmp_path)
    with pytest.raises(TypeError, match="Two archival"):
        _prepare(first, object())
    with pytest.raises(TypeError, match="Two archival"):
        _prepare(object(), second)


def test_untrusted_text_is_preserved_as_data_without_interpretation(tmp_path):
    _session, first, second = _two_records(tmp_path)
    proposal = _prepare(
        first, second, proposed_by="<b>Unknown</b>",
        justification="<script>untrusted</script>",
    )
    assert proposal.proposed_by == "<b>Unknown</b>"
    assert proposal.justification == "<script>untrusted</script>"
    assert proposal.review_state == "proposal_not_geological_approval"
