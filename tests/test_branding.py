import pytest

from geoworkbench.ui.branding import application_icon, about_program_logo_pixmap, logo_pixmap


def test_packaged_logo_loads_and_scales(qapp) -> None:
    original = logo_pixmap()
    scaled = logo_pixmap(128)

    assert not original.isNull()
    assert original.width() == 1254
    assert original.height() == 1254
    assert not scaled.isNull()
    assert scaled.width() <= 128
    assert scaled.height() <= 128
    about = about_program_logo_pixmap(420, 420)
    assert not about.isNull()
    assert about.width() <= 420
    assert about.height() <= 420
    assert not application_icon().isNull()


def test_logo_rejects_invalid_target_size(qapp) -> None:
    with pytest.raises(ValueError, match="положительным"):
        logo_pixmap(0)


def test_branding_uses_one_canonical_logo_resource() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    branding_source = (
        root / "src" / "geoworkbench" / "ui" / "branding.py"
    ).read_text(encoding="utf-8")
    canonical_logo = "geologist-logo.png"
    legacy_about_logo = "about-program-" + "logo.png"

    assert f"resources/{canonical_logo}" in branding_source
    assert legacy_about_logo not in branding_source
    assert (root / "src" / "geoworkbench" / "resources" / canonical_logo).is_file()
    assert not (
        root / "src" / "geoworkbench" / "resources" / legacy_about_logo
    ).exists()

    candidates = [
        root / "README.md",
        *sorted((root / "src").rglob("*.py")),
        *sorted((root / "tests").rglob("*.py")),
        *sorted((root / "docs").rglob("*.md")),
    ]
    offenders = [
        str(candidate.relative_to(root))
        for candidate in candidates
        if candidate != Path(__file__).resolve()
        and legacy_about_logo in candidate.read_text(encoding="utf-8")
    ]
    assert offenders == []
