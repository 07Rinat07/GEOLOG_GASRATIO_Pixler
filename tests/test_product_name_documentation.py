from __future__ import annotations

from pathlib import Path

from geoworkbench.product_identity import PRODUCT_NAME


LEGACY_PRODUCT_NAMES = (
    "GEOLOG GASRATIO&PIXLER",
    "GEOLOG GASRATIO@Pixler",
    "Geolog GASRATIO&Pixler",
)


def test_canonical_product_name_is_used_in_primary_documentation() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    paths = [
        repository_root / "README.md",
        repository_root / "LICENSE",
        repository_root / "docs" / "BRANDING.md",
        repository_root / "docs" / "README.md",
        repository_root / "docs" / "USER_GUIDE_RU.md",
        repository_root / "docs" / "USER_GUIDE_KK.md",
        repository_root / "docs" / "USER_GUIDE_EN.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert PRODUCT_NAME in text, path
        for legacy_name in LEGACY_PRODUCT_NAMES:
            assert legacy_name not in text, path


def test_documentation_does_not_reintroduce_legacy_product_wordmarks() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    documentation_paths = [repository_root / "README.md"]
    documentation_paths.extend(
        path
        for path in (repository_root / "docs").rglob("*.md")
        if "vendor_reference" not in path.parts
    )

    for path in documentation_paths:
        text = path.read_text(encoding="utf-8")
        for legacy_name in LEGACY_PRODUCT_NAMES:
            assert legacy_name not in text, path
