from pathlib import Path

from tools.check_documentation import (
    audit_i18n_key_parity,
    audit_localized_document_structure,
    audit_localized_file_parity,
    audit_markdown_links,
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

def test_all_internal_markdown_links_resolve() -> None:
    """Documentation navigation must not lead to missing local files."""

    assert audit_markdown_links(ROOT) == []


def test_interface_translation_keys_are_synchronized() -> None:
    """Stable interface keys must be present in RU, KK, and EN catalogs."""

    assert audit_i18n_key_parity(ROOT) == []


def test_package_and_current_release_documents_use_one_version() -> None:
    """Package metadata, release notes, and manifests must describe one build."""

    assert audit_version_contract(ROOT) == []


def test_guides_cover_save_reopen_and_catalog_symbols() -> None:
    """The complete symbol lifecycle must remain documented in every language."""

    assert audit_user_workflow_coverage(ROOT) == []
