"""Explicit combined evidence approval rejects stale numeric and geological data."""

from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.gis_interval_sample_review import review_gis_source_interval_batch
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from geoworkbench.services.interpretation_geology_interval_evidence import (
    correlate_gas_interval_with_well_geology,
)
from geoworkbench.services.interpretation_gis_evidence_handoff import (
    GisEvidenceTarget, confirm_gis_geology_selection, confirmed_gis_geology_evidence_html,
    verified_gis_geology_handoff,
)
from geoworkbench.services.interpretation_gis_interval_evidence import GasGeologyGisIntervalEvidence
from geoworkbench.services.localization import AppLanguage
from test_interpretation_geology_evidence_operator_ui import _candidate
from test_interpretation_gis_interval_evidence import _combined
from test_report_geology_snapshot import _report


def _reviewed(monkeypatch, tmp_path):
    session, receiver, _, dataset, key = _combined(monkeypatch, tmp_path)
    report = replace(
        _report(), dataset_id=dataset.dataset_id, depth_axis_id=dataset.active_index_id,
        candidates=(_candidate(100.0, 102.0),),
    )
    snapshot = GisIntervalSnapshot(dataset, (key,), lambda: False)
    geology = correlate_gas_interval_with_well_geology(
        session, top_depth=100.0, bottom_depth=102.0,
    )
    gis = review_gis_source_interval_batch(
        snapshot.dataset, curve_keys=(key,), top_md_m=100.0, bottom_md_m=102.0,
    )
    return session, receiver, dataset, key, report, snapshot, GasGeologyGisIntervalEvidence(geology, gis)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_confirmed_html_fragment_preserves_original_observations(monkeypatch, tmp_path, language):
    session, receiver, dataset, key, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    before = dataset.curves[key].values.copy()
    dirty = session.dirty
    source_key = ("source", report.dataset_id)
    selection = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot, source_key=source_key,
    )
    assert verified_gis_geology_handoff(
        session, report, replace(report), selection, source_key=source_key,
    ) == evidence
    html = confirmed_gis_geology_evidence_html(
        session, report, replace(report), selection, language, source_key=source_key,
    )
    assert "gas-geology-evidence" in html and "gas-gis-evidence" in html
    assert "sample-1" in html and "0.0–2.0" in html and "50.0%" in html
    assert receiver.curves == {} and session.dirty == dirty
    np.testing.assert_array_equal(dataset.curves[key].values, before)


@pytest.mark.parametrize("change", ("gis", "axis", "geology", "report", "candidate", "source_key"))
def test_confirmed_handoff_rejects_stale_sources(monkeypatch, tmp_path, change):
    session, _, dataset, key, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    source_key = ("source",)
    selection = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot, source_key=source_key,
    )
    current = replace(report)
    if change == "gis":
        # Same counts, minimum, maximum and MD endpoints, different raw value.
        dataset.curves[key].values[1] = 1.5
        current_summary = review_gis_source_interval_batch(
            dataset, curve_keys=(key,), top_md_m=100.0, bottom_md_m=102.0,
        )
        assert current_summary == evidence.gis
    elif change == "axis":
        dataset.active_index.values[1] = 101.5
    elif change == "geology":
        session.current_well.cuttings[0].calcite_percent = 25.0
    elif change == "report":
        report = replace(report)
    elif change == "candidate":
        current = replace(report, candidates=(replace(report.candidates[0], max_primary_value=999.0),))
    else:
        source_key = ("other",)
    with pytest.raises(ValueError):
        verified_gis_geology_handoff(session, report, current, selection, source_key=source_key)


def test_confirmation_rejects_forged_summary_and_empty_selection(monkeypatch, tmp_path):
    session, _, _, _, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    item, = evidence.gis
    assert item.review is not None
    forged = replace(item, review=replace(item.review, finite_value_bounds=(0.0, 999.0)))
    for bad in (replace(evidence, gis=(forged,)), replace(evidence, gis=())):
        with pytest.raises(ValueError):
            confirm_gis_geology_selection(
                session, report, replace(report), bad, snapshot, source_key=("source",),
            )


def test_confirmation_rejects_source_edit_between_preview_and_approval(monkeypatch, tmp_path):
    session, _, dataset, key, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    dataset.curves[key].values[1] = 1.5
    with pytest.raises(ValueError, match="changed source arrays"):
        confirm_gis_geology_selection(
            session, report, replace(report), evidence, snapshot, source_key=("source",),
        )


