from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleScopeKind,
)
from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    LoadedDocumentBundleSnapshot,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.document_bundle_artifacts import (
    DocumentBundleArtifactSpec,
    expand_document_bundle_artifacts,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import (
    ReportKind,
    ReportPassport,
    ReportPassportBuilder,
    ReportPassportRequest,
    ReportRenderSettings,
    masterlog_template_snapshot,
    passport_sidecar_path,
)


class MasterlogBundleExportError(RuntimeError):
    """Raised when a bound Masterlog bundle artifact cannot be rendered safely."""


class BundleSnapshotLoader(Protocol):
    def load(
        self,
        binding: DocumentBundleSnapshotBinding,
    ) -> LoadedDocumentBundleSnapshot:
        """Load and verify the persisted project revision bound to the bundle."""


class MasterlogPdfRenderer(Protocol):
    def __call__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        target: Path,
        *,
        overwrite: bool,
        settings: MasterlogOutputSettings,
        passport: ReportPassport,
    ) -> Path:
        """Render one Masterlog PDF using the existing renderer boundary."""


def _render_masterlog_pdf(
    template: MasterlogTemplate,
    session: ProjectSession,
    target: Path,
    *,
    overwrite: bool,
    settings: MasterlogOutputSettings,
    passport: ReportPassport,
) -> Path:
    from geoworkbench.printing.masterlog_renderer import export_masterlog_pdf

    return export_masterlog_pdf(
        template,
        session,
        target,
        overwrite=overwrite,
        settings=settings,
        passport=passport,
    )


