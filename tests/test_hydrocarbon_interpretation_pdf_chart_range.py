from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QRectF

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as chart
from geoworkbench.printing.hydrocarbon_interpretation_report_range import ReportDepthRange
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonCandidateInterval,
)
from geoworkbench.services.localization import AppLanguage


def _dataset() -> Dataset:
    return Dataset(
        dataset_id="dataset-chart-range",
        name="Chart range",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([47.0, 1980.0, 2016.2, 2200.0], dtype=np.float64),
    )


def test_chart_page_planner_uses_selected_report_depth_range(monkeypatch) -> None:
    observed: list[tuple[float, float, float]] = []

    monkeypatch.setattr(
        chart.base_chart,
        "_panel_curves",
        lambda report, dataset: (("gas", (object(),)),),
    )
    monkeypatch.setattr(chart.base_chart, "_curve_ranges", lambda panels, dataset: {})

    def _plan(top: float, bottom: float, available: float):
        observed.append((top, bottom, available))
        return ()

    monkeypatch.setattr(chart, "plan_depth_pages", _plan)
    canvas = SimpleNamespace(content_rect=QRectF(0.0, 0.0, 842.0, 560.0))
    report = SimpleNamespace(depth_unit="m")

    chart.render_chart_pages(
        canvas,
        report,  # type: ignore[arg-type]
        _dataset(),
        AppLanguage.RU,
        depth_range=ReportDepthRange(1980.0, 2016.2),
    )

    assert len(observed) == 1
    assert observed[0][0:2] == (1980.0, 2016.2)
    assert observed[0][2] > 0.0


def _candidate(
    fluid_hypothesis: str,
    *,
    top: float = 2000.0,
    bottom: float = 2002.0,
) -> HydrocarbonCandidateInterval:
    return HydrocarbonCandidateInterval(
        top_depth=top,
        bottom_depth=bottom,
        sample_count=5,
        anomaly_strength="medium",
        primary_mnemonic="TG_NORM",
        max_robust_z=4.2,
        max_primary_value=2.5,
        fluid_hypothesis=fluid_hypothesis,
        interval_wetness=None,
        background_wetness=None,
        wetness_robust_z=None,
        interval_balance=None,
        interval_character=None,
        pixler_assessment=None,
        lba_assessments=(),
        gas_lba_correlation="unknown",
        metrics=(),
        evidence=(),
    )


def test_fluid_callout_uses_explicit_fluid_name() -> None:
    assert chart._fluid_callout_spec(
        _candidate("probable_gas"),
        AppLanguage.RU,
    )[0] == "ГАЗ"
    assert chart._fluid_callout_spec(
        _candidate("wet_gas_or_gas_condensate"),
        AppLanguage.RU,
    )[0] == "ГАЗ-КОНДЕНСАТ"
    assert chart._fluid_callout_spec(
        _candidate("light_oil_high_gor"),
        AppLanguage.RU,
    )[0] == "ЛЁГКАЯ НЕФТЬ"
    assert chart._fluid_callout_spec(
        _candidate("opus_gasomer_oil"),
        AppLanguage.RU,
    )[0] == "НЕФТЬ"


def test_fluid_callout_does_not_guess_ambiguous_fluid() -> None:
    label, _color = chart._fluid_callout_spec(
        _candidate("opus_gasomer_no_consensus"),
        AppLanguage.RU,
    )

    assert label == "СМЕШАННЫЙ / НЕОПРЕДЕЛЁННЫЙ ТИП"


def test_callout_staggering_stays_inside_printable_track() -> None:
    centers = chart._stagger_callout_centers(
        (101.0, 102.0, 103.0, 104.0),
        min_center=100.0,
        max_center=160.0,
        minimum_gap=34.0,
    )

    assert len(centers) == 4
    assert all(100.0 <= center <= 160.0 for center in centers)
    assert centers == tuple(sorted(centers))


def test_callout_interval_text_marks_interpretation_as_preliminary() -> None:
    text = chart._fluid_callout_interval_text(
        _candidate("probable_gas", top=2010.25, bottom=2012.75),
        "m",
        AppLanguage.RU,
    )

    assert text.startswith("предв.")
    assert "2010.2" in text
    assert "2012.8 m" in text