def test_confirmation_rejects_blocked_and_all_missing_sources(monkeypatch, tmp_path):
    session, _, dataset, key, report, _, evidence = _reviewed(monkeypatch, tmp_path)
    dataset.curves[key].values[:] = np.nan
    for keys in ((key,), ("missing-key",)):
        snapshot = GisIntervalSnapshot(dataset, keys, lambda: False)
        gis = review_gis_source_interval_batch(
            snapshot.dataset, curve_keys=keys, top_md_m=100.0, bottom_md_m=102.0,
        )
        with pytest.raises(ValueError, match="reviewed GIS sources"):
            confirm_gis_geology_selection(
                session, report, replace(report), replace(evidence, gis=gis),
                snapshot, source_key=("source",),
            )


@pytest.mark.parametrize("change", ("curve", "axis"))
def test_approval_rejects_matching_edits_to_live_and_copied_arrays(monkeypatch, tmp_path, change):
    session, _, dataset, key, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    source_key = ("source",)
    selection = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot, source_key=source_key,
    )
    if change == "curve":
        dataset.curves[key].values[1] = 1.5
        snapshot.dataset.curves[key].values[1] = 1.5
    else:
        dataset.active_index.values[1] = 101.5
        snapshot.dataset.active_index.values[1] = 101.5
    assert snapshot.matches(lambda: False)
    summary = review_gis_source_interval_batch(
        snapshot.dataset, curve_keys=(key,), top_md_m=100.0, bottom_md_m=102.0,
    )
    assert summary == evidence.gis
    with pytest.raises(ValueError, match="approved numeric fingerprint"):
        verified_gis_geology_handoff(
            session, report, replace(report), selection, source_key=source_key,
        )


_TARGETS: tuple[GisEvidenceTarget, ...] = ("html", "word", "pdf", "excel", "print")


@pytest.mark.parametrize("target", _TARGETS)
def test_confirmation_is_bound_to_one_output_target(monkeypatch, tmp_path, target):
    session, receiver, dataset, key, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    source_key = ("source",)
    before = dataset.curves[key].values.copy()
    dirty = session.dirty
    selection = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot,
        source_key=source_key, target=target,
    )
    assert selection.target == target
    for output in _TARGETS:
        if output == target:
            assert verified_gis_geology_handoff(
                session, report, replace(report), selection,
                source_key=source_key, target=output,
            ) == evidence
        else:
            with pytest.raises(ValueError, match="different output target"):
                verified_gis_geology_handoff(
                    session, report, replace(report), selection,
                    source_key=source_key, target=output,
                )
    if target != "html":
        with pytest.raises(ValueError, match="different output target"):
            confirmed_gis_geology_evidence_html(
                session, report, replace(report), selection, AppLanguage.EN,
                source_key=source_key,
            )
    assert session.dirty == dirty and receiver.curves == {}
    np.testing.assert_array_equal(dataset.curves[key].values, before)


@pytest.mark.parametrize("target", _TARGETS[1:])
@pytest.mark.parametrize("change", ("gis", "geology", "candidate"))
def test_export_target_revalidates_reviewed_sources(monkeypatch, tmp_path, target, change):
    session, _, dataset, key, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    source_key = ("source",)
    selection = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot,
        source_key=source_key, target=target,
    )
    current = replace(report)
    if change == "gis":
        dataset.curves[key].values[1] = 1.5
    elif change == "geology":
        session.current_well.cuttings[0].calcite_percent = 25.0
    else:
        current = replace(report, candidates=(replace(report.candidates[0], max_primary_value=999.0),))
    with pytest.raises(ValueError):
        verified_gis_geology_handoff(
            session, report, current, selection, source_key=source_key, target=target,
        )


def test_default_html_confirmation_cannot_authorize_exports(monkeypatch, tmp_path):
    session, _, _, _, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    selection = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot, source_key=("source",),
    )
    assert selection.target == "html"
    for target in _TARGETS[1:]:
        with pytest.raises(ValueError, match="different output target"):
            verified_gis_geology_handoff(
                session, report, replace(report), selection, source_key=("source",), target=target,
            )
    with pytest.raises(ValueError, match="Unknown GIS evidence confirmation target"):
        confirm_gis_geology_selection(
            session, report, replace(report), evidence, snapshot,
            source_key=("source",), target="docx",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="Unknown GIS evidence confirmation target"):
        verified_gis_geology_handoff(
            session, report, replace(report), selection,
            source_key=("source",), target="docx",  # type: ignore[arg-type]
        )
