from __future__ import annotations

import inspect
from types import SimpleNamespace
import zipfile

import numpy as np
import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
    export_hydrocarbon_interpretation_docx,
)
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
    export_polished_hydrocarbon_interpretation_docx,
)
from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
    _haworth_pixler_text,
    _manual_row,
    export_readable_hydrocarbon_interpretation_xlsx,
)
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.interval_gas_statistics import CandidateIntervalGasStatistics
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_drilling
from geoworkbench.ui import interpretation_report_workspace_final
from geoworkbench.ui import interpretation_report_workspace_legacy


def _minimal_report() -> HydrocarbonInterpretationReport:
    return HydrocarbonInterpretationReport(
        report_profile="standard",
        project_name="Project",
        well_name="Well",
        dataset_name="Dataset",
        dataset_id="dataset-i18n",
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


def _document_xml(path) -> str:
    with zipfile.ZipFile(path) as package:
        return package.read("word/document.xml").decode("utf-8")


def test_polished_docx_cover_uses_selected_english_language(tmp_path) -> None:
    target = tmp_path / "report-en.docx"

    export_polished_hydrocarbon_interpretation_docx(
        _minimal_report(),
        target,
        language=AppLanguage.EN,
    )

    xml = _document_xml(target)
    assert "Mud-gas interpretation report" in xml
    assert "Document" in xml
    assert "Prepared by" in xml
    assert "Signature / date" in xml
    assert "Charts, methods, prospective intervals" in xml
    assert "Документ" not in xml
    assert "Подготовил" not in xml
    assert "Подпись / дата" not in xml


def test_polished_docx_cover_uses_selected_kazakh_language(tmp_path) -> None:
    target = tmp_path / "report-kk.docx"

    export_polished_hydrocarbon_interpretation_docx(
        _minimal_report(),
        target,
        language=AppLanguage.KK,
    )

    xml = _document_xml(target)
    assert "Газ каротажын интерпретациялау есебі" in xml
    assert "Құжат" in xml
    assert "Дайындаған" in xml
    assert "Қолы / күні" in xml
    assert "Графиктер, әдістер" in xml
    assert "Документ" not in xml
    assert "Подготовил" not in xml


def test_docx_progress_uses_selected_language(tmp_path) -> None:
    updates: list[tuple[str, int, int]] = []

    export_hydrocarbon_interpretation_docx(
        _minimal_report(),
        tmp_path / "report-en.docx",
        language=AppLanguage.EN,
        progress=lambda stage, current, total: updates.append(
            (stage, current, total)
        ),
    )

    assert updates == [
        ("Preparing Word report", 0, 100),
        ("Calculating interval statistics", 20, 100),
        ("Saving Word file", 90, 100),
        ("Word report ready", 100, 100),
    ]


def test_missing_ratio_values_follow_selected_language() -> None:
    candidate = SimpleNamespace(
        interval_wetness=None,
        interval_balance=None,
        interval_character=None,
        pixler_assessment=None,
    )

    english = _haworth_pixler_text(candidate, AppLanguage.EN)
    kazakh = _haworth_pixler_text(candidate, AppLanguage.KK)

    assert english == "Wh=no data; Bh=no data; Ch=no data"
    assert kazakh == "Wh=дерек жоқ; Bh=дерек жоқ; Ch=дерек жоқ"
    assert "нет данных" not in english
    assert "нет данных" not in kazakh


def test_workspace_office_exports_explicitly_propagate_language() -> None:
    legacy_xlsx = inspect.getsource(
        interpretation_report_workspace_legacy.InterpretationReportWorkspace._export_xlsx
    )
    legacy_docx = inspect.getsource(
        interpretation_report_workspace_legacy.InterpretationReportWorkspace._export_docx
    )
    final_xlsx = inspect.getsource(
        interpretation_report_workspace_final.InterpretationReportWorkspace._export_xlsx
    )
    drilling_docx = inspect.getsource(
        interpretation_report_workspace_drilling.InterpretationReportWorkspace._export_docx
    )

    assert "language=self.language" in legacy_xlsx
    assert "language=self.language" in legacy_docx
    assert "language=self.language" in final_xlsx
    assert "language=self.language" in drilling_docx


def test_docx_dataset_mismatch_error_uses_selected_language(tmp_path) -> None:
    dataset = Dataset(
        dataset_id="other-dataset",
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0], dtype=np.float64),
    )

    with pytest.raises(
        HydrocarbonInterpretationExportError,
        match="The report belongs to another dataset",
    ):
        export_hydrocarbon_interpretation_docx(
            _minimal_report(),
            tmp_path / "report-en.docx",
            dataset=dataset,
            language=AppLanguage.EN,
        )


def test_docx_invalid_curve_length_error_uses_selected_language(tmp_path) -> None:
    dataset = Dataset(
        dataset_id="dataset-i18n",
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0], dtype=np.float64),
    )
    dataset.upsert_curve(
        "TG",
        np.asarray([1.0, 2.0], dtype=np.float64),
        unit="%",
    )

    with pytest.raises(
        HydrocarbonInterpretationExportError,
        match="Curves with an invalid sample count: TG",
    ):
        export_hydrocarbon_interpretation_docx(
            _minimal_report(),
            tmp_path / "report-en.docx",
            dataset=dataset,
            language=AppLanguage.EN,
        )


def test_xlsx_dataset_mismatch_error_uses_selected_language(tmp_path) -> None:
    dataset = Dataset(
        dataset_id="other-dataset",
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0], dtype=np.float64),
    )

    with pytest.raises(
        HydrocarbonInterpretationExportError,
        match="The dataset does not match the generated interpretation report",
    ):
        export_readable_hydrocarbon_interpretation_xlsx(
            _minimal_report(),
            dataset,
            tmp_path / "report-en.xlsx",
            language=AppLanguage.EN,
        )


def test_xlsx_manual_interval_identifier_uses_selected_language() -> None:
    item = SimpleNamespace(
        top_depth=1000.0,
        bottom_depth=1001.0,
        interpretation_name="Confirmed interval",
        label="",
        interval_type="confirmed",
        comment="",
    )
    statistics = CandidateIntervalGasStatistics(
        primary=None,
        raw_total=None,
        components=(),
        dexp=None,
    )

    row = _manual_row(1, _minimal_report(), item, statistics, AppLanguage.EN)

    assert row[0] == "G-1"
    assert row[0] != "Г-1"


def test_report_identity_uses_language_scoped_persisted_header() -> None:
    source = inspect.getsource(
        interpretation_report_workspace_final.InterpretationReportWorkspace._select_report_identity
    )

    assert "report_header_fields(" in source
    assert "self.language.value" in source
    assert "identity_with_report_header_fields(" in source
    assert "_report_identity_key" not in source
    assert "_report_identity" not in source
