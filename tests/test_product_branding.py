from __future__ import annotations

from pathlib import Path

from geoworkbench.brand import APPLICATION_DISPLAY_NAME, REPORT_BRAND_WORDMARK


LEGACY_DISPLAY_NAMES = (
    "GEOLOG GASRATIO@Pixler",
    "GASRATIO@Pixler",
    "Geolog GASRATIO&Pixler",
    "GEOLOG GASRATIO&PIXLER",
)


def test_canonical_product_name_is_shared_by_application_and_reports() -> None:
    assert APPLICATION_DISPLAY_NAME == "DIGITAL GEOLOG GASRATIO&PIXLER"
    assert REPORT_BRAND_WORDMARK == APPLICATION_DISPLAY_NAME


def test_legacy_display_names_are_not_present_in_product_text_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "README.md",
        root / "LICENSE",
        *sorted((root / "src").rglob("*.py")),
        *sorted((root / "tests").rglob("*.py")),
        *sorted((root / "docs").rglob("*.md")),
    ]
    offenders: list[str] = []
    for path in candidates:
        if path == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        searchable_text = text.replace(APPLICATION_DISPLAY_NAME, "<CANONICAL_PRODUCT_NAME>")
        for legacy_name in LEGACY_DISPLAY_NAMES:
            if legacy_name in searchable_text:
                offenders.append(f"{path.relative_to(root)}: {legacy_name}")
    assert offenders == []
