from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_readme_contains_only_project_overview_and_navigation() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    forbidden_fragments = (
        "Текущая тестовая версия",
        "Исправлена критическая регрессия",
        "_localizer",
        "passed",
        "skipped",
        "deselected",
        "traceback",
        "hotfix",
        "release notes",
    )
    for fragment in forbidden_fragments:
        assert fragment.casefold() not in text.casefold()

    required_links = (
        "docs/PROJECT_STATUS.md",
        "docs/PROJECT_PLAN.md",
        "docs/CHANGELOG.md",
        "docs/TESTING.md",
    )
    for link in required_links:
        assert link in text


def test_root_has_no_release_manifest_document() -> None:
    root_manifests = list(ROOT.glob("FULL_PROJECT_*_MANIFEST.md"))
    assert root_manifests == []
