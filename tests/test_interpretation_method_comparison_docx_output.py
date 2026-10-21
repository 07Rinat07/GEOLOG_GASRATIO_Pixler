"""Opt-in comparison evidence survives Word export without recalculation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from geoworkbench.data import hydrocarbon_interpretation_export as exporter
from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.hydrocarbon_interpretation import HydrocarbonInterpretationReport
from geoworkbench.services.interpretation_method_comparison import (
    MethodComparisonInterval,
    MethodComparisonStatus,
)
from geoworkbench.services.interpretation_method_comparison_html import (
    method_comparison_table,
)
from geoworkbench.services.localization import AppLanguage


_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _report() -> HydrocarbonInterpretationReport:
    return HydrocarbonInterpretationReport(
        project_name="Project",
        well_name="Well",
        dataset_id="dataset",
        dataset_name="Gas dataset",
        generated_at="2026-10-17T00:00:00Z",
        depth_unit="m",
        threshold=4.0,
        primary_mnemonic=None,
        baseline_median=None,
        robust_scale=None,
        methods=(),
        candidates=(),
        manual_intervals=(),
        warnings=(),
    )


def _comparison() -> MethodComparisonInterval:
    return MethodComparisonInterval(
        standard_bounds=(100.0, 104.0),
        opus_bounds=(100.0, 104.0),
        status=MethodComparisonStatus.AGREEMENT,
        reason_code="bounded_phase_agreement",
        overlap_depth=4.0,
        standard_overlap_fraction=0.8,
        opus_overlap_fraction=0.5,
        standard_phase=FluidPhaseContract.GAS,
        opus_phase=FluidPhaseContract.GAS,
        standard_wetness_robust_z=3.2,
        standard_pixler_c1_c2=17.0,
        opus_class_code=3,
        opus_support_fraction=0.625,
        opus_valid_rows=8,
    )


def _document_xml(path: Path) -> ET.Element:
    with ZipFile(path) as archive:
        return ET.fromstring(archive.read("word/document.xml"))


def _cell_text(cell: ET.Element) -> str:
    return "".join(node.text or "" for node in cell.iter(_WORD + "t"))


def _all_text(root: ET.Element) -> str:
    return " ".join(node.text or "" for node in root.iter(_WORD + "t"))


@pytest.mark.parametrize("language", list(AppLanguage))
def test_real_docx_uses_same_localized_evidence_as_html_and_xlsx(
    tmp_path: Path, language: AppLanguage,
) -> None:
    report = _report()
    comparison = _comparison()
    expected = method_comparison_table((comparison,), language, depth_unit="m")
    target = exporter.export_hydrocarbon_interpretation_docx(
        report, tmp_path / "with-comparison.docx",
        language=language, method_comparisons=(comparison,),
    )
    root = _document_xml(target)
    text = _all_text(root)

    assert expected.title in text
    assert expected.intro in text
    assert expected.rows[0].cells[2] in text
    assert expected.rows[0].cells[3] in text
    assert expected.rows[0].cells[4] in text

    tables = root.findall(".//" + _WORD + "tbl")
    matching = []
    for table in tables:
        rows = table.findall(_WORD + "tr")
        if len(rows) < 2:
            continue
        headers = tuple(_cell_text(c) for c in rows[0].findall(_WORD + "tc"))
        if headers == expected.headings:
            matching.append(rows)
    assert len(matching) == 1
    cells = matching[0][1].findall(_WORD + "tc")
    assert tuple(_cell_text(c) for c in cells) == expected.rows[0].cells
    assert report == _report()
    assert comparison == _comparison()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_default_docx_has_no_unrequested_comparison(
    tmp_path: Path, language: AppLanguage,
) -> None:
    report = _report()
    target = exporter.export_hydrocarbon_interpretation_docx(
        report, tmp_path / "plain.docx", language=language,
    )
    text = _all_text(_document_xml(target))
    projection = method_comparison_table((_comparison(),), language)
    assert projection.title not in text
    assert projection.intro not in text
    assert projection.rows[0].cells[3] not in text


def test_docx_renders_missing_measurements_and_escapes_untrusted_depth_unit(
    tmp_path: Path,
) -> None:
    report = replace(_report(), depth_unit="m & <unsafe>")
    comparison = replace(
        _comparison(),
        standard_wetness_robust_z=None,
        standard_pixler_c1_c2=None,
        opus_support_fraction=None,
    )
    target = exporter.export_hydrocarbon_interpretation_docx(
        report, tmp_path / "escaped.docx",
        language=AppLanguage.EN, method_comparisons=(comparison,),
    )
    with ZipFile(target) as archive:
        raw = archive.read("word/document.xml").decode("utf-8")
    root = ET.fromstring(raw)
    assert "m &amp; &lt;unsafe&gt;" in raw
    assert "<unsafe>" not in raw
    assert "Wetness robust-z: —" in _all_text(root)
    assert "Pixler C1/C2: —" in _all_text(root)
    assert "OPUS class support: —" in _all_text(root)


@pytest.mark.parametrize("with_comparison", (False, True))
def test_legacy_docx_writer_called_without_new_keyword_when_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, with_comparison: bool,
) -> None:
    calls: list[tuple[AppLanguage, dict[str, object]]] = []

    def legacy_writer(
        path: Path,
        report: HydrocarbonInterpretationReport,
        dataset: object,
        language: AppLanguage,
        **kwargs: object,
    ) -> None:
        del report, dataset
        calls.append((language, kwargs))
        path.write_bytes(b"legacy DOCX fixture")

    monkeypatch.setattr(exporter, "_write_docx", legacy_writer)
    snapshot = (_comparison(),) if with_comparison else ()
    target = exporter.export_hydrocarbon_interpretation_docx(
        _report(), tmp_path / "legacy.docx", language=AppLanguage.EN,
        method_comparisons=snapshot,
    )
    assert target.read_bytes() == b"legacy DOCX fixture"
    assert len(calls) == 1
    assert calls[0][0] is AppLanguage.EN
    assert calls[0][1].get("method_comparisons", ()) == snapshot
    assert ("method_comparisons" in calls[0][1]) is with_comparison
