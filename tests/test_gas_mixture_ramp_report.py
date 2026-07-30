from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.gas_mixture_ramp_report import (
    build_gas_mixture_ramp_report,
    export_gas_mixture_ramp_pdf,
    gas_mixture_ramp_html,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


def _session() -> ProjectSession:
    time = np.arange(60.0)
    dataset = Dataset(
        "sample-ramp",
        "Проба газа 17",
        DatasetKind.GTI,
        DepthDomain.TIME,
        time,
    )
    response = np.exp(-0.5 * ((time - 30.0) / 5.0) ** 2)
    for mnemonic, amplitude in (
        ("C1", 90.0),
        ("C2", 5.0),
        ("C3", 3.0),
        ("C4", 1.5),
        ("C5", 0.5),
    ):
        dataset.curves[mnemonic] = CurveData(
            CurveMetadata(
                mnemonic,
                mnemonic,
                mnemonic,
                "%",
                mnemonic,
                dataset.dataset_id,
                "source:test",
            ),
            amplitude * response,
        )
    session = ProjectSession()
    session.project.name = "Sample project"
    session.add_dataset(dataset, "Well sample")
    return session


def test_gas_mixture_ramp_uses_time_response_and_classifies_sample() -> None:
    report = build_gas_mixture_ramp_report(_session())

    assert report.time_label == "TIME, ms"
    assert report.interpretation_code == "productive_gas_increasing_wetness"
    assert report.confidence == "high"
    assert report.wetness is not None
    assert 9.0 < report.wetness < 12.0
    assert report.balance == 19.0
    assert report.character == pytest.approx(2.0 / 3.0)
    assert [item.mnemonic for item in report.components] == [
        "C1",
        "C2",
        "C3",
        "C4Σ",
        "C5Σ",
    ]
    assert dict(report.pixler_ratios)["C1/C2"] == 18.0


def test_constant_detector_background_is_not_classified_as_a_sample() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    for curve in dataset.curves.values():
        curve.values[:] = 5.0

    report = build_gas_mixture_ramp_report(session)

    assert report.interpretation_code == "background_or_no_hydrocarbons"
    assert report.wetness is None
    assert all(item.peak_value == 0.0 for item in report.components)


def test_gas_mixture_report_supports_chart_and_text_only_modes(qapp) -> None:
    report = build_gas_mixture_ramp_report(_session())

    chart = gas_mixture_ramp_html(report, AppLanguage.RU, include_chart=True)
    text_only = gas_mixture_ramp_html(report, AppLanguage.RU, include_chart=False)

    assert "data:image/png;base64," in chart
    assert "Временная диаграмма" in chart
    assert "data:image/png;base64," not in text_only
    assert "газ с увеличением содержания тяжёлых УВ" in text_only
    assert "ISO 6974-1:2012" in text_only


def test_gas_mixture_report_exports_nonempty_pdf(qapp, tmp_path) -> None:
    report = build_gas_mixture_ramp_report(_session())

    target = export_gas_mixture_ramp_pdf(
        report,
        tmp_path / "gas-mixture-ramp.pdf",
        language=AppLanguage.RU,
    )

    assert target.exists()
    assert target.stat().st_size > 1_000
