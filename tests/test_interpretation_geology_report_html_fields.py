"""Explicit measured-field selection for verified report HTML only.

This does not opt in signed PDF/Word/Excel or change source observations.
"""

from __future__ import annotations

import pytest

from geoworkbench.services.hydrocarbon_interpretation import (
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.interpretation_geology_interval_evidence import (
    correlate_gas_interval_with_well_geology,
)
from geoworkbench.services.localization import AppLanguage
from test_interpretation_geology_evidence_signed_pdf import _actual_source


@pytest.mark.parametrize(
    ("language", "title"),
    (
        (AppLanguage.RU, "Покрытие отдельных измерений (MD)"),
        (AppLanguage.KK, "Жеке өлшемдердің қамтылуы (MD)"),
        (AppLanguage.EN, "Coverage by measured field (MD)"),
    ),
)
def test_report_html_field_selection_is_localized_and_does_not_impute(
    language: AppLanguage, title: str,
) -> None:
    session, report, _ = _actual_source()
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.dolomite_percent = None
    before = repr(session.current_well)
    observed = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    fields = (
        ("calcimetry", "calcite_percent"),
        ("calcimetry", "dolomite_percent"),
    )
    html = hydrocarbon_interpretation_html(
        report, language, geology_evidence=(observed,), geology_fields=fields,
    )
    assert title in html
    assert "62.5%" in html
    assert "1002.00–1004.00 m" in html
    assert "1009.00–1010.00 m" in html
    assert "1002.00–1010.00 m" in html  # Missing dolomite assay
    assert repr(session.current_well) == before


def test_report_html_default_remains_unchanged_without_field_selection() -> None:
    _, report, observed = _actual_source()
    standard = hydrocarbon_interpretation_html(
        report, AppLanguage.EN, geology_evidence=(observed,),
    )
    assert standard == hydrocarbon_interpretation_html(
        report, AppLanguage.EN, geology_evidence=(observed,), geology_fields=(),
    )
    assert "Coverage by measured field (MD)" not in standard


def test_report_html_field_selection_fails_closed_without_evidence() -> None:
    _, report, _ = _actual_source()
    with pytest.raises(ValueError, match="require selected geology evidence"):
        hydrocarbon_interpretation_html(
            report, AppLanguage.EN,
            geology_fields=(("calcimetry", "calcite_percent"),),
        )


@pytest.mark.parametrize(
    "fields",
    (
        (("calcimetry", "unknown_field"),),
        (("lithology", "description"),),
        (("calcimetry", "calcite_percent"), ("calcimetry", "calcite_percent")),
    ),
)
def test_report_html_rejects_invalid_or_duplicate_field_selection(fields) -> None:
    _, report, observed = _actual_source()
    with pytest.raises(ValueError, match="Unknown or repeated measured geology field"):
        hydrocarbon_interpretation_html(
            report, AppLanguage.EN,
            geology_evidence=(observed,), geology_fields=fields,
        )
