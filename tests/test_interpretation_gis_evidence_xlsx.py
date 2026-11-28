"""Actual Excel output requires its own current combined GIS approval."""
from dataclasses import replace
from math import inf, nextafter

import numpy as np
from openpyxl import load_workbook
import pytest

from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
from geoworkbench.data.hydrocarbon_interpretation_export import HydrocarbonInterpretationExportError
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.services.interpretation_gis_evidence_handoff import confirm_gis_geology_selection
from geoworkbench.services.interpretation_gis_interval_evidence import review_gas_geology_gis_interval
from geoworkbench.services.interpretation_gis_interval_evidence_html import gis_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from test_gis_interval_compare import _two_curves
from test_interpretation_geology_evidence_operator_ui import _candidate
from test_interpretation_gis_evidence_docx import _approval
from test_report_geology_snapshot import _report


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_excel_combined_evidence_is_separate_and_preserves_source(monkeypatch, tmp_path, language):
    session, receiver, dataset, key, report, evidence, kwargs = _approval(
        monkeypatch, tmp_path, target="excel",
    )
    before = dataset.curves[key].values.copy()
    axis = dataset.active_index.values.copy()
    dirty = session.dirty
    exporter = readable.export_readable_hydrocarbon_interpretation_xlsx
    plain = exporter(report, dataset, tmp_path / "plain.xlsx", language=language)
    actual = exporter(report, dataset, tmp_path / "approved.xlsx", language=language, **kwargs)
    gis = gis_interval_evidence_table(evidence, language)
    geology = geology_interval_evidence_table(evidence.geology, language)
    gis_name = readable._GIS_EVIDENCE_SHEET_NAMES[language]
    geology_name = readable._GEOLOGY_EVIDENCE_SHEET_NAMES[language]
    workbook = load_workbook(plain)
    try:
        assert gis_name not in workbook.sheetnames and geology_name not in workbook.sheetnames
    finally:
        workbook.close()
    workbook = load_workbook(actual)
    try:
        sheet = workbook[gis_name]
        assert sheet["A1"].value == gis.title and sheet["A2"].value == gis.notice
        assert tuple(cell.value for cell in sheet[3]) == gis.headings
        assert tuple(tuple(cell.value for cell in row) for row in sheet.iter_rows(min_row=4)) == gis.rows
        assert sheet.freeze_panes == "A4"
        assert all(cell.data_type != "f" for row in sheet for cell in row)
        values = {cell.value for row in workbook[geology_name] for cell in row}
        assert geology.title in values
        for row in geology.coverage_rows:
            assert all(value in values for value in row)
    finally:
        workbook.close()
    assert receiver.curves == {} and session.dirty == dirty
    np.testing.assert_array_equal(dataset.curves[key].values, before)
    np.testing.assert_array_equal(dataset.active_index.values, axis)


def test_excel_preserves_signed_gis_bounds_as_literal_text(tmp_path):
    dataset = _two_curves()
    top, bottom = -12.000000000000002, -10.000000000000002
    dataset.active_index.values[:] = [top, -11.0, bottom]
    minimum = -1.2345678901234567
    maximum = nextafter(minimum, inf)
    curve = dataset.curves["GR"]
    curve.values[:] = [minimum, np.nan, maximum]
    provenance = "-operator source note"
    curve.metadata = replace(curve.metadata, provenance=provenance)
    session = ProjectSession()
    session.add_dataset(dataset)
    report = replace(
        _report(), dataset_id=dataset.dataset_id, depth_axis_id=dataset.active_index_id,
        candidates=(_candidate(top, bottom),),
    )
    keys = ("GR",)
    snapshot = GisIntervalSnapshot(dataset, keys, lambda: False)
    evidence = review_gas_geology_gis_interval(
        session, top_depth=top, bottom_depth=bottom, curve_keys=keys,
    )
    source_key = ("signed-gis", dataset.dataset_id)
    approved = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot, source_key=source_key, target="excel",
    )

    exported = readable.export_readable_hydrocarbon_interpretation_xlsx(
        report, dataset, tmp_path / "signed.xlsx", session=session, language=AppLanguage.EN,
        gis_selection=approved, gis_source_key=source_key, current_gis_report=lambda: replace(report),
    )
    workbook = load_workbook(exported)
    try:
        sheet = workbook["Source GIS MD"]
        assert sheet["E4"].value == "'" + provenance and sheet["E4"].data_type == "s"
        assert (sheet["I4"].value, sheet["J4"].value) == (f"{top}–{bottom}", f"{minimum}–{maximum}")
        assert sheet["I4"].data_type == sheet["J4"].data_type == "s"
    finally:
        workbook.close()


@pytest.mark.parametrize("change", ("html", "word", "pdf", "print", "curve", "axis", "geology", "candidate", "key", "builder", "duplicate", "foreign_dataset"))
def test_excel_rejects_wrong_or_stale_approval_without_replacing_file(monkeypatch, tmp_path, change):
    session, _, dataset, key, report, evidence, kwargs = _approval(
        monkeypatch, tmp_path, target=change if change in {"html", "word", "pdf", "print"} else "excel",
    )
    if change == "curve":
        dataset.curves[key].values[1] = 1.5
    elif change == "axis":
        dataset.active_index.values[1] = 101.5
    elif change == "geology":
        session.current_well.cuttings[0].calcite_percent = 25.0
    elif change == "candidate":
        kwargs["current_gis_report"] = lambda: replace(
            report, candidates=(replace(report.candidates[0], max_primary_value=999.0),),
        )
    elif change == "key":
        kwargs["gis_source_key"] = ("foreign",)
    elif change == "builder":
        kwargs.pop("current_gis_report")
    elif change == "duplicate":
        kwargs["geology_evidence"] = (evidence.geology,)
    elif change == "foreign_dataset":
        dataset = replace(dataset)
    destination = tmp_path / "previous.xlsx"
    destination.write_bytes(b"previous workbook")
    with pytest.raises(ValueError):
        readable.export_readable_hydrocarbon_interpretation_xlsx(
            report, dataset, destination, overwrite=True, **kwargs,
        )
    assert destination.read_bytes() == b"previous workbook"
    assert not list(tmp_path.glob(".previous-*.xlsx"))


@pytest.mark.parametrize("phase", ("progress", "save"))
def test_excel_rechecks_approval_before_atomic_replace(monkeypatch, tmp_path, phase):
    _, _, dataset, key, report, _, kwargs = _approval(monkeypatch, tmp_path, target="excel")
    destination = tmp_path / "previous.xlsx"
    destination.write_bytes(b"previous workbook")

    def progress(_message, step, _total):
        if phase == "progress" and step == 95:
            dataset.curves[key].values[1] = 1.5

    if phase == "save":
        original = readable.Workbook.save

        def save(workbook, filename):
            original(workbook, filename)
            dataset.curves[key].values[1] = 1.5

        monkeypatch.setattr(readable.Workbook, "save", save)

    with pytest.raises((ValueError, HydrocarbonInterpretationExportError)):
        readable.export_readable_hydrocarbon_interpretation_xlsx(
            report, dataset, destination, overwrite=True, progress=progress, **kwargs,
        )
    assert destination.read_bytes() == b"previous workbook"
    assert not list(tmp_path.glob(".previous-*.xlsx"))
