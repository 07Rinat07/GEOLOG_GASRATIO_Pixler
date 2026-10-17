"""RU/KK/EN analytical causes are measured, localized, and opt-in."""

from __future__ import annotations

from dataclasses import replace
from html import unescape

import pytest

from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.interpretation_method_comparison import (
    MethodComparisonInterval,
    MethodComparisonStatus,
)
from geoworkbench.services.interpretation_method_comparison_html import (
    _REASONS,
    method_comparison_html,
)
from geoworkbench.services.localization import AppLanguage


def _item(
    code: str = "bounded_phase_agreement",
    status: MethodComparisonStatus = MethodComparisonStatus.AGREEMENT,
) -> MethodComparisonInterval:
    return MethodComparisonInterval(
        standard_bounds=(100.0, 104.0),
        opus_bounds=(100.0, 104.0),
        status=status,
        reason_code=code,
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


@pytest.mark.parametrize(
    ("language", "heading", "status_label", "reason_fragment"),
    [
        (
            AppLanguage.RU,
            "Сопоставление стандартного метода и ОПУС",
            "Признаки согласуются",
            "одинаковое направление",
        ),
        (
            AppLanguage.KK,
            "Стандартты әдіс пен ОПУС нәтижелерін салыстыру",
            "Белгілер сәйкес келеді",
            "бір бағыттағы",
        ),
        (
            AppLanguage.EN,
            "Standard and OPUS method comparison",
            "Indicators agree",
            "same broad gas",
        ),
    ],
)
def test_localized_analytical_html_preserves_actual_evidence(
    language: AppLanguage, heading: str, status_label: str, reason_fragment: str,
) -> None:
    item = _item()
    original = replace(item)
    html = method_comparison_html((item,), language, depth_unit="m")
    assert heading in html
    assert status_label in html
    assert reason_fragment in html
    assert "100.00–104.00 m" in html
    assert "80.0% / 50.0%" in html
    assert "3.2" in html and "17" in html
    assert "62.5%" in html
    assert "data-reason-version=\"1\"" in html
    assert 'data-reason-code="bounded_phase_agreement"' in html
    assert "notice" not in html
    assert "method-comparison-analytics" in html
    assert "bounded_phase_agreement</td>" not in html
    assert item == original


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("code", sorted(_REASONS))
def test_all_reason_codes_have_explicit_language_not_raw_codes(
    language: AppLanguage, code: str,
) -> None:
    html = method_comparison_html(
        (_item(code, MethodComparisonStatus.INSUFFICIENT),),
        language,
    )
    assert _REASONS[code][language] in unescape(html)
    assert f">{code}<" not in html
    assert 'data-reason-code="' + code + '"' in html


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (AppLanguage.RU, "Недостаточно данных для сравнения"),
        (AppLanguage.KK, "Салыстыру үшін дерек жеткіліксіз"),
        (AppLanguage.EN, "Insufficient data for comparison"),
    ],
)
def test_class_four_does_not_claim_water_in_any_language(
    language: AppLanguage, expected: str,
) -> None:
    item = replace(
        _item("opus_class_four_unverified", MethodComparisonStatus.INSUFFICIENT),
        opus_class_code=4,
        opus_phase=FluidPhaseContract.INDETERMINATE,
    )
    html = method_comparison_html((item,), language)
    assert expected in html
    assert _REASONS["opus_class_four_unverified"][language] in html


def test_missing_measurements_are_not_rendered_as_zero_or_nan() -> None:
    item = replace(
        _item("standard_context_unavailable", MethodComparisonStatus.INSUFFICIENT),
        standard_wetness_robust_z=None,
        standard_pixler_c1_c2=None,
        opus_support_fraction=None,
    )
    html = method_comparison_html((item,), AppLanguage.EN)
    assert "Wetness robust-z: —" in html
    assert "Pixler C1/C2: —" in html
    assert "OPUS class support: —" in html
    assert "nan" not in html.casefold()


def test_html_escapes_untrusted_unit_and_reason_code() -> None:
    item = replace(
        _item(),
        reason_code='<img src=x onerror="evil">',
    )
    html = method_comparison_html((item,), AppLanguage.EN, depth_unit="<ft>")
    assert "<img" not in html
    assert "<ft>" not in html
    assert "&lt;ft&gt;" in html
    assert "&lt;img" in html
    assert "The reason requires review against source data." in html


def test_opt_in_html_adds_analytical_section_without_changing_default() -> None:
    report = HydrocarbonInterpretationReport(
        project_name="Project",
        well_name="Well",
        dataset_id="dataset",
        dataset_name="Dataset",
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
    default_html = hydrocarbon_interpretation_html(report, AppLanguage.EN)
    assert "method-comparison-analytics" not in default_html
    enriched = hydrocarbon_interpretation_html(
        report, AppLanguage.EN, method_comparisons=(_item(),),
    )
    assert "method-comparison-analytics" in enriched
    assert "Indicators agree" in enriched
    assert enriched.count("method-comparison-analytics") == 1
    assert default_html.endswith("</html>") == enriched.endswith("</html>")


@pytest.mark.parametrize("language", list(AppLanguage))
def test_no_comparison_rows_means_no_false_agreement(language: AppLanguage) -> None:
    html = method_comparison_html((), language)
    assert "<table" not in html
    assert "<p>" in html
    assert "data-reason-code" not in html
