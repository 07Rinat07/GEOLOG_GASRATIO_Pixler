"""One verified combined MD snapshot in real HTML, DOCX, XLSX and PDF.

Independent format approvals are mandatory. Physical printing and geological
field validation are not implied; system printing has separate UI acceptance.
"""
from dataclasses import replace
import json
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import fitz
import numpy as np
from openpyxl import load_workbook
import pytest

from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
    export_polished_hydrocarbon_interpretation_docx,
)
from geoworkbench.domain.models import CurveData, CurveMetadata
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError, export_hydrocarbon_interpretation_pdf_with_passport,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    default_interpretation_report_identity,
)
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.interpretation_geology_interval_evidence_html import (
    geology_interval_evidence_table,
)
from geoworkbench.services.interpretation_gis_evidence_handoff import (
    confirm_gis_geology_selection, confirmed_gis_geology_evidence_html,
)
from geoworkbench.services.interpretation_gis_interval_evidence import (
    review_gas_geology_gis_interval,
)
from geoworkbench.services.interpretation_gis_interval_evidence_html import (
    gis_interval_evidence_table,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import passport_sidecar_path
from test_interpretation_geology_evidence_operator_ui import _candidate
from test_interpretation_gis_interval_evidence import _combined


_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _source(monkeypatch, tmp_path):
    session, receiver, original, dataset, key = _combined(monkeypatch, tmp_path)
    # A real gas curve plus the exact-source imported GIS curve. Missing
    # samples remain missing; the measured zero remains a finite observation.
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", "Methane", dataset.dataset_id, "source:las"),
        np.array([1.0, 2.0, 3.0]),
    )
    dataset.curves[key].values[1] = np.nan
    report = replace(
        build_hydrocarbon_interpretation_report(session),
        candidates=(_candidate(100.0, 102.0),),
    )
    snapshot = GisIntervalSnapshot(dataset, (key,), lambda: False)
    evidence = review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
    )
    source_key = ("cross-format", dataset.dataset_id)
    return session, receiver, original, dataset, key, report, snapshot, evidence, source_key


def _docx_tables(path):
    with ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    return tuple(
        tuple(
            tuple("".join(t.text or "" for t in cell.iter(_WORD + "t"))
                  for cell in row.findall(_WORD + "tc"))
            for row in table.findall(_WORD + "tr")
        )
        for table in root.findall(".//" + _WORD + "tbl")
    )


def _compact(text):
    return re.sub(r"\s+", "", text)


