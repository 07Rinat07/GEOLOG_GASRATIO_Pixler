"""Source-bound field confirmation for opt-in HTML report handoff.

No field-level PDF, Word, Excel or print output is enabled here.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from geoworkbench.services.interpretation_geology_field_handoff import (
    confirm_geology_field_selection,
    confirmed_geology_field_report_html,
    verified_geology_field_html_handoff,
)
from geoworkbench.services.interpretation_geology_interval_evidence import (
    correlate_gas_interval_with_well_geology,
)
from geoworkbench.services.localization import AppLanguage
from test_interpretation_geology_evidence_signed_pdf import _actual_source


def _source_with_zero_and_missing():
    session, report, _ = _actual_source()
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.dolomite_percent = None
    observed = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    return session, report, observed


@pytest.mark.parametrize(
    ("language", "heading"),
    (
        (AppLanguage.RU, "Покрытие отдельных измерений (MD)"),
        (AppLanguage.KK, "Жеке өлшемдердің қамтылуы (MD)"),
        (AppLanguage.EN, "Coverage by measured field (MD)"),
    ),
)
def test_confirmed_html_handoff_is_source_bound_and_does_not_impute(
    language: AppLanguage, heading: str,
) -> None:
    session, report, observed = _source_with_zero_and_missing()
    before = repr(session.current_well)
    source_key = ("session", id(report), report.dataset_id)
    fields = (
        ("calcimetry", "calcite_percent"),
        ("calcimetry", "dolomite_percent"),
    )
    selection = confirm_geology_field_selection(
        session, report, (observed,), fields, source_key=source_key,
    )
    assert verified_geology_field_html_handoff(
        session, report, selection, source_key=source_key,
    ) == ((observed,), fields)
    html = confirmed_geology_field_report_html(
        session, report, selection, language, source_key=source_key,
    )
    assert heading in html
    assert "62.5%" in html
    assert "1002.00" in html
    assert "1009.00" in html
    assert repr(session.current_well) == before


@pytest.mark.parametrize(
    "fields",
    (
        (),
        (("calcimetry", "unknown"),),
        (("lithology", "description"),),
        (("calcimetry", "calcite_percent"), ("calcimetry", "calcite_percent")),
        (("calcimetry", ["calcite_percent"]),),
        (("calcimetry", "calcite_percent", "extra"),),
    ),
)
def test_confirmation_rejects_empty_unknown_or_duplicate_fields(fields) -> None:
    session, report, observed = _source_with_zero_and_missing()
    with pytest.raises(ValueError, match="unique schema-owned"):
        confirm_geology_field_selection(
            session, report, (observed,), fields, source_key=("source",),
        )


def test_confirmation_requires_actual_evidence_and_report_source_key() -> None:
    session, report, observed = _source_with_zero_and_missing()
    fields = (("calcimetry", "calcite_percent"),)
    with pytest.raises(ValueError, match="identified report source"):
        confirm_geology_field_selection(
            session, report, (observed,), fields, source_key=(),
        )
    with pytest.raises(ValueError, match="selected measured geology evidence"):
        confirm_geology_field_selection(
            session, report, (), fields, source_key=("source",),
        )


@pytest.mark.parametrize("change", ("geology", "report", "source_key", "candidate"))
def test_handoff_refuses_stale_source_before_render(change: str) -> None:
    session, report, observed = _source_with_zero_and_missing()
    source_key = ("source", id(report))
    selection = confirm_geology_field_selection(
        session, report, (observed,),
        (("calcimetry", "calcite_percent"),),
        source_key=source_key,
    )
    if change == "geology":
        session.current_well.cuttings[0].description = "Edited after confirmation"
    elif change == "report":
        report = replace(report)
    elif change == "source_key":
        source_key = ("new source", id(report))
    else:
        report = replace(report, candidates=())
    with pytest.raises(ValueError):
        confirmed_geology_field_report_html(
            session, report, selection, AppLanguage.EN, source_key=source_key,
        )
