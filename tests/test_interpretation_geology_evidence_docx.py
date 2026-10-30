"""Explicit source-bound geology in Word; no implicit well lookup."""
from dataclasses import replace
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
    export_hydrocarbon_interpretation_docx,
)
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import export_polished_hydrocarbon_interpretation_docx
from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.services.interpretation_geology_interval_evidence import (
    correlate_gas_interval_with_well_geology,
)
from geoworkbench.services.interpretation_geology_field_handoff import (
    confirm_geology_field_selection,
)
from geoworkbench.services.localization import AppLanguage
from test_interpretation_geology_evidence_signed_pdf import _actual_source


@pytest.mark.parametrize("exporter", (export_hydrocarbon_interpretation_docx, export_polished_hydrocarbon_interpretation_docx))
@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_word_contains_exact_shared_projection_only_when_selected(tmp_path, language, exporter):
    _, report, evidence = _actual_source()
    plain = exporter(report, tmp_path / "plain.docx", language=language)
    selected = exporter(
        report, tmp_path / "selected.docx", language=language, geology_evidence=(evidence,),
    )
    def text(path):
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        return " ".join(root.itertext())
    projection = geology_interval_evidence_table(evidence, language)
    assert projection.title not in text(plain)
    result = text(selected)
    assert projection.title in result
    assert projection.intro in result
    for row in (*projection.coverage_rows, *projection.rows):
        for cell in row:
            assert cell in result


@pytest.mark.parametrize("change", ("dataset", "axis", "candidate", "duplicate"))
def test_foreign_evidence_preserves_existing_destination(tmp_path, change):
    _, report, evidence = _actual_source()
    selected = (evidence,)
    if change == "dataset":
        selected = (replace(evidence, dataset_id="foreign"),)
    elif change == "axis":
        selected = (replace(evidence, depth_axis_id="foreign"),)
    elif change == "candidate":
        selected = (replace(evidence, gas_top=1003.0),)
    else:
        selected = (evidence, evidence)
    target = tmp_path / "preserved.docx"
    target.write_bytes(b"existing document")
    with pytest.raises(ValueError):
        export_hydrocarbon_interpretation_docx(report, target, overwrite=True, geology_evidence=selected)
    assert target.read_bytes() == b"existing document"



def _docx_text(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    return " ".join(root.itertext())


def _approved_fields(session, report, *fields):
    observed = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    source_key = ("word-field-source", report.dataset_id, report.depth_axis_id)
    selected = confirm_geology_field_selection(
        session, report, (observed,), fields, source_key=source_key,
    )
    return selected, source_key


@pytest.mark.parametrize(
    "exporter",
    (export_hydrocarbon_interpretation_docx, export_polished_hydrocarbon_interpretation_docx),
)
@pytest.mark.parametrize(
    ("language", "field_heading"),
    (
        (AppLanguage.RU, "Покрытие отдельных измерений (MD)"),
        (AppLanguage.KK, "Жеке өлшемдердің қамтылуы (MD)"),
        (AppLanguage.EN, "Coverage by measured field (MD)"),
    ),
)
def test_confirmed_measured_fields_reach_both_word_exporters(
    tmp_path, language, field_heading, exporter,
):
    session, report, _ = _actual_source()
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.dolomite_percent = None
    approved, source_key = _approved_fields(
        session, report,
        ("calcimetry", "calcite_percent"),
        ("calcimetry", "dolomite_percent"),
    )
    before = repr(session.current_well)
    plain = exporter(report, tmp_path / "plain.docx", language=language)
    selected = exporter(
        report, tmp_path / "selected.docx", language=language,
        session=session, geology_field_selection=approved,
        geology_source_key=source_key,
    )
    text = _docx_text(selected)
    assert field_heading in text
    assert ("Calcite" if language == AppLanguage.EN else "Кальцит") in text
    assert "62.5%" in text
    assert "1002.00" in text and "1010.00" in text
    assert field_heading not in _docx_text(plain)
    assert repr(session.current_well) == before


@pytest.mark.parametrize(
    "exporter",
    (export_hydrocarbon_interpretation_docx, export_polished_hydrocarbon_interpretation_docx),
)
@pytest.mark.parametrize(
    "change",
    ("missing_session", "missing_key", "wrong_key", "edited_source", "different_report",
     "bad_attribute", "unconfirmed_key", "conflicting_observation"),
)
def test_word_field_approval_refuses_stale_source_preserving_existing_file(
    tmp_path, exporter, change,
):
    session, report, observed = _actual_source()
    approved, source_key = _approved_fields(
        session, report, ("calcimetry", "calcite_percent"),
    )
    kwargs = {
        "session": session,
        "geology_field_selection": approved,
        "geology_source_key": source_key,
    }
    if change == "missing_session":
        kwargs.pop("session")
    elif change == "missing_key":
        kwargs.pop("geology_source_key")
    elif change == "wrong_key":
        kwargs["geology_source_key"] = ("different-source",)
    elif change == "edited_source":
        session.current_well.cuttings[0].description = "edited after confirmation"
    elif change == "different_report":
        report = replace(report)
    elif change == "bad_attribute":
        kwargs["geology_field_selection"] = replace(
            approved, fields=(("calcimetry", "wrong_field"),),
        )
    elif change == "unconfirmed_key":
        kwargs = {"geology_source_key": source_key}
    elif change == "conflicting_observation":
        kwargs["geology_evidence"] = (replace(observed, well_id="elsewhere"),)
    target = tmp_path / "approved.docx"
    target.write_bytes(b"previous operator-approved Word document")
    with pytest.raises(ValueError):
        exporter(report, target, overwrite=True, **kwargs)
    assert target.read_bytes() == b"previous operator-approved Word document"


def test_word_source_change_inside_progress_callback_cannot_replace_file(tmp_path):
    session, report, _ = _actual_source()
    approved, source_key = _approved_fields(
        session, report, ("calcimetry", "calcite_percent"),
    )
    target = tmp_path / "previous.docx"
    target.write_bytes(b"approved original")

    def progress(_message, step, _total):
        if step == 90:
            session.current_well.cuttings[0].description = "mutated during export"

    with pytest.raises(HydrocarbonInterpretationExportError):
        export_hydrocarbon_interpretation_docx(
            report, target, overwrite=True, session=session,
            geology_field_selection=approved, geology_source_key=source_key,
            progress=progress,
        )
    assert target.read_bytes() == b"approved original"
