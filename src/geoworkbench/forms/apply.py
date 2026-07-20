from __future__ import annotations

from dataclasses import dataclass, field

from geoworkbench.catalogs.sensors import SensorCatalog, active_sensor_catalog, normalize_sensor_key
from geoworkbench.domain.models import Dataset, IndexRole, new_id
from geoworkbench.forms.models import FormDocument, FormAxisKind, ParameterBinding
from geoworkbench.tablet.models import (
    CurveDisplaySettings,
    TabletLayout,
    TrackDefinition,
    XScale,
)


@dataclass(frozen=True, slots=True)
class BindingResolution:
    binding_id: str
    canonical_parameter_id: str
    mnemonic: str | None
    matched_by: str

    @property
    def resolved(self) -> bool:
        return self.mnemonic is not None


@dataclass(slots=True)
class FormApplyResult:
    layout: TabletLayout
    resolutions: list[BindingResolution] = field(default_factory=list)

    @property
    def resolved_count(self) -> int:
        return sum(item.resolved for item in self.resolutions)

    @property
    def missing(self) -> list[BindingResolution]:
        return [item for item in self.resolutions if not item.resolved]


class FormApplyEngine:
    """Resolve a form against one dataset and build a TabletLayout.

    This intentionally implements only the confirmed first application slice:
    explicit mnemonic, canonical mnemonic and Sensors/user-catalog matching.  It
    does not yet perform unit conversion or calculated-curve creation.
    """

    def __init__(self, catalog: SensorCatalog | None = None) -> None:
        self.catalog = catalog or active_sensor_catalog()

    def resolve_binding(self, dataset: Dataset, binding: ParameterBinding) -> BindingResolution:
        if binding.source_mnemonic:
            curve = dataset.curve_by_mnemonic(binding.source_mnemonic)
            if curve is not None:
                return BindingResolution(
                    binding.binding_id,
                    binding.canonical_parameter_id,
                    curve.metadata.original_mnemonic,
                    "explicit",
                )

        curve = dataset.curve_by_mnemonic(binding.canonical_parameter_id)
        if curve is not None:
            return BindingResolution(
                binding.binding_id,
                binding.canonical_parameter_id,
                curve.metadata.original_mnemonic,
                "canonical",
            )

        wanted = normalize_sensor_key(binding.canonical_parameter_id)
        for candidate in dataset.curves.values():
            metadata = candidate.metadata
            match = self.catalog.match(
                metadata.original_mnemonic,
                description=metadata.description or "",
                unit=metadata.unit or "",
            )
            if match is not None and normalize_sensor_key(match.definition.canonical_mnemonic) == wanted:
                return BindingResolution(
                    binding.binding_id,
                    binding.canonical_parameter_id,
                    metadata.original_mnemonic,
                    "catalog",
                )
        return BindingResolution(
            binding.binding_id,
            binding.canonical_parameter_id,
            None,
            "missing",
        )

    def build_layout(self, form: FormDocument, dataset: Dataset) -> FormApplyResult:
        tracks: list[TrackDefinition] = []
        resolutions: list[BindingResolution] = []
        for column in form.columns:
            if not column.visible:
                continue
            for form_track in column.tracks:
                if not form_track.visible:
                    continue
                resolved_mnemonics: list[str] = []
                styles = {}
                display_settings = {}
                x_scale = None
                x_min = None
                x_max = None
                for binding in form_track.bindings:
                    resolution = self.resolve_binding(dataset, binding)
                    resolutions.append(resolution)
                    if not binding.visible or resolution.mnemonic is None:
                        continue
                    resolved_mnemonics.append(resolution.mnemonic)
                    styles[resolution.mnemonic] = binding.style
                    display_settings[resolution.mnemonic] = CurveDisplaySettings(
                        display_name=binding.display_name,
                        x_scale=binding.x_scale,
                        x_min=binding.x_min,
                        x_max=binding.x_max,
                    )
                    if x_scale is None:
                        x_scale = binding.x_scale
                        x_min = binding.x_min
                        x_max = binding.x_max

                tracks.append(
                    TrackDefinition(
                        track_id=form_track.track_id or new_id(),
                        title=form_track.title or column.title,
                        kind=form_track.kind,
                        curve_mnemonics=resolved_mnemonics,
                        width=column.width,
                        visible=True,
                        locked=form_track.locked or column.locked,
                        x_scale=x_scale or XScale.LINEAR,
                        x_min=x_min,
                        x_max=x_max,
                        curve_styles=styles,
                        curve_display=display_settings,
                        grid_x=form_track.grid_x,
                        grid_y=form_track.grid_y,
                        grid_alpha=form_track.grid_alpha,
                        x_axis_label=form_track.x_axis_label,
                    )
                )

        preferred = dataset.active_index
        wanted_role = IndexRole.DEPTH if form.axis_kind is FormAxisKind.DEPTH else IndexRole.TIME
        if preferred.role is not wanted_role:
            preferred = next(
                (index for index in dataset.indexes.values() if index.role is wanted_role),
                preferred,
            )
        return FormApplyResult(
            TabletLayout(tracks=tracks, vertical_index_id=preferred.index_id),
            resolutions,
        )
