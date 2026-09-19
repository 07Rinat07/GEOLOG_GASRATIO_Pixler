from __future__ import annotations

import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleContractError,
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
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

def test_document_bundle_request_binds_output_specs_in_request_order() -> None:
    specs = (
        DocumentBundleOutputSpec(
            output_id="masterlog",
            exporter_kind="masterlog",
            source_id="template-1",
            dataset_id="dataset-1",
            file_format=DocumentBundleOutputFormat.PDF,
            target_name="masterlog.pdf",
        ),
        DocumentBundleOutputSpec(
            output_id="gas-report",
            exporter_kind="report",
            source_id="report-1",
            dataset_id="dataset-1",
            file_format=DocumentBundleOutputFormat.DOCX,
            target_name="gas-report.docx",
        ),
    )

    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog", "gas-report"),
        languages=("ru",),
        orientations=("portrait",),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
        output_specs=specs,
    )

    assert request.output_specs == specs


@pytest.mark.parametrize(
    "target_name",
    ("../masterlog.pdf", "nested/masterlog.pdf", "masterlog.docx", ""),
)
def test_output_spec_rejects_unsafe_or_mismatched_target_name(
    target_name: str,
) -> None:
    with pytest.raises(DocumentBundleContractError):
        DocumentBundleOutputSpec(
            output_id="masterlog",
            exporter_kind="masterlog",
            source_id="template-1",
            file_format=DocumentBundleOutputFormat.PDF,
            target_name=target_name,
        )


def test_document_bundle_request_rejects_output_specs_that_do_not_match_ids() -> None:
    spec = DocumentBundleOutputSpec(
        output_id="other",
        exporter_kind="masterlog",
        source_id="template-1",
        file_format=DocumentBundleOutputFormat.PDF,
        target_name="masterlog.pdf",
    )

    with pytest.raises(DocumentBundleContractError, match="match output_ids"):
        DocumentBundleRequest(
            well_id="well-1",
            output_ids=("masterlog",),
            languages=("ru",),
            orientations=("portrait",),
            scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
            output_specs=(spec,),
        )
