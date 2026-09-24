from __future__ import annotations

from geoworkbench.printing.report_visual_system import (
    REPORT_BRAND_WORDMARK,
    ReportVisualProfileId,
    modern_oilfield_report_profile,
)


def test_report_brand_wordmark_is_canonical() -> None:
    assert REPORT_BRAND_WORDMARK == "Geolog GASRATIO&Pixler"


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
