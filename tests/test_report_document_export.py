from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.data.report_document_export import (
    MISSING_CELL,
    REPORT_DOCUMENT_SCHEMA_VERSION,
    UNAVAILABLE_CELL,
    ReportDocumentExportError,
    build_report_document_model,
    export_report_docx,
    export_report_html,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.report_definition import (
    ReportDefinition,
    ReportIntervalContext,
    ReportIntervalMode,
    ReportIntervalSelection,
    ReportProfile,
    resolve_report_definition,
)


def _resolved_report():
    dataset = Dataset(
        "dataset-1",
        "Well A",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "ppm", "Methane", dataset.dataset_id),
        np.array([0.0, np.nan, 25.0, 30.0]),
    )
    definition = ReportDefinition(
        "selection:dataset-1",
        "Gas interval",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("c1",),
        channel_mnemonics=("C1", "H2S"),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )
    return dataset, report


def test_document_model_uses_resolved_indices_and_coverage_states() -> None:
    dataset, report = _resolved_report()

    model = build_report_document_model(dataset, report)

    assert model.schema_version == REPORT_DOCUMENT_SCHEMA_VERSION
    assert model.sample_count == 3
    assert [column.technical_name for column in model.columns] == ["DEPTH", "C1", "H2S"]
    assert model.rows[0] == ("100", "0", UNAVAILABLE_CELL)
    assert model.rows[1] == ("101", MISSING_CELL, UNAVAILABLE_CELL)
    assert model.rows[2] == ("102", "25", UNAVAILABLE_CELL)
    assert model.columns[1].coverage is not None
    assert model.columns[1].coverage.zero_count == 1
    assert model.columns[1].coverage.missing_count == 1
    assert model.columns[2].coverage is not None
    assert model.columns[2].coverage.unavailable_count == 3


def test_html_export_is_self_contained_and_explicit_about_coverage(tmp_path) -> None:
    dataset, report = _resolved_report()
    target = tmp_path / "report.html"

    export_report_html(dataset, target, report)

    text = target.read_text(encoding="utf-8")
    assert '<html lang="en">' in text
    assert "Gas interval" in text
    assert 'data-state="zero">0</td>' in text
    assert 'data-state="missing">—</td>' in text
    assert 'data-state="unavailable">#N/A</td>' in text
    assert "ReportDefinition SHA-256" in text
    assert report.definition.content_sha256 in text
    assert "http://" not in text
    assert "https://" not in text
    assert "<script" not in text


def test_docx_export_is_valid_deterministic_openxml(tmp_path) -> None:
    dataset, report = _resolved_report()
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"

    export_report_docx(dataset, first, report)
    export_report_docx(dataset, second, report)

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) >= {
            "[Content_Types].xml",
            "_rels/.rels",
            "word/document.xml",
            "word/styles.xml",
            "docProps/core.xml",
        }
        document = archive.read("word/document.xml").decode("utf-8")
        core = archive.read("docProps/core.xml").decode("utf-8")
    assert "Gas interval" in document
    assert "#N/A" in document
    assert "—" in document
    assert "0" in document
    assert report.definition.content_sha256 in document
    assert "GEOLOG GASRATIO@Pixler" in core


def test_document_export_validates_suffix_and_overwrite(tmp_path) -> None:
    dataset, report = _resolved_report()
    invalid = tmp_path / "report.pdf"
    with pytest.raises(ReportDocumentExportError, match="расширение"):
        export_report_docx(dataset, invalid, report)

    target = tmp_path / "report.html"
    export_report_html(dataset, target, report)
    with pytest.raises(FileExistsError):
        export_report_html(dataset, target, report)
    export_report_html(dataset, target, report, overwrite=True)


def test_document_export_supports_resolved_datetime_index(tmp_path) -> None:
    from geoworkbench.domain.models import DatasetIndex, IndexRole, IndexType

    dataset, _report = _resolved_report()
    dataset.add_index(
        DatasetIndex(
            "time-index",
            "DATETIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            None,
            np.array(
                [
                    "2026-07-23T10:00:00.000",
                    "2026-07-23T10:00:01.250",
                    "2026-07-23T10:00:02.500",
                    "2026-07-23T10:00:03.750",
                ],
                dtype="datetime64[ns]",
            ),
            timezone="UTC",
        ),
        make_active=True,
    )
    definition = ReportDefinition(
        "time:dataset-1",
        "Time report",
        ReportProfile.GAS,
        dataset.dataset_id,
        "time-index",
        ReportIntervalSelection(
            ReportIntervalMode.CUSTOM,
            "2026-07-23T10:00:01.250",
            "2026-07-23T10:00:02.500",
        ),
        language="en",
        curve_ids=("c1",),
    )
    report = resolve_report_definition(dataset, definition, require_curves=True)

    target = export_report_html(dataset, tmp_path / "time.html", report)
    text = target.read_text(encoding="utf-8")

    assert report.interval.sample_count == 2
    assert "2026-07-23T10:00:01.250" in text
    assert "2026-07-23T10:00:02.500" in text
    assert "2026-07-23T10:00:00.000" not in text


def test_html_export_is_deterministic_for_same_model(tmp_path) -> None:
    dataset, report = _resolved_report()
    first = tmp_path / "first.html"
    second = tmp_path / "second.html"

    export_report_html(dataset, first, report)
    export_report_html(dataset, second, report)

    assert first.read_bytes() == second.read_bytes()
