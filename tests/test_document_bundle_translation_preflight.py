from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geoworkbench.domain.document_bundle import (
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.domain.models import (
    LithologyInterval,
    Project,
    Well,
)
from geoworkbench.domain.translation_status import (
    TranslationState,
    TranslationStatus,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    LoadedDocumentBundleSnapshot,
)
from geoworkbench.project.document_bundle_translation_preflight import (
    DocumentBundleTranslationPreflightValidator,
)
from geoworkbench.storage.project_codec import ProjectDocument


@dataclass
class StaticReader:
    loaded: LoadedDocumentBundleSnapshot

    def load(self, _snapshot):
        return self.loaded


def _fixture(
    tmp_path: Path,
    *,
    state: TranslationState | None,
    current_revision: int = 3,
) -> tuple[DocumentBundleSnapshotBinding, LoadedDocumentBundleSnapshot]:
    field_id = "lithology/lith-1/description"
    well = Well(
        "well-1",
        "Well",
        lithology=[
            LithologyInterval(
                "lith-1",
                1000.0,
                1100.0,
                "sandstone",
                description_i18n={"ru": "Песчаник"},
            )
        ],
        content_revision=9,
        authored_field_revisions={field_id: current_revision},
        authored_field_source_languages={field_id: "ru"},
    )
    if state is not None:
        well.translation_statuses[field_id] = {
            "kk": TranslationStatus(
                state=state,
                source_language="ru",
                source_revision=3,
                translation_revision=2,
            )
        }

    project = Project(
        "project-1",
        "Project",
        wells={well.well_id: well},
        save_revision=4,
    )
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("placeholder",),
        languages=("ru", "kk"),
        orientations=("portrait",),
        scope=DocumentBundleScope(
            DocumentBundleScopeKind.INTERVAL,
            top_depth=1000.0,
            bottom_depth=1100.0,
        ),
    )
    snapshot = DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=request,
        project_path=tmp_path / "project.geologpkg",
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )
    return snapshot, LoadedDocumentBundleSnapshot(
        binding=snapshot,
        document=ProjectDocument(project),
    )


def test_translation_preflight_skips_explicit_source_language_and_accepts_reviewed(
    tmp_path: Path,
) -> None:
    snapshot, loaded = _fixture(tmp_path, state=TranslationState.REVIEWED)

    issues = DocumentBundleTranslationPreflightValidator(
        StaticReader(loaded)  # type: ignore[arg-type]
    ).validate(snapshot)

    assert issues == ()


def test_translation_preflight_reports_missing_target_translation(tmp_path: Path) -> None:
    snapshot, loaded = _fixture(tmp_path, state=None)

    issues = DocumentBundleTranslationPreflightValidator(
        StaticReader(loaded)  # type: ignore[arg-type]
    ).validate(snapshot)

    assert len(issues) == 1
    assert issues[0].code == "translation.missing"
    assert issues[0].language == "kk"


def test_translation_preflight_detects_stale_reviewed_translation(tmp_path: Path) -> None:
    snapshot, loaded = _fixture(
        tmp_path,
        state=TranslationState.REVIEWED,
        current_revision=4,
    )

    issues = DocumentBundleTranslationPreflightValidator(
        StaticReader(loaded)  # type: ignore[arg-type]
    ).validate(snapshot)

    assert len(issues) == 1
    assert issues[0].code == "translation.stale"
