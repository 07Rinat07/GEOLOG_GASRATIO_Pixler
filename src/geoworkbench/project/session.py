from __future__ import annotations

from dataclasses import dataclass, field

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios
from geoworkbench.domain.models import Dataset, Project, Well, new_id
from geoworkbench.data.lossless_las import LosslessLasDocument
from geoworkbench.data.las_import_report import LasImportReport
from geoworkbench.tablet.models import TabletLayout
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.services.las_parameter_resolver import resolve_gas_ratio_inputs


@dataclass(slots=True)
class ProjectSession:
    project: Project = field(default_factory=lambda: Project(new_id(), "Новый проект"))
    current_well_id: str | None = None
    current_dataset_id: str | None = None
    tablet_layouts: dict[str, TabletLayout] = field(default_factory=dict)
    tablet_presets: dict[str, TabletLayout] = field(default_factory=dict)
    source_documents: dict[str, LosslessLasDocument] = field(default_factory=dict)
    import_reports: dict[str, LasImportReport] = field(default_factory=dict)
    image_assets: dict[str, ImageAsset] = field(default_factory=dict)
    dirty: bool = False

    def add_dataset(
        self,
        dataset: Dataset,
        well_name: str | None = None,
        *,
        source_document: LosslessLasDocument | None = None,
        import_report: LasImportReport | None = None,
        create_new_well: bool = False,
    ) -> Well:
        """Attach a dataset to the session and make it current.

        ``create_new_well`` is deliberately explicit.  Geological intervals,
        cuttings, stratigraphy, interpretations and canvas annotations belong to
        a :class:`Well`, not to an individual LAS dataset.  Reusing the current
        well while opening an unrelated LAS therefore makes the previous well's
        manual interpretation appear on the new file.  Normal *Open LAS* uses a
        fresh well workspace; specialised merge/insert workflows may continue to
        attach datasets to the current well.
        """

        well = None if create_new_well else self.current_well
        if well is None:
            requested_name = (well_name or dataset.headers.get("WELL") or dataset.name).strip()
            well = Well(new_id(), self._unique_well_name(requested_name or "Well"))
            self.project.wells[well.well_id] = well
            self.current_well_id = well.well_id
        well.datasets[dataset.dataset_id] = dataset
        if source_document is not None:
            self.source_documents[dataset.dataset_id] = source_document
        if import_report is not None:
            self.import_reports[dataset.dataset_id] = import_report
        self.current_dataset_id = dataset.dataset_id
        self.dirty = True
        return well

    def _unique_well_name(self, requested: str) -> str:
        """Return a readable name that does not collide in the project tree."""

        base = requested.strip() or "Well"
        existing = {well.name.casefold() for well in self.project.wells.values()}
        if base.casefold() not in existing:
            return base
        suffix = 2
        while f"{base} ({suffix})".casefold() in existing:
            suffix += 1
        return f"{base} ({suffix})"

    @property
    def current_well(self) -> Well | None:
        if self.current_well_id is None:
            return None
        return self.project.wells.get(self.current_well_id)

    @property
    def current_dataset(self) -> Dataset | None:
        well = self.current_well
        if well is None or self.current_dataset_id is None:
            return None
        return well.datasets.get(self.current_dataset_id)

    @property
    def current_tablet_layout(self) -> TabletLayout | None:
        if self.current_dataset_id is None:
            return None
        return self.tablet_layouts.get(self.current_dataset_id)

    def set_current_tablet_layout(self, layout: TabletLayout) -> None:
        if self.current_dataset_id is None:
            raise RuntimeError("Сначала выберите набор данных")
        self.tablet_layouts[self.current_dataset_id] = layout

    def calculate_basic_gas_ratios(self) -> list[str]:
        dataset = self.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала откройте LAS-файл")

        # Resolve by semantic meaning instead of relying on column order or a small
        # hard-coded list of exact LAS mnemonics. The resolver uses the Sensors catalog,
        # multilingual descriptions, chemical formulas, units and controlled aliases.
        inputs = resolve_gas_ratio_inputs(dataset)
        results = calculate_basic_ratios(inputs)
        created: list[str] = []
        for result in results.values():
            dataset.upsert_curve(
                result.mnemonic,
                result.values,
                unit=result.unit,
                description=result.description,
                provenance="calculation:basic-gas-ratio:1.0",
            )
            created.append(result.mnemonic)
        self.dirty = True
        return created
