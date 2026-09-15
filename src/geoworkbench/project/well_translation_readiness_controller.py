from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from geoworkbench.domain.translation_readiness import (
    TranslatableField,
    TranslationReadinessQuery,
    TranslationReadinessSummary,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_field_catalog import WellTranslationFieldCatalog


@dataclass(slots=True)
class WellTranslationReadinessController:
    """Read-only application boundary for WELL-04 readiness of the current well."""

    session: ProjectSession

    def fields(self) -> tuple[TranslatableField, ...]:
        return WellTranslationFieldCatalog.fields(self._require_well())

    def summarize(
        self,
        *,
        target_languages: Sequence[object],
        depth_range: tuple[float, float] | None = None,
        include_reviewed: bool = False,
    ) -> TranslationReadinessSummary:
        well = self._require_well()
        revisions = well.authored_field_revisions
        return TranslationReadinessQuery.summarize(
            WellTranslationFieldCatalog.fields(well),
            well.translation_statuses,
            target_languages=target_languages,
            depth_range=depth_range,
            source_revisions=revisions,
            # Dependency revisions use the same stable revision ledger.  Source
            # and dependency IDs occupy separate namespaces in field identity,
            # so one persisted mapping remains sufficient and version-compatible.
            dependency_revisions=revisions,
            include_reviewed=include_reviewed,
        )

    def _require_well(self):
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well
