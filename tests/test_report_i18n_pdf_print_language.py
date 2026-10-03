from __future__ import annotations

from dataclasses import replace
import inspect

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError,
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    default_interpretation_report_identity,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_final


def _minimal_report() -> HydrocarbonInterpretationReport:
    return HydrocarbonInterpretationReport(
        report_profile="standard",
        project_name="Project",
        well_name="Well",
        dataset_name="Dataset",
        dataset_id="dataset-i18n-pdf",
        generated_at="2026-10-03T00:00:00Z",
        primary_mnemonic="TG",
        threshold=3.0,
        baseline_median=None,
        robust_scale=None,
        methods=(),
        opus_gasomer=None,
        candidates=(),
        depth_unit="m",
        manual_intervals=(),
        warnings=(),
    )


def test_pdf_invalid_interval_error_uses_selected_english_language(tmp_path) -> None:
    report = _minimal_report()
    dataset = Dataset(
        dataset_id=report.dataset_id,
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1001.0], dtype=np.float64),
    )
    identity = replace(
        default_interpretation_report_identity(report, AppLanguage.EN),
        interval="broken",
    )

    with pytest.raises(
        HydrocarbonInterpretationPdfError,
        match="Invalid report interval: The interval must use the form",
    ) as captured:
        export_hydrocarbon_interpretation_pdf(
            report,
            tmp_path / "report-en.pdf",
            dataset=dataset,
            identity=identity,
            language=AppLanguage.EN,
        )

    assert "Некорректный" not in str(captured.value)
    assert "Интервал должен" not in str(captured.value)


def test_workspace_print_explicitly_propagates_language() -> None:
    source = inspect.getsource(
        interpretation_report_workspace_final.InterpretationReportWorkspace._print_report
    )

    assert "language=self.language" in source
