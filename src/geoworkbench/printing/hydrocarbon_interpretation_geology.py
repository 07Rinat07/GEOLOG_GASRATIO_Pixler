from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.printing.geology_track_rendering import (
    FrozenCuttingsComponent,
    FrozenCuttingsSample,
)
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.lba_observations import has_recorded_lba


@dataclass(frozen=True, slots=True)
class InterpretationGeologySnapshot:
    samples: tuple[FrozenCuttingsSample, ...]
    lithotypes: tuple[CatalogLithotype, ...]

    @property
    def lithotype_map(self) -> dict[str, CatalogLithotype]:
        return {item.lithotype_id: item for item in self.lithotypes}

    @property
    def has_cuttings(self) -> bool:
        return any(sample.components for sample in self.samples)

    @property
    def has_lba(self) -> bool:
        return any(has_recorded_lba(sample) for sample in self.samples)


def interpretation_geology_snapshot(
    session: ProjectSession,
) -> InterpretationGeologySnapshot | None:
    well = session.current_well
    if well is None or not well.cuttings:
        return None

    samples = tuple(
        FrozenCuttingsSample(
            sample_id=sample.sample_id,
            top_depth=float(sample.top_depth),
            bottom_depth=float(sample.bottom_depth),
            components=tuple(
                FrozenCuttingsComponent(
                    lithotype_id=component.lithotype_id,
                    percentage=float(component.percentage),
                )
                for component in sample.components
            ),
            lba_group=sample.lba_group,
            lba_type_id=sample.lba_type_id,
            lba_intensity=sample.lba_intensity,
            lba_color=sample.lba_color,
            lba_distribution=sample.lba_distribution,
            lba_cut=sample.lba_cut,
            lba_description=sample.lba_description,
            lba_cut_speed=sample.lba_cut_speed,
            lba_cut_color=sample.lba_cut_color,
            lba_residue_type=sample.lba_residue_type,
            lba_residue_color=sample.lba_residue_color,
            lba_odour=sample.lba_odour,
            lba_stain=sample.lba_stain,
        )
        for sample in well.cuttings
    )
    used_lithotypes = {
        component.lithotype_id
        for sample in samples
        for component in sample.components
    }
    catalog = tuple(
        item
        for item in LithotypeCatalogController(session).available()
        if item.lithotype_id in used_lithotypes
    )
    snapshot = InterpretationGeologySnapshot(samples, catalog)
    if not snapshot.has_cuttings and not snapshot.has_lba:
        return None
    return snapshot


__all__ = [
    "InterpretationGeologySnapshot",
    "interpretation_geology_snapshot",
]
