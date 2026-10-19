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
    geology_interval_evidence_table,
)
from geoworkbench.domain.models import StratigraphyInterval
from geoworkbench.services.localization import AppLanguage
from test_report_geology_snapshot import _session


@pytest.mark.parametrize(("language", "heading", "complete"), (
    (AppLanguage.RU, "Интервалы без наблюдений (MD)", "Непокрытых интервалов нет"),
    (AppLanguage.KK, "Бақылаусыз аралықтар (MD)", "Қамтылмаған аралықтар жоқ"),
    (AppLanguage.EN, "Intervals without observations (MD)", "No uncovered intervals"),
))
def test_partial_absent_and_complete_observation_coverage_has_explicit_md_gaps(language, heading, complete):
    session = _session()
    session.current_well.stratigraphy.append(StratigraphyInterval("full", 1000.0, 1015.0, "C"))
    evidence = correlate_gas_interval_with_well_geology(session, top_depth=1002.0, bottom_depth=1010.0)
    projection = geology_interval_evidence_table(evidence, language)
    assert projection.coverage_headings[2] == heading
    assert projection.coverage_rows[1][2] == "1002.00–1004.00 m; 1009.00–1010.00 m"
    assert projection.coverage_rows[3][2] == "1002.00–1010.00 m"
    assert projection.coverage_rows[4][2] == complete
    html = geology_interval_evidence_html(evidence, language)
    assert heading in html and complete in html
    assert "1002.00–1004.00 m; 1009.00–1010.00 m" in html


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
    assert "Calcite, %: 0.0" in rendered
    assert evidence.coverage("calcimetry") == pytest.approx(5 / 8)
    assert rendered.count("62.5%") >= 1


@pytest.mark.parametrize(
    ("language", "calcite", "description", "intensity", "composition"),
    (
        (AppLanguage.RU, "Кальцит, %", "Описание", "Интенсивность ЛБА", "ID литотипа sandstone, %"),
        (AppLanguage.KK, "Кальцит, %", "Сипаттама", "ЛБА қарқындылығы", "Литотип ID sandstone, %"),
        (AppLanguage.EN, "Calcite, %", "Description", "LBA intensity", "Lithotype ID sandstone, %"),
    ),
)
def test_measurement_names_and_units_follow_language_without_translating_values(
    language, calcite, description, intensity, composition,
) -> None:
    session = _session()
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.lba_intensity = 2
    sample.description = "Авторский текст <source> & saved description"
    evidence = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    before = repr(evidence)
    rendered = geology_interval_evidence_html(evidence, language)
    assert f"{calcite}: 0.0" in rendered
    assert f"{intensity}: 2" in rendered
    assert f"{composition}: 70.0" in rendered
    assert f"{description}: {escape(sample.description)}" in rendered
    assert "calcite_percent" not in rendered
    assert "lba_intensity" not in rendered
    assert "lithotype:sandstone" not in rendered
    assert repr(evidence) == before


def test_unknown_attribute_and_custom_lithotype_ids_remain_verbatim_and_escaped() -> None:
    session = _session()
    evidence = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    observation = replace(evidence.intersections[0], attributes=(
        ("vendor_<field>", "<untranslated>"), ("lithotype:<custom>", 0.0),
    ))
    rendered = geology_interval_evidence_html(replace(evidence, intersections=(observation,)), AppLanguage.EN)
    assert "vendor_&lt;field&gt;: &lt;untranslated&gt;" in rendered
    assert "Lithotype ID &lt;custom&gt;, %: 0.0" in rendered


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
