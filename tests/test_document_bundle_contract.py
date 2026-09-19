from __future__ import annotations

import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleContractError,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)


def test_document_bundle_request_accepts_valid_multi_language_selection() -> None:
    request = DocumentBundleRequest(
        well_id=" well-1 ",
        output_ids=("masterlog", "gas-report"),
        languages=("ru", "kk", "en"),
        orientations=("portrait", "landscape"),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
    )

    assert request.well_id == "well-1"
    assert request.output_ids == ("masterlog", "gas-report")
    assert request.languages == ("ru", "kk", "en")
    assert request.orientations == ("portrait", "landscape")


@pytest.mark.parametrize(
    ("kind", "top_depth", "bottom_depth"),
    (
        (DocumentBundleScopeKind.INTERVAL, 1000.0, 1000.0),
        (DocumentBundleScopeKind.INTERVAL, 1001.0, 1000.0),
        (DocumentBundleScopeKind.NEW_SECTION, None, 1100.0),
        (DocumentBundleScopeKind.NEW_SECTION, 1000.0, None),
        (DocumentBundleScopeKind.INTERVAL, float("nan"), 1100.0),
    ),
)
def test_document_bundle_scope_rejects_invalid_bounds(
    kind: DocumentBundleScopeKind,
    top_depth: float | None,
    bottom_depth: float | None,
) -> None:
    with pytest.raises(DocumentBundleContractError):
        DocumentBundleScope(kind, top_depth, bottom_depth)


def test_whole_well_scope_rejects_explicit_bounds() -> None:
    with pytest.raises(DocumentBundleContractError):
        DocumentBundleScope(
            DocumentBundleScopeKind.WHOLE_WELL,
            top_depth=1000.0,
            bottom_depth=1100.0,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("well_id", ""),
        ("output_ids", ()),
        ("output_ids", ("masterlog", "masterlog")),
        ("languages", ("ru", "de")),
        ("languages", ("ru", "ru")),
        ("orientations", ("portrait", "square")),
        ("orientations", ("landscape", "landscape")),
    ),
)
def test_document_bundle_request_rejects_invalid_selection(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "well_id": "well-1",
        "output_ids": ("masterlog",),
        "languages": ("ru",),
        "orientations": ("portrait",),
        "scope": DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
    }
    kwargs[field_name] = value

    with pytest.raises(DocumentBundleContractError):
        DocumentBundleRequest(**kwargs)  # type: ignore[arg-type]


def test_document_bundle_request_preserves_explicit_draft_policy() -> None:
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru",),
        orientations=("portrait",),
        scope=DocumentBundleScope(
            DocumentBundleScopeKind.INTERVAL,
            top_depth=1000.0,
            bottom_depth=1100.0,
        ),
        allow_drafts=True,
    )

    assert request.allow_drafts is True
