"""A Pixler plot must distinguish depth colours from candidate phase evidence."""

from html import unescape
from types import SimpleNamespace

import pytest

from geoworkbench.printing.ratio_phase_summary import ratio_phase_summary_html
from geoworkbench.services.hydrocarbon_interpretation import fluid_hypothesis_label
from geoworkbench.services.localization import AppLanguage


def _candidate(start, code, score):
    return SimpleNamespace(
        top_depth=float(start),
        bottom_depth=float(start + 2),
        fluid_hypothesis=code,
        max_robust_z=float(score),
    )


@pytest.mark.parametrize("language", list(AppLanguage))
def test_pixler_phase_key_reports_real_candidate_depth_and_not_false_productivity(language):
    candidates = (
        _candidate(4459.9, "probable_liquid_hydrocarbons", 6.21),
        _candidate(4559.9, "probable_gas_hydrocarbons", 7.55),
        _candidate(5006.9, "probable_liquid_hydrocarbons", 5.10),
    )
    report = SimpleNamespace(candidates=candidates, depth_unit="m")
    html = unescape(ratio_phase_summary_html(report, language))
    assert "4459.90–4461.90 m" in html
    assert "4559.90–4561.90 m" in html
    assert "6.21" in html and "7.55" in html
    assert fluid_hypothesis_label(candidates[0], language) in html
    assert fluid_hypothesis_label(candidates[1], language) in html
    assert "<table" in html and "<th>" in html
    assert "Pixler" in html
    assert "productiv" in html.lower() or "продуктив" in html.lower() or "өнім" in html.lower()


def test_pixler_phase_key_never_invents_nonproductive_zone_on_empty_candidates() -> None:
    html = ratio_phase_summary_html(SimpleNamespace(candidates=(), depth_unit="m"), AppLanguage.RU)
    assert "Не выделено аномальных интервалов" in html
    assert "Непродуктивность" in html
    assert "<tr><td>" not in html


def test_pixler_phase_key_limits_rows_but_reports_full_class_counts() -> None:
    rows = tuple(_candidate(1000 + index * 3, "probable_liquid_hydrocarbons", index + 1)
                 for index in range(12))
    html = ratio_phase_summary_html(SimpleNamespace(candidates=rows, depth_unit="m"), AppLanguage.RU)
    assert html.count("<tr><td>") == 3
    assert ": 12" in html
    assert "полный перечень" in html
