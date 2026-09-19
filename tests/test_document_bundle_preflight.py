from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.project.document_bundle_preflight import (
    DocumentBundlePreflightCategory,
    DocumentBundlePreflightIssue,
    DocumentBundlePreflightService,
    DocumentBundlePreflightSeverity,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)


@dataclass
class StaticOutputValidator:
    issues: tuple[DocumentBundlePreflightIssue, ...]

    def validate(self, _snapshot, _output):
        return self.issues


@dataclass
class StaticCrossValidator:
    issues: tuple[DocumentBundlePreflightIssue, ...]

    def validate(self, _snapshot):
        return self.issues


def _snapshot(*, allow_drafts: bool = False) -> DocumentBundleSnapshotBinding:
    spec = DocumentBundleOutputSpec(
        output_id="masterlog",
        exporter_kind="masterlog",
        source_id="template-1",
        dataset_id="dataset-1",
        file_format=DocumentBundleOutputFormat.PDF,
        target_name="masterlog.pdf",
    )
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru", "kk"),
        orientations=("portrait",),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
        allow_drafts=allow_drafts,
        output_specs=(spec,),
    )
    return DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=request,
        project_path=__import__("pathlib").Path("project.geologpkg"),
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )


def test_missing_output_validator_is_blocking() -> None:
    report = DocumentBundlePreflightService({}).evaluate(_snapshot())

    assert report.is_ready is False
    assert report.blocking_issues[0].code == "output.validator_missing"


def test_translation_issue_blocks_final_bundle() -> None:
    issue = DocumentBundlePreflightIssue(
        code="translation.stale",
        message="Translation is stale",
        category=DocumentBundlePreflightCategory.TRANSLATION,
        language="kk",
    )
    report = DocumentBundlePreflightService(
        {"masterlog": StaticOutputValidator(())},
        (StaticCrossValidator((issue,)),),
    ).evaluate(_snapshot())

    assert report.is_ready is False
    assert report.draft_mark_required is False
    assert report.issues[0].severity is DocumentBundlePreflightSeverity.ERROR


def test_draft_policy_only_downgrades_translation_issues() -> None:
    translation = DocumentBundlePreflightIssue(
        code="translation.missing",
        message="Translation is missing",
        category=DocumentBundlePreflightCategory.TRANSLATION,
        language="kk",
    )
    dependency = DocumentBundlePreflightIssue(
        code="masterlog.dependencies_missing",
        message="Required curve is missing",
        category=DocumentBundlePreflightCategory.DEPENDENCY,
        output_id="masterlog",
    )
    report = DocumentBundlePreflightService(
        {"masterlog": StaticOutputValidator((dependency,))},
        (StaticCrossValidator((translation,)),),
    ).evaluate(_snapshot(allow_drafts=True))

    by_code = {issue.code: issue for issue in report.issues}
    assert by_code["translation.missing"].severity is DocumentBundlePreflightSeverity.WARNING
    assert (
        by_code["masterlog.dependencies_missing"].severity
        is DocumentBundlePreflightSeverity.ERROR
    )
    assert report.draft_mark_required is True
    assert report.is_ready is False
