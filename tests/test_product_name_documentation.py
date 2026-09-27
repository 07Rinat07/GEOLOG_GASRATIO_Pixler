from __future__ import annotations

from pathlib import Path
import re

from geoworkbench.product_identity import PRODUCT_NAME


EXPECTED_PRODUCT_NAME = "DIGITAL GEOLOG GASRATIO&PIXLER"
LEGACY_PRODUCT_NAMES = (
    "GEOLOG " + "GASRATIO@Pixler",
    "Geolog " + "GASRATIO&Pixler",
)


def test_product_name_contract() -> None:
    assert PRODUCT_NAME == EXPECTED_PRODUCT_NAME
    assert not PRODUCT_NAME.startswith("DIGITAL DIGITAL ")


def test_canonical_product_name_is_used_in_primary_documentation() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    paths = [
        repository_root / "README.md",
        repository_root / "LICENSE",
        repository_root / "pyproject.toml",
        repository_root / "docs" / "BRANDING.md",
        repository_root / "docs" / "README.md",
        repository_root / "docs" / "USER_GUIDE_RU.md",
        repository_root / "docs" / "USER_GUIDE_KK.md",
        repository_root / "docs" / "USER_GUIDE_EN.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert PRODUCT_NAME in text, path
        assert "DIGITAL DIGITAL GEOLOG" not in text, path


def test_first_party_text_does_not_reintroduce_legacy_product_names() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    roots = (
        repository_root / "src" / "geoworkbench",
        repository_root / "tests",
        repository_root / "docs",
    )
    suffixes = {
        ".py", ".md", ".json", ".toml", ".txt", ".yml", ".yaml",
        ".ini", ".cfg", ".ps1", ".sh", ".bat", ".xml", ".html", ".css", ".qss",
    }
    paths = [
        repository_root / "README.md",
        repository_root / "LICENSE",
        repository_root / "SECURITY.md",
        repository_root / "pyproject.toml",
    ]
    for root in roots:
        paths.extend(
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in suffixes
            and "vendor_reference" not in path.parts
        )

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "DIGITAL DIGITAL GEOLOG" not in text, path
        for legacy_name in LEGACY_PRODUCT_NAMES:
            assert legacy_name not in text, path

        for match in re.finditer(
            r"(?i)\\b(?:digital\\s+)*geolog\\s+gasratio(?:\\s*@\\s*|\\s*&\\s*|\\s+)pixler\\b",
            text,
        ):
            assert match.group(0) == PRODUCT_NAME, (path, match.group(0))