def _check_snapshot(monkeypatch, tmp_path, language):
    session, receiver, original, dataset, key, report, snapshot, evidence, source_key = _source(
        monkeypatch, tmp_path,
    )
    axis_before = dataset.active_index.values.copy()
    curves_before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    original_before = original.curves["gr"].values.copy()
    dirty = session.dirty
    report_before = replace(report)
    projection = gis_interval_evidence_table(evidence, language)
    geology = geology_interval_evidence_table(evidence.geology, language)
    row, = projection.rows
    assert row[5:10] == ("3", "2", "1", "100.0–102.0", "0.0–2.0")
    assert evidence.geology.coverage("calcimetry") == 0.5
    approvals = {
        target: confirm_gis_geology_selection(
            session, report, replace(report), evidence, snapshot,
            source_key=source_key, target=target,
        )
        for target in ("html", "word", "excel", "pdf")
    }
    assert all(approval.evidence == evidence for approval in approvals.values())
    identity = default_interpretation_report_identity(report, language, interval="100–102 m")
    html = confirmed_gis_geology_evidence_html(
        session, report, replace(report), approvals["html"], language, source_key=source_key,
    )
    section = html[html.index("<section class='gas-gis-evidence'"):]
    root = ET.fromstring(section)
    assert root.attrib["data-axis"] == "MD"
    assert root.attrib["data-dataset-id"] == dataset.dataset_id
    assert root.attrib["data-axis-id"] == dataset.active_index_id
    assert tuple(cell.text or "" for cell in root.findall("./table/thead/tr/th")) == projection.headings
    assert tuple(tuple(cell.text or "" for cell in tr.findall("td"))
                 for tr in root.findall("./table/tbody/tr")) == projection.rows

    common = dict(gis_source_key=source_key, current_gis_report=lambda: replace(report))
    word = export_polished_hydrocarbon_interpretation_docx(
        report, tmp_path / "review.docx", dataset=dataset, session=session,
        language=language, identity=identity, gis_selection=approvals["word"], **common,
    )
    expected_table = tuple(zip(projection.headings, row, strict=True))
    assert _docx_tables(word).count(expected_table) == 1

    xlsx = readable.export_readable_hydrocarbon_interpretation_xlsx(
        report, dataset, tmp_path / "review.xlsx", session=session,
        language=language, identity=identity, gis_selection=approvals["excel"], **common,
    )
    book = load_workbook(xlsx)
    try:
        sheet = book[readable._GIS_EVIDENCE_SHEET_NAMES[language]]
        assert sheet["A1"].value == projection.title
        assert sheet["A2"].value == projection.notice
        assert tuple(cell.value for cell in sheet[3]) == projection.headings
        assert tuple(tuple(cell.value for cell in tr) for tr in sheet.iter_rows(min_row=4)) == projection.rows
        geological = book[readable._GEOLOGY_EVIDENCE_SHEET_NAMES[language]]
        values = {cell.value for tr in geological for cell in tr}
        assert all(cell in values for tr in geology.coverage_rows for cell in tr)
    finally:
        book.close()

    signed = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "review.pdf",
        language=language, identity=identity, gis_selection=approvals["pdf"], **common,
    )
    with fitz.open(signed.primary_path) as document:
        pdf_text = _compact(" ".join(page.get_text() for page in document))
    assert _compact(projection.title) in pdf_text
    assert _compact(projection.notice) in pdf_text
    for heading, cell in expected_table:
        assert _compact(heading) in pdf_text, heading
        assert _compact(cell) in pdf_text, cell
    assert "sample-1" in pdf_text and "lith-1" in pdf_text
    sidecar = json.loads(passport_sidecar_path(signed.primary_path).read_text(encoding="utf-8"))
    assert dict(sidecar["render"]["options"])["confirmed_gis_curves"] == "1"
    assert dataset.curves[key].metadata.curve_id in {channel["curve_id"] for channel in sidecar["channels"]}

    assert receiver.curves == {} and session.current_dataset is dataset and session.dirty == dirty
    np.testing.assert_array_equal(dataset.active_index.values, axis_before)
    np.testing.assert_array_equal(original.curves["gr"].values, original_before)
    for name, before in curves_before.items():
        np.testing.assert_array_equal(dataset.curves[name].values, before)
    assert report == report_before


def test_combined_snapshot_all_formats_ru(qapp, monkeypatch, tmp_path):
    _check_snapshot(monkeypatch, tmp_path, AppLanguage.RU)


def test_combined_snapshot_all_formats_kk(qapp, monkeypatch, tmp_path):
    _check_snapshot(monkeypatch, tmp_path, AppLanguage.KK)


def test_combined_snapshot_all_formats_en(qapp, monkeypatch, tmp_path):
    _check_snapshot(monkeypatch, tmp_path, AppLanguage.EN)


def test_pdf_rejects_other_format_approval_without_replacing_document(qapp, monkeypatch, tmp_path):
    session, _, _, _, _, report, snapshot, evidence, source_key = _source(monkeypatch, tmp_path)
    approval = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot, source_key=source_key, target="print",
    )
    path = tmp_path / "previous.pdf"
    path.write_bytes(b"previous approved document")
    sidecar = passport_sidecar_path(path)
    sidecar.write_bytes(b"previous passport")
    with pytest.raises(HydrocarbonInterpretationPdfError, match="different output target"):
        export_hydrocarbon_interpretation_pdf_with_passport(
            session, report, path, overwrite=True, gis_selection=approval,
            gis_source_key=source_key, current_gis_report=lambda: replace(report),
        )
    assert path.read_bytes() == b"previous approved document"
    assert sidecar.read_bytes() == b"previous passport"
