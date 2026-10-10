from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import pytest

from geoworkbench.printing.report_visual_system import (
    REPORT_BRAND_WORDMARK,
    ReportLayoutMetrics,
    ReportTypography,
    ReportVisualProfileId,
    modern_oilfield_report_profile,
)


def test_report_brand_wordmark_is_canonical() -> None:
    assert REPORT_BRAND_WORDMARK == "DIGITAL GEOLOG GASRATIO&PIXLER"


def test_modern_oilfield_profile_has_shared_brand_and_semantic_palette() -> None:
    profile = modern_oilfield_report_profile()

    assert profile.profile_id is ReportVisualProfileId.MODERN_OILFIELD
    assert profile.brand_wordmark == REPORT_BRAND_WORDMARK
    assert profile.monochrome_safe is True
    assert profile.palette.page == "#ffffff"
    assert profile.palette.text != profile.palette.page
    assert profile.palette.accent != profile.palette.page


def test_grayscale_profile_keeps_same_brand_and_distinguishable_roles() -> None:
    profile = modern_oilfield_report_profile(grayscale=True)

    assert profile.brand_wordmark == REPORT_BRAND_WORDMARK
    assert profile.palette.accent != profile.palette.accent_soft
    assert profile.palette.critical != profile.palette.page


def test_print_footer_wordmarks_use_bold_brand_without_changing_canonical_text() -> None:
    root = Path(__file__).resolve().parents[1]
    pdf_canvas = (
        root / "src" / "geoworkbench" / "printing" / "hydrocarbon_interpretation_pdf_canvas.py"
    ).read_text(encoding="utf-8")
    masterlog = (
        root / "src" / "geoworkbench" / "printing" / "masterlog_renderer.py"
    ).read_text(encoding="utf-8")

    assert "brand_font.setBold(True)" in pdf_canvas
    assert "self._footer_font(REPORT_BRAND_WORDMARK)" in pdf_canvas
    assert "font.setBold(True)" in masterlog
    assert "font.setBold(False)" in masterlog
    assert 'from geoworkbench.brand import REPORT_BRAND_WORDMARK' in (
        root / "src" / "geoworkbench" / "printing" / "report_visual_system.py"
    ).read_text(encoding="utf-8")

@pytest.mark.parametrize(
    "invalid", (float("nan"), float("inf"), float("-inf"), True, "8.0", None),
)
@pytest.mark.parametrize("field_name", (field.name for field in fields(ReportLayoutMetrics)))
def test_report_layout_rejects_non_finite_or_non_numeric_dimensions(
    field_name: str, invalid: object,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        replace(ReportLayoutMetrics(), **{field_name: invalid})


@pytest.mark.parametrize(
    "invalid", (float("nan"), float("inf"), float("-inf"), True, "8.0", None),
)
@pytest.mark.parametrize("field_name", (field.name for field in fields(ReportTypography)))
def test_report_typography_rejects_non_finite_or_non_numeric_font_sizes(
    field_name: str, invalid: object,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        replace(ReportTypography(), **{field_name: invalid})


def test_report_point_dimensions_preserve_valid_values_and_ranges() -> None:
    layout = ReportLayoutMetrics(thin_rule_pt=0.35, section_gap_pt=12.0)
    type_scale = ReportTypography(body_pt=9.25, footer_pt=6.0)
    assert layout.thin_rule_pt == 0.35
    assert layout.section_gap_pt == 12.0
    assert type_scale.body_pt == 9.25
    assert type_scale.footer_pt == 6.0
    with pytest.raises(ValueError, match="thin_rule_pt"):
        ReportLayoutMetrics(thin_rule_pt=0.0)
    with pytest.raises(ValueError, match="body_pt"):
        ReportTypography(body_pt=36.1)
