"""Word exports require independent approval of reviewed GIS and geology."""
from dataclasses import replace
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import numpy as np
import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
    export_hydrocarbon_interpretation_docx,
)
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
    export_polished_hydrocarbon_interpretation_docx,
)
from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.services.interpretation_gis_evidence_handoff import confirm_gis_geology_selection
from geoworkbench.services.interpretation_gis_interval_evidence_html import gis_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from test_interpretation_gis_evidence_handoff import _reviewed


_EXPORTERS = (export_hydrocarbon_interpretation_docx, export_polished_hydrocarbon_interpretation_docx)


def _text(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    return " ".join(root.itertext())


def _approval(monkeypatch, tmp_path, target="word"):
    session, receiver, dataset, key, report, snapshot, evidence = _reviewed(monkeypatch, tmp_path)
    source_key = ("word-source", report.dataset_id)
    approved = confirm_gis_geology_selection(
        session, report, replace(report), evidence, snapshot, source_key=source_key, target=target,
    )
    kwargs = dict(
        session=session, gis_selection=approved, gis_source_key=source_key,
        current_gis_report=lambda: replace(report),
    )
    return session, receiver, dataset, key, report, evidence, kwargs


@pytest.mark.parametrize("exporter", _EXPORTERS)
@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_word_contains_reviewed_geology_and_gis_only_with_word_approval(
    monkeypatch, tmp_path, exporter, language,
):
    session, receiver, dataset, key, report, evidence, kwargs = _approval(monkeypatch, tmp_path)
    before = dataset.curves[key].values.copy()
    dirty = session.dirty
    plain = exporter(report, tmp_path / "plain.docx", language=language)
    actual = exporter(report, tmp_path / "approved.docx", language=language, **kwargs)
    geology = geology_interval_evidence_table(evidence.geology, language)
    gis = gis_interval_evidence_table(evidence, language)
    result = _text(actual)
    assert geology.title not in _text(plain) and gis.title not in _text(plain)
    assert geology.title in result and gis.title in result and gis.notice in result
    for row in (gis.headings, *gis.rows, *geology.coverage_rows):
        for cell in row:
            assert cell in result
    assert session.dirty == dirty and receiver.curves == {}
    np.testing.assert_array_equal(dataset.curves[key].values, before)


@pytest.mark.parametrize("exporter", _EXPORTERS)
@pytest.mark.parametrize("change", ("html", "curve", "axis", "geology", "candidate", "key", "builder"))
def test_word_refuses_stale_or_wrong_target_preserving_destination(
    monkeypatch, tmp_path, exporter, change,
):
    session, _, dataset, key, report, _, kwargs = _approval(
        monkeypatch, tmp_path, target="html" if change == "html" else "word",
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
    target = tmp_path / "previous.docx"
    target.write_bytes(b"previous approved document")
    with pytest.raises(ValueError):
        exporter(report, target, overwrite=True, **kwargs)
    assert target.read_bytes() == b"previous approved document"


def test_word_rechecks_after_progress_and_preserves_destination(monkeypatch, tmp_path):
    _, _, dataset, key, report, _, kwargs = _approval(monkeypatch, tmp_path)
    target = tmp_path / "previous.docx"
    target.write_bytes(b"previous approved document")

    def progress(_message, step, _total):
        if step == 90:
            dataset.curves[key].values[1] = 1.5

    with pytest.raises(HydrocarbonInterpretationExportError):
        export_hydrocarbon_interpretation_docx(
            report, target, overwrite=True, progress=progress, **kwargs,
        )
    assert target.read_bytes() == b"previous approved document"


def test_polished_word_rechecks_after_cover_rewrite(monkeypatch, tmp_path):
    from geoworkbench.data import hydrocarbon_interpretation_export_docx_polished as polished

    _, _, dataset, key, report, _, kwargs = _approval(monkeypatch, tmp_path)
    original = polished._rewrite_cover

    def rewrite(*args, **options):
        original(*args, **options)
        dataset.curves[key].values[1] = 1.5

    monkeypatch.setattr(polished, "_rewrite_cover", rewrite)
    target = tmp_path / "previous.docx"
    target.write_bytes(b"previous approved document")
    with pytest.raises(ValueError):
        export_polished_hydrocarbon_interpretation_docx(report, target, overwrite=True, **kwargs)
    assert target.read_bytes() == b"previous approved document"
