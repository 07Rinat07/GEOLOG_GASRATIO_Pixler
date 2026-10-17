"""Opt-in comparison evidence flows through the real PDF and passport boundaries."""

from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from PySide6.QtGui import QPdfWriter

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing import hydrocarbon_interpretation_pdf_renderer as pdf_renderer
from geoworkbench.printing import hydrocarbon_interpretation_report as pdf_export
from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.hydrocarbon_interpretation import HydrocarbonInterpretationReport
from geoworkbench.services.interpretation_method_comparison import (
    MethodComparisonInterval,
    MethodComparisonStatus,
)
from geoworkbench.services.localization import AppLanguage


def _report() -> HydrocarbonInterpretationReport:
    return HydrocarbonInterpretationReport(
        project_name="Project",
        well_name="Well",
        dataset_id="source-dataset",
        dataset_name="Gas dataset",
        generated_at="2026-10-17T12:00:00Z",
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
        standard_overlap_fraction=1.0,
        opus_overlap_fraction=1.0,
        standard_phase=FluidPhaseContract.GAS,
        opus_phase=FluidPhaseContract.GAS,
        standard_wetness_robust_z=3.2,
        standard_pixler_c1_c2=17.0,
        opus_class_code=3,
        opus_support_fraction=0.625,
        opus_valid_rows=8,
    )


@pytest.mark.parametrize(
    ("language", "localized_status"),
    (
        (AppLanguage.RU, "Признаки согласуются"),
        (AppLanguage.KK, "Белгілер сәйкес келеді"),
        (AppLanguage.EN, "Indicators agree"),
    ),
)
def test_real_pdf_contains_only_explicit_comparison(
    qapp: object,
    tmp_path: Path,
    language: AppLanguage,
    localized_status: str,
) -> None:
    del qapp
    report = _report()
    comparison = _comparison()
    plain = pdf_export.export_hydrocarbon_interpretation_pdf(
        report, tmp_path / "plain.pdf", language=language,
    )
    enriched = pdf_export.export_hydrocarbon_interpretation_pdf(
        report, tmp_path / "enriched.pdf", language=language,
        method_comparisons=(comparison,),
    )

    def extract(path: Path) -> str:
        with fitz.open(path) as document:
            assert len(document) >= 1
            return re.sub(r"\s+", " ", " ".join(page.get_text() for page in document))

    assert plain.read_bytes().startswith(b"%PDF")
    assert enriched.read_bytes().startswith(b"%PDF")
    assert localized_status not in extract(plain)
    assert localized_status in extract(enriched)
    assert report == _report()


def test_empty_comparison_preserves_legacy_pdf_html_signature(
    monkeypatch: pytest.MonkeyPatch, qapp: object, tmp_path: Path,
) -> None:
    del qapp
    report = _report()
    calls: list[AppLanguage] = []

    def legacy_html(
        _report_value: HydrocarbonInterpretationReport,
        language: AppLanguage,
    ) -> str:
        calls.append(language)
        return "<html><body><h2>Report</h2></body></html>"

    monkeypatch.setattr(pdf_export, "hydrocarbon_interpretation_html", legacy_html)
    target = pdf_export.export_hydrocarbon_interpretation_pdf(
        report, tmp_path / "legacy-preflight.pdf", language=AppLanguage.EN,
    )
    assert target.read_bytes().startswith(b"%PDF")
    assert calls == [AppLanguage.EN]

    monkeypatch.setattr(pdf_renderer, "hydrocarbon_interpretation_html", legacy_html)
    writer = QPdfWriter(str(tmp_path / "legacy-renderer.pdf"))
    pdf_renderer.render_hydrocarbon_interpretation_report(
        writer, report, language=AppLanguage.EN,
    )
    del writer
    assert calls == [AppLanguage.EN, AppLanguage.EN]


@pytest.mark.parametrize("with_comparison", (False, True))
def test_passport_export_forwards_snapshot_only_when_selected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    with_comparison: bool,
) -> None:
    report = _report()
    dataset = Dataset(
        "source-dataset", "Gas dataset", DatasetKind.GTI, DepthDomain.MD,
        np.array([100.0, 102.0, 104.0]),
    )
    session = SimpleNamespace(current_dataset=dataset, report_compositions={})
    comparison = (_comparison(),) if with_comparison else ()
    observed: list[dict[str, object]] = []
    passport_options: list[tuple[tuple[str, str], ...]] = []

    def build_passport(_builder: object, _session: object, request: object) -> object:
        passport_options.append(request.render.options)
        return object()

    def fake_export(
        _report_value: HydrocarbonInterpretationReport,
        output: Path,
        **kwargs: object,
    ) -> Path:
        observed.append(kwargs)
        output.write_bytes(b"%PDF-1.4\n")
        return output

    def execute_transaction(
        destination: Path, produce: object, _passport: object, *, overwrite: bool,
    ) -> Path:
        assert not overwrite
        return produce(destination)

    monkeypatch.setattr(pdf_export.ReportPassportBuilder, "build", build_passport)
    monkeypatch.setattr(pdf_export, "export_hydrocarbon_interpretation_pdf", fake_export)
    monkeypatch.setattr(
        pdf_export, "execute_report_output_transaction", execute_transaction,
    )
    target = tmp_path / "passport.pdf"
    pdf_export.export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, target, language=AppLanguage.EN,
        method_comparisons=comparison,
    )

    assert len(observed) == 1
    assert observed[0].get("method_comparisons", ()) == comparison
    assert ("method_comparison_intervals", "1") in passport_options[0] if with_comparison else (
        "method_comparison_intervals", "1"
    ) not in passport_options[0]
    assert target.read_bytes().startswith(b"%PDF")