@dataclass(slots=True)
class MasterlogPdfBundleExporter:
    """WELL-06 adapter over the existing Masterlog PDF renderer."""

    output_id: str
    output_directory: Path
    snapshot_loader: BundleSnapshotLoader
    renderer: MasterlogPdfRenderer = _render_masterlog_pdf

    def export(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> tuple[Path, ...]:
        loaded = self.snapshot_loader.load(snapshot)
        session = self._session_from_snapshot(loaded)
        artifacts = tuple(
            artifact
            for artifact in expand_document_bundle_artifacts(snapshot.request)
            if artifact.output_id == self.output_id
        )
        if not artifacts:
            raise MasterlogBundleExportError(
                f"No artifacts are bound to Masterlog output {self.output_id!r}"
            )

        paths: list[Path] = []
        for artifact in artifacts:
            paths.extend(
                self._export_artifact(
                    snapshot=snapshot,
                    session=session,
                    artifact=artifact,
                )
            )
        return tuple(paths)

    def _export_artifact(
        self,
        *,
        snapshot: DocumentBundleSnapshotBinding,
        session: ProjectSession,
        artifact: DocumentBundleArtifactSpec,
    ) -> tuple[Path, Path]:
        if artifact.exporter_kind != "masterlog":
            raise MasterlogBundleExportError(
                f"Artifact {artifact.artifact_id} is not a Masterlog output"
            )
        if artifact.file_format is not DocumentBundleOutputFormat.PDF:
            raise MasterlogBundleExportError(
                f"Masterlog artifact {artifact.artifact_id} must use PDF format"
            )
        if artifact.dataset_id is None:
            raise MasterlogBundleExportError(
                f"Masterlog artifact {artifact.artifact_id} requires dataset_id"
            )

        well = session.project.wells[snapshot.request.well_id]
        if artifact.dataset_id not in well.datasets:
            raise MasterlogBundleExportError(
                f"Dataset {artifact.dataset_id!r} is not present in the bound well"
            )
        try:
            source_template = session.project.masterlog_templates[artifact.source_id]
        except KeyError as exc:
            raise MasterlogBundleExportError(
                f"Masterlog template {artifact.source_id!r} is not present in the snapshot"
            ) from exc

        session.current_well_id = well.well_id
        session.current_dataset_id = artifact.dataset_id

        template = deepcopy(source_template)
        if template.page_format.casefold() == "roll":
            if artifact.orientation != "portrait":
                raise MasterlogBundleExportError(
                    "Roll Masterlog output supports portrait orientation only"
                )
        else:
            template.properties["orientation"] = artifact.orientation

        settings = self._settings(snapshot, session, artifact.language)
        passport = self._passport(
            snapshot=snapshot,
            session=session,
            artifact=artifact,
            template=template,
            settings=settings,
        )
        target = self.output_directory / artifact.target_name
        rendered = self.renderer(
            template,
            session,
            target,
            overwrite=False,
            settings=settings,
            passport=passport,
        )
        sidecar = passport_sidecar_path(rendered)
        if not sidecar.is_file() or sidecar.stat().st_size <= 0:
            raise MasterlogBundleExportError(
                f"Masterlog passport sidecar was not created: {sidecar}"
            )
        return rendered, sidecar

    @staticmethod
    def _session_from_snapshot(
        loaded: LoadedDocumentBundleSnapshot,
    ) -> ProjectSession:
        document = loaded.document
        return ProjectSession(
            project=document.project,
            current_well_id=loaded.binding.request.well_id,
            tablet_layouts=document.tablet_layouts,
            tablet_presets=document.tablet_presets,
            source_documents=document.source_documents,
            import_reports=document.import_reports,
            image_assets=document.image_assets,
            rock_code_profiles=document.rock_code_profiles,
            rock_code_source_bindings=document.rock_code_source_bindings,
            dirty=False,
        )

    @staticmethod
    def _passport(
        *,
        snapshot: DocumentBundleSnapshotBinding,
        session: ProjectSession,
        artifact: DocumentBundleArtifactSpec,
        template: MasterlogTemplate,
        settings: MasterlogOutputSettings,
    ) -> ReportPassport:
        curve_mnemonics = tuple(
            dict.fromkeys(
                mnemonic
                for column in template.columns
                if column.column_type == "curves"
                for mnemonic in column.curve_mnemonics
            )
        )
        render = ReportRenderSettings(
            renderer="masterlog",
            output_format="pdf",
            page_format=template.page_format,
            orientation=artifact.orientation,
            dpi=300,
            range_mode=snapshot.request.scope.kind.value,
            options=(
                ("bundle_snapshot_id", snapshot.snapshot_id),
                ("project_save_revision", str(snapshot.save_revision)),
                ("well_content_revision", str(snapshot.well_content_revision)),
                ("project_bundle_sha256", snapshot.bundle_sha256),
                ("output_id", artifact.output_id),
                ("artifact_id", artifact.artifact_id),
            ),
        )
        request = ReportPassportRequest(
            report_kind=ReportKind.MASTERLOG,
            report_name=template.name,
            language=artifact.language,
            render=render,
            interval=settings.depth_range,
            curve_mnemonics=curve_mnemonics or None,
            form=masterlog_template_snapshot(template),
        )
        return ReportPassportBuilder().build(session, request)

    @staticmethod
    def _settings(
        snapshot: DocumentBundleSnapshotBinding,
        session: ProjectSession,
        language: str,
    ) -> MasterlogOutputSettings:
        scope = snapshot.request.scope
        if scope.kind is DocumentBundleScopeKind.WHOLE_WELL:
            from geoworkbench.printing.masterlog_renderer import masterlog_depth_range

            depth_range = masterlog_depth_range(session)
            if depth_range is None:
                raise MasterlogBundleExportError(
                    "The bound dataset has no printable depth range"
                )
            top, bottom = depth_range
        else:
            if scope.top_depth is None or scope.bottom_depth is None:
                raise MasterlogBundleExportError(
                    "The bound interval scope has no resolved depth bounds"
                )
            top, bottom = scope.top_depth, scope.bottom_depth

        try:
            app_language = AppLanguage(language)
        except ValueError as exc:
            raise MasterlogBundleExportError(
                f"Unsupported Masterlog language: {language}"
            ) from exc

        return MasterlogOutputSettings(
            depth_top=top,
            depth_bottom=bottom,
            language=app_language,
        )
