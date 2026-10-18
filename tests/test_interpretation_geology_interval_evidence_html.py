"""Read-only geological evidence HTML: depth coverage != assay result."""

from __future__ import annotations

from dataclasses import replace
from html import escape

import pytest

from geoworkbench.services.interpretation_geology_interval_evidence import (
    correlate_gas_interval_with_well_geology,
)
from geoworkbench.services.interpretation_geology_interval_evidence_html import (
    geology_interval_evidence_html,
)
from geoworkbench.services.localization import AppLanguage
from test_report_geology_snapshot import _session


@pytest.mark.parametrize(
    ("language", "heading", "lba", "missing"),
    (
        (
            AppLanguage.RU,
            "Фактическое пересечение газового интервала",
            "ЛБА", "Нет измерений / сведений",
        ),
        (
            AppLanguage.KK,
            "Газ аралығы мен геологиялық деректердің нақты қиылысуы",
            "ЛБА", "Өлшеулер / мәліметтер жоқ",
        ),
        (
            AppLanguage.EN,
            "Measured gas interval and geological evidence intersection",
            "LBA", "No measurement / record",
        ),
    ),
)
def test_real_snapshot_is_localized_without_inferred_results(
    language, heading, lba, missing,
) -> None:
    session = _session()
    snapshot = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    rendered = geology_interval_evidence_html(snapshot, language)
    assert "<section class='gas-geology-evidence'" in rendered
    assert heading in rendered
    assert lba in rendered
    assert missing in rendered
    assert "1002.00–1010.00 m" in rendered
    assert "1004.00–1009.00 m" in rendered
    assert "sample-in" in rendered
    assert "62.5%" in rendered
    assert snapshot.coverage("calcimetry") == 0.0
    assert "calcite_percent: 0" not in rendered
    assert "97.0%" not in rendered
    assert "negative carbonate" not in rendered.casefold()


def test_measured_zero_remains_measurement_not_missing() -> None:
    session = _session()
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    evidence = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    rendered = geology_interval_evidence_html(evidence, AppLanguage.EN)
    assert "calcite_percent: 0.0" in rendered
    assert evidence.coverage("calcimetry") == pytest.approx(5 / 8)
    assert rendered.count("62.5%") >= 1


def test_untrusted_source_fields_and_provenance_are_html_escaped() -> None:
    session = _session()
    sample = session.current_well.cuttings[0]
    sample.sample_id = 'probe" onmouseover="<alert>'
    sample.description = "<script>alert(1)</script>"
    evidence = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    evidence = replace(
        evidence, dataset_id='data" data-injected="false',
        depth_axis_id='axis" onclick="alert(1)',
    )
    rendered = geology_interval_evidence_html(evidence)
    assert "<script>" not in rendered
    assert "<alert>" not in rendered
    assert "onmouseover=\"<alert>" not in rendered
    assert escape(sample.description) in rendered
    assert escape(sample.sample_id) in rendered
    assert escape(evidence.depth_axis_id, quote=True) in rendered
    assert 'data-injected="false"' not in rendered


def test_no_geology_returns_no_observation_not_false_zero() -> None:
    session = _session()
    well = session.current_well
    well.lithology.clear()
    well.cuttings.clear()
    well.stratigraphy.clear()
    evidence = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    rendered = geology_interval_evidence_html(evidence, AppLanguage.EN)
    assert 'colspan=\'5\'' in rendered
    assert rendered.count("No measurement / record") == 6
    assert "0.0%" not in rendered
    assert not evidence.intersections


def test_invalid_depth_or_coverage_refused_without_reinterpretation() -> None:
    session = _session()
    evidence = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    with pytest.raises(ValueError, match="increasing MD"):
        geology_interval_evidence_html(replace(evidence, depth_unit="ft"))
    with pytest.raises(ValueError, match="coverage entry"):
        geology_interval_evidence_html(replace(
            evidence,
            coverage_by_kind=(("lithology", 1.1),),
        ))
