from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
import re


REPORT_BRAND_WORDMARK = "Geolog GASRATIO&Pixler"
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class ReportVisualProfileId(StrEnum):
    """Stable identifiers for application-owned report visual profiles."""

    MODERN_OILFIELD = "modern_oilfield"


@dataclass(frozen=True, slots=True)
class ReportPalette:
    """Semantic colours shared by every printed/exported report adapter."""

    page: str
    text: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_dark: str
    accent_soft: str
    border: str
    border_strong: str
    table_header: str
    table_alt: str
    positive: str
    warning: str
    critical: str

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not isinstance(value, str) or _HEX_COLOR.fullmatch(value) is None:
                raise ValueError(f"{item.name} must be a #RRGGBB colour")


@dataclass(frozen=True, slots=True)
class ReportTypography:
    """Point-size hierarchy shared by PDF and Office export adapters."""

    title_pt: float = 22.0
    subtitle_pt: float = 10.0
    section_pt: float = 12.0
    body_pt: float = 8.5
    table_pt: float = 7.6
    caption_pt: float = 7.2
    footer_pt: float = 7.0

    def __post_init__(self) -> None:
        for item in fields(self):
            value = float(getattr(self, item.name))
            if not 5.0 <= value <= 36.0:
                raise ValueError(f"{item.name} is outside supported report range")


@dataclass(frozen=True, slots=True)
class ReportLayoutMetrics:
    """Physical-layout guidance expressed in points for paged reports."""

    accent_bar_height_pt: float = 8.0
    corner_radius_pt: float = 5.0
    card_padding_pt: float = 8.0
    section_gap_pt: float = 10.0
    footer_height_pt: float = 16.0
    thin_rule_pt: float = 0.7
    strong_rule_pt: float = 1.0

    def __post_init__(self) -> None:
        for item in fields(self):
            value = float(getattr(self, item.name))
            if value <= 0.0:
                raise ValueError(f"{item.name} must be positive")


@dataclass(frozen=True, slots=True)
class ReportVisualProfile:
    """Immutable visual contract for professional petroleum-service reports."""

    profile_id: ReportVisualProfileId
    brand_wordmark: str
    palette: ReportPalette
    typography: ReportTypography = ReportTypography()
    layout: ReportLayoutMetrics = ReportLayoutMetrics()
    monochrome_safe: bool = True

    def __post_init__(self) -> None:
        if not self.brand_wordmark.strip():
            raise ValueError("brand_wordmark must not be empty")


_COLOR_PALETTE = ReportPalette(
    page="#ffffff",
    text="#172033",
    text_secondary="#24384c",
    text_muted="#526579",
    accent="#174f78",
    accent_dark="#113b59",
    accent_soft="#e9f1f7",
    border="#9db1c5",
    border_strong="#60788e",
    table_header="#dce8f4",
    table_alt="#f6f9fc",
    positive="#2f6b4f",
    warning="#a66a00",
    critical="#a23535",
)

_GRAYSCALE_PALETTE = ReportPalette(
    page="#ffffff",
    text="#111111",
    text_secondary="#2d2d2d",
    text_muted="#5f5f5f",
    accent="#3b3b3b",
    accent_dark="#232323",
    accent_soft="#ededed",
    border="#a0a0a0",
    border_strong="#666666",
    table_header="#dddddd",
    table_alt="#f5f5f5",
    positive="#424242",
    warning="#5a5a5a",
    critical="#242424",
)


def modern_oilfield_report_profile(*, grayscale: bool = False) -> ReportVisualProfile:
    """Return the canonical application-owned report visual profile."""

    return ReportVisualProfile(
        profile_id=ReportVisualProfileId.MODERN_OILFIELD,
        brand_wordmark=REPORT_BRAND_WORDMARK,
        palette=_GRAYSCALE_PALETTE if grayscale else _COLOR_PALETTE,
    )


__all__ = [
    "REPORT_BRAND_WORDMARK",
    "ReportLayoutMetrics",
    "ReportPalette",
    "ReportTypography",
    "ReportVisualProfile",
    "ReportVisualProfileId",
    "modern_oilfield_report_profile",
]
