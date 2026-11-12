"""Combined presentation preserves measured source values and unknowns."""

from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.interpretation_gis_interval_evidence import (
    review_gas_geology_gis_interval,
)
from geoworkbench.services.interpretation_gis_interval_evidence_html import (
    geology_gis_interval_evidence_html, gis_interval_evidence_table,
)
from geoworkbench.services.localization import AppLanguage
from test_interpretation_gis_interval_evidence import _combined
from test_report_geology_snapshot import _session


@pytest.mark.parametrize("language", list(AppLanguage))
def test_combined_view_preserves_source_and_separate_coverage(monkeypatch, tmp_path, language):
    session, _, _, dataset, key = _combined(monkeypatch, tmp_path)
    dataset.curves[key].values[1] = np.nan
    before = dataset.curves[key].values.copy()
    evidence = review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
    )
    table = gis_interval_evidence_table(evidence, language)
    row, = table.rows
    assert row[:5] == (
        key, dataset.curves[key].metadata.curve_id, dataset.dataset_id,
        "API", dataset.curves[key].metadata.provenance,
    )
    assert row[5:10] == ("3", "2", "1", "100.0–102.0", "0.0–2.0")
    html = geology_gis_interval_evidence_html(
        evidence, language, fields=(("calcimetry", "calcite_percent"),),
    )
    assert "gas-geology-evidence" in html and "gas-gis-evidence" in html
    assert table.title in html and table.notice in html
    assert "0.0–2.0" in html and "50.0%" in html
    np.testing.assert_array_equal(dataset.curves[key].values, before)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_no_selection_is_not_a_zero_measurement(language):
    evidence = review_gas_geology_gis_interval(
        _session(), top_depth=1004.0, bottom_depth=1012.0,
    )
    table = gis_interval_evidence_table(evidence, language)
    assert table.rows == ()
    assert table.empty in geology_gis_interval_evidence_html(evidence, language)


def test_blocked_no_rows_and_all_missing_have_distinct_states(monkeypatch, tmp_path):
    session, _, _, dataset, key = _combined(monkeypatch, tmp_path)
    missing_key = "<missing>&"
    evidence = review_gas_geology_gis_interval(
        session, top_depth=100.2, bottom_depth=100.8, curve_keys=(missing_key, key),
    )
    blocked, no_rows = gis_interval_evidence_table(evidence, AppLanguage.EN).rows
    assert blocked[5:10] == ("—",) * 5
    assert blocked[-1] == "Blocked: curve_not_found"
    assert no_rows[5:10] == ("0", "0", "0", "—", "—")
    assert no_rows[-1] == "No rows"
    html = geology_gis_interval_evidence_html(evidence, AppLanguage.EN)
    assert "&lt;missing&gt;&amp;" in html and missing_key not in html

    dataset.curves[key].values[:] = np.nan
    evidence = review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
    )
    row, = gis_interval_evidence_table(evidence, AppLanguage.EN).rows
    assert row[5:10] == ("3", "0", "3", "—", "—")
    assert row[-1] == "No finite values"


def test_foreign_or_inconsistent_review_is_rejected(monkeypatch, tmp_path):
    session, _, _, _, key = _combined(monkeypatch, tmp_path)
    evidence = review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
    )
    item, = evidence.gis
    assert item.review is not None
    foreign = replace(item, review=replace(item.review, top_md_m=101.0))
    with pytest.raises(ValueError, match="MD interval mismatch"):
        gis_interval_evidence_table(replace(evidence, gis=(foreign,)))
    with pytest.raises(ValueError, match="Duplicate GIS evidence key"):
        gis_interval_evidence_table(replace(evidence, gis=(item, item)))
    bad_counts = replace(item, review=replace(item.review, missing_count=100))
    with pytest.raises(ValueError, match="sample counts"):
        gis_interval_evidence_table(replace(evidence, gis=(bad_counts,)))


def test_original_source_dataset_identity_need_not_be_current_dataset(monkeypatch, tmp_path):
    session, _, _, _, key = _combined(monkeypatch, tmp_path)
    evidence = review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
    )
    item, = evidence.gis
    assert item.source is not None and item.review is not None
    # Source dataset ID is provenance, not a second axis or current dataset ID.
    source = replace(item.source, source_dataset_id="original-source-id")
    item = replace(item, source=source, review=replace(item.review, source=source))
    row, = gis_interval_evidence_table(replace(evidence, gis=(item,))).rows
    assert row[2] == "original-source-id"
