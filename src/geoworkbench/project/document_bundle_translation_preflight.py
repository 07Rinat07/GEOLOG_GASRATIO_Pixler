from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.translation_readiness import TranslationReadinessQuery
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.document_bundle_preflight import (
    DocumentBundlePreflightCategory,
    DocumentBundlePreflightIssue,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    DocumentBundleSnapshotReader,
)
from geoworkbench.project.translation_field_catalog import WellTranslationFieldCatalog


@dataclass(slots=True)
class DocumentBundleTranslationPreflightValidator:
    snapshot_reader: DocumentBundleSnapshotReader

    def validate(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> tuple[DocumentBundlePreflightIssue, ...]:
        loaded = self.snapshot_reader.load(snapshot)
        well = loaded.document.project.wells[snapshot.request.well_id]
        fields = WellTranslationFieldCatalog.fields(well)
        if not fields:
            return ()

        depth_range = None
        scope = snapshot.request.scope
        if scope.top_depth is not None and scope.bottom_depth is not None:
            depth_range = (scope.top_depth, scope.bottom_depth)

        issues: list[DocumentBundlePreflightIssue] = []
        for language in snapshot.request.languages:
            required_fields = tuple(
                field
                for field in fields
                if well.authored_field_source_languages.get(field.field_id) != language
            )
            if not required_fields:
                continue
            summary = TranslationReadinessQuery.summarize(
                required_fields,
                well.translation_statuses,
                target_languages=(language,),
                depth_range=depth_range,
                source_revisions=well.authored_field_revisions,
                dependency_revisions=well.authored_field_revisions,
                source_languages=well.authored_field_source_languages,
                include_reviewed=False,
            )
            for item in summary.items:
                if item.state is TranslationState.REVIEWED:
                    continue
                issues.append(
                    DocumentBundlePreflightIssue(
                        code=f"translation.{item.state.value}",
                        message=(
                            f"{item.field.label} requires a current reviewed "
                            f"{language.upper()} translation"
                        ),
                        category=DocumentBundlePreflightCategory.TRANSLATION,
                        language=language,
                    )
                )
        return tuple(issues)
