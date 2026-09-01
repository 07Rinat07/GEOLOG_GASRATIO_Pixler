from pathlib import Path

from tools.check_documentation import (
    audit_compact_column_coverage,
    audit_current_documentation_contract,
    audit_daily_project_workflow_coverage,
    audit_documentation_hygiene,
    audit_documentation_navigation,
    audit_form_creation_naming_coverage,
    audit_i18n_key_parity,
    audit_localized_document_structure,
    audit_localized_file_parity,
    audit_markdown_links,
    audit_runtime_contract,
    audit_startup_command_contract,
    audit_user_workflow_coverage,
    audit_version_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_localized_document_sets_are_identical() -> None:
    """A user-facing document may not exist in only one or two languages."""

    assert audit_localized_file_parity(ROOT) == []



def test_current_localized_guides_have_comparable_structure() -> None:
    """A translated current guide must not be only a shortened placeholder."""

    assert audit_localized_document_structure(ROOT) == []


def test_documentation_tree_contains_only_current_sources() -> None:
    """Generated reports and parallel plans must stay out of the documentation tree."""

    assert audit_documentation_hygiene(ROOT) == []


def test_documentation_hygiene_rejects_generated_and_parallel_sources(
    tmp_path: Path,
) -> None:
    """The hygiene gate must reject every removed document category."""

    docs = tmp_path / "docs"
    localized = docs / "ru"
    validation = docs / "validation"
    localized.mkdir(parents=True)
    validation.mkdir()

    (docs / "PROJECT_PLAN.md").write_text("# Canonical plan\n", encoding="utf-8")
    (
        validation / "ETP12_INTEROPERABILITY_MATRIX_TEMPLATE.csv"
    ).write_text("scenario,status\n", encoding="utf-8")
    forbidden = (
        docs / "RELEASE_NOTES_0.7.93.md",
        docs / "BUILD_MANIFEST_0.7.93.md",
        docs / "HOTFIX_REPORT_0.7.93.md",
        docs / "IMPLEMENTATION_REPORT_0.7.93.md",
        docs / "INCREMENT_0.7.md",
        localized / "PROJECT_PLAN.md",
        docs / "PRODUCT_AUDIT_2026.md",
        docs / "PROJECT_STATUS.md",
        docs / "ROADMAP.md",
        validation / "render.png",
        docs / "LAS_curve_zero_validation_0.7.87.json",
    )
    for path in forbidden:
        path.write_text("generated\n", encoding="utf-8")

    issues = audit_documentation_hygiene(tmp_path)
    rejected = {
        issue.message.split(" is forbidden:", 1)[0]
        for issue in issues
    }
    assert rejected == {
        path.relative_to(tmp_path).as_posix()
        for path in forbidden
    }


def test_all_internal_markdown_links_resolve() -> None:
    """Documentation navigation must not lead to missing local files."""

    assert audit_markdown_links(ROOT) == []


def test_all_documents_are_reachable_from_the_canonical_index() -> None:
    """No current guide or engineering contract may become an orphan."""

    assert audit_documentation_navigation(ROOT) == []


def test_navigation_audit_rejects_an_orphan_document(tmp_path: Path) -> None:
    """The canonical index must lead to every Markdown document."""

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "DOCUMENTATION_INDEX.md").write_text(
        "# Index\n\n[Current](CURRENT.md)\n",
        encoding="utf-8",
    )
    (docs / "CURRENT.md").write_text("# Current\n", encoding="utf-8")
    orphan = docs / "ORPHAN.md"
    orphan.write_text("# Orphan\n", encoding="utf-8")

    issues = audit_documentation_navigation(tmp_path)
    assert [issue.message for issue in issues] == [
        "docs/ORPHAN.md is not reachable from docs/DOCUMENTATION_INDEX.md"
    ]


def test_interface_translation_keys_are_synchronized() -> None:
    """Stable interface keys must be present in RU, KK, and EN catalogs."""

    assert audit_i18n_key_parity(ROOT) == []


def test_package_metadata_uses_one_version() -> None:
    """Package metadata must expose one version without per-build documents."""

    assert audit_version_contract(ROOT) == []


def test_current_runtime_contract_matches_source_constants() -> None:
    """Canonical architecture and plan may not advertise stale schema versions."""

    assert audit_runtime_contract(ROOT) == []


def test_guides_cover_save_reopen_and_catalog_symbols() -> None:
    """The complete symbol lifecycle must remain documented in every language."""

    assert audit_user_workflow_coverage(ROOT) == []


def test_guides_cover_portable_project_daily_append_and_three_languages() -> None:
    """The main guides must retain the safe daily .geologpkg workflow."""

    assert audit_daily_project_workflow_coverage(ROOT) == []


def test_guides_cover_compact_columns_and_embedded_user_template() -> None:
    """All three languages must explain widths, migration, and the built-in template."""

    assert audit_compact_column_coverage(ROOT) == []


def test_guides_cover_visible_library_and_duplicate_name_protection() -> None:
    """Creation instructions must show how to review and name forms in every language."""

    assert audit_form_creation_naming_coverage(ROOT) == []


def test_documented_startup_command_matches_module_entrypoint() -> None:
    """README and localized guides must use the executable module command."""

    assert audit_startup_command_contract(ROOT) == []


def test_current_index_and_testing_guide_use_canonical_entry_points() -> None:
    """Current documentation navigation must point to canonical documents."""

    assert audit_current_documentation_contract(ROOT) == []
