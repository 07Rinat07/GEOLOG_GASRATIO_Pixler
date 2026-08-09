from __future__ import annotations

import re

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.hydrocarbon_interpretation_chart import (
    hydrocarbon_interpretation_chart_data_uri,
)
from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    hydrocarbon_interpretation_html_with_front_chart,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def _session_with_report_curves(
    *,
    depth_start: float = 1_300.0,
    depth_span: float = 120.0,
    samples: int = 241,
) -> ProjectSession:
    depth = np.linspace(depth_start, depth_start + depth_span, samples)
    center = depth_start + depth_span * 0.55
    width = max(1.0, depth_span * 0.06)
    dataset = Dataset(
        "dataset",
        "Geology and technology",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    series = {
        "TG_CALC": 0.02 + 0.08 * np.exp(-((depth - center) / width) ** 2),
        "WH": 5.0 + 20.0 * np.exp(-((depth - center) / (width * 1.3)) ** 2),
        "BH": 2.0 + 8.0 * np.exp(-((depth - center) / (width * 1.5)) ** 2),
        "CH": 0.5 + 2.0 * np.exp(-((depth - center) / (width * 1.2)) ** 2),
        "C1_C2": 4.0 + 2.0 * np.sin(depth / 9.0),
        "C1_C3": 12.0 + 5.0 * np.cos(depth / 11.0),
        "DEXP": 1.1 + 0.2 * np.sin(depth / 13.0),
    }
    for index, (mnemonic, values) in enumerate(series.items()):
        dataset.curves[f"curve-{index}"] = CurveData(
            CurveMetadata(
                f"curve-{index}",
                mnemonic,
                mnemonic,
                "",
                "test",
                dataset.dataset_id,
            ),
            np.asarray(values, dtype=np.float64),
        )
    session = ProjectSession()
    session.add_dataset(dataset, "Well 494")
    return session


def _pdf_page_count(payload: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", payload))


def test_whole_well_report_chart_is_embedded_before_tables(qapp) -> None:
    session = _session_with_report_curves()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)

    uri = hydrocarbon_interpretation_chart_data_uri(report, dataset, AppLanguage.RU)
    html = hydrocarbon_interpretation_html_with_front_chart(
        report,
        dataset,
        AppLanguage.RU,
    )

    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 10_000
    chart_position = html.index("Графики интерпретационных кривых по глубине")
    methods_position = html.index("Методы и доступность")
    assert chart_position < methods_position
    assert "data:image/png;base64," in html
    assert "max-width:1050px" in html
    assert "margin:0 auto" in html
    assert 'width="1050"' not in html


def test_whole_well_pdf_contains_chart_image(qapp, tmp_path) -> None:
    session = _session_with_report_curves()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    target = tmp_path / "mud-gas-with-curves.pdf"

    exported = export_hydrocarbon_interpretation_pdf(
        report,
        target,
        language=AppLanguage.RU,
        dataset=dataset,
        include_chart=True,
    )

    payload = target.read_bytes()
    assert exported == target
    assert payload.startswith(b"%PDF")
    assert target.stat().st_size > 20_000
    assert _pdf_page_count(payload) >= 3


def test_long_well_pdf_uses_more_chart_pages_than_short_well(qapp, tmp_path) -> None:
    short_session = _session_with_report_curves(depth_span=40.0, samples=161)
    long_session = _session_with_report_curves(depth_span=3_000.0, samples=1_501)
    short_dataset = short_session.current_dataset
    long_dataset = long_session.current_dataset
    assert short_dataset is not None
    assert long_dataset is not None
    short_target = tmp_path / "short-well.pdf"
    long_target = tmp_path / "long-well.pdf"

    export_hydrocarbon_interpretation_pdf(
        build_hydrocarbon_interpretation_report(short_session),
        short_target,
        language=AppLanguage.RU,
        dataset=short_dataset,
        include_chart=True,
    )
    export_hydrocarbon_interpretation_pdf(
        build_hydrocarbon_interpretation_report(long_session),
        long_target,
        language=AppLanguage.RU,
        dataset=long_dataset,
        include_chart=True,
    )

    short_pages = _pdf_page_count(short_target.read_bytes())
    long_pages = _pdf_page_count(long_target.read_bytes())
    assert short_pages >= 3
    assert long_pages > short_pages
    assert long_pages <= short_pages + 12


def test_workspace_exposes_primary_recalculation_and_chart_actions(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.RU,
    )

    assert workspace.recalculate_all_button.text().startswith("2. Рассчитать кривые")
    assert workspace.refresh_chart_report_button.text() == "3. Обновить и проверить отчёт"
    report_index = workspace.report_mode.findData("well_text")
    assert report_index >= 0
    assert "с графиками" in workspace.report_mode.itemText(report_index)
    workspace.close()
