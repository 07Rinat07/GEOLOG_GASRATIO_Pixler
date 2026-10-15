"""The standard signed report export must include stored page marks exactly once."""

from __future__ import annotations

import json

import fitz
import numpy as np
import pytest

from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ensure_report_composition_id,
)
from geoworkbench.printing import hydrocarbon_interpretation_report as pdf_reports
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.report_passport import passport_sidecar_path
from geoworkbench.services.report_preview_marks import PreviewMark, PreviewMarkKind
from test_report_annotations_multiwell_acceptance import _select, _two_well_session


def _mark(text: str, page: int = 1) -> PreviewMark:
    return PreviewMark(PreviewMarkKind.COMMENT, page, 0.2, 0.3, text=text)


def _render_fixture_pdf(report, target, **kwargs):
    """Minimal deterministic PDF: the real transaction still signs the final output."""
    with fitz.open() as pdf:
        for page_number in range(2):
            page = pdf.new_page()
            page.insert_text((72, 72), f"Source report page {page_number + 1}")
        pdf.save(target)
    return target


@pytest.mark.parametrize("well_id,dataset_id,text", [
    ("well-a", "dataset-a", "Аргиллит Максат"),
    ("well-b", "dataset-b", "Other well"),
])
def test_signed_standard_pdf_includes_only_current_well_preview_marks(
    qapp, tmp_path, monkeypatch, well_id, dataset_id, text,
):
    session = _two_well_session()
    for owner_id, owner_dataset, _ in (
        ("well-a", "dataset-a", 1000.0),
        ("well-b", "dataset-b", 2000.0),
    ):
        other_text = "Аргиллит Максат" if owner_id == "well-a" else "Other well"
        session.report_compositions[owner_dataset] = ensure_report_composition_id(
            InterpretationReportComposition(preview_marks=(_mark(other_text),)),
            owner_dataset,
        )
    _select(session, well_id, dataset_id)
    dataset = session.current_dataset
    assert dataset is not None
    raw_depth = dataset.depth.copy()
    raw_curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    report = build_hydrocarbon_interpretation_report(session)
    monkeypatch.setattr(pdf_reports, "export_hydrocarbon_interpretation_pdf", _render_fixture_pdf)
    destination = tmp_path / f"{dataset_id}.pdf"

    result = pdf_reports.export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, destination, include_preview_marks=True,
    )
    assert result.primary_path == destination
    with fitz.open(destination) as signed_pdf:
        assert len(signed_pdf) == 2
        assert not signed_pdf[0].get_images(full=True)
        assert signed_pdf[1].get_images(full=True)
        assert "Source report page 2" in signed_pdf[1].get_text()
    sidecar = json.loads(passport_sidecar_path(destination).read_text(encoding="utf-8"))
    assert dict(sidecar["render"]["options"])["report_preview_marks"] == "1"
    assert result.passport.artifacts
    np.testing.assert_array_equal(dataset.depth, raw_depth)
    for key, values in raw_curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


def test_preview_render_opt_out_has_no_extra_overlay_or_passport_mark_count(
    qapp, tmp_path, monkeypatch,
):
    session = _two_well_session()
    session.report_compositions["dataset-a"] = ensure_report_composition_id(
        InterpretationReportComposition(preview_marks=(_mark("Never stamp twice"),)),
        "dataset-a",
    )
    report = build_hydrocarbon_interpretation_report(session)
    monkeypatch.setattr(pdf_reports, "export_hydrocarbon_interpretation_pdf", _render_fixture_pdf)
    destination = tmp_path / "unmarked.pdf"
    pdf_reports.export_hydrocarbon_interpretation_pdf_with_passport(session, report, destination)
    with fitz.open(destination) as output:
        assert not output[0].get_images(full=True)
        assert not output[1].get_images(full=True)
    passport = json.loads(passport_sidecar_path(destination).read_text(encoding="utf-8"))
    assert "report_preview_marks" not in dict(passport["render"]["options"])


def test_invalid_page_rollback_preserves_existing_signed_report(
    qapp, tmp_path, monkeypatch,
):
    session = _two_well_session()
    session.report_compositions["dataset-a"] = ensure_report_composition_id(
        InterpretationReportComposition(preview_marks=(_mark("First"),)),
        "dataset-a",
    )
    report = build_hydrocarbon_interpretation_report(session)
    monkeypatch.setattr(pdf_reports, "export_hydrocarbon_interpretation_pdf", _render_fixture_pdf)
    destination = tmp_path / "existing.pdf"
    pdf_reports.export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, destination, include_preview_marks=True,
    )
    original_pdf = destination.read_bytes()
    sidecar_path = passport_sidecar_path(destination)
    original_passport = sidecar_path.read_bytes()

    session.report_compositions["dataset-a"] = ensure_report_composition_id(
        InterpretationReportComposition(preview_marks=(_mark("Missing page", page=99),)),
        "dataset-a",
    )
    with pytest.raises(pdf_reports.HydrocarbonInterpretationPdfError, match="missing PDF page"):
        pdf_reports.export_hydrocarbon_interpretation_pdf_with_passport(
            session, report, destination, include_preview_marks=True, overwrite=True,
        )
    assert destination.read_bytes() == original_pdf
    assert sidecar_path.read_bytes() == original_passport
