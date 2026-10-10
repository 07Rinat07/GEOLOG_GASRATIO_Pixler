from __future__ import annotations

from dataclasses import dataclass, field

from geoworkbench.catalogs.sensors import SensorCatalog, active_sensor_catalog, normalize_sensor_key
from geoworkbench.domain.models import Dataset, IndexRole, new_id
from geoworkbench.forms.models import (
    FormAxisKind,
    FormDocument,
    FormTemplateOrigin,
    ParameterBinding,
    TOTAL_CALCIMETRY_PARAMETERS,
)
from geoworkbench.forms.materialize import materialize_form_for_dataset
from geoworkbench.services.las_parameter_resolver import (
    DatasetParameterResolution,
    LasParameterResolver,
)
from geoworkbench.tablet.models import (
    COMPACT_TRACK_KINDS,
    CurveDisplaySettings,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)


# These sensor IDs and supporting channels occur together in the GeoScape
# LAS family (e.g. the Maksat M-1 exported LAS). Never substitute an
# unmeasured insoluble residue or guess a source from the channel description.
_GEOSCAPE_FORM_CHANNELS: dict[str, tuple[str, tuple[str, ...], frozenset[str]]] = {
    "ROP": (
        "S106",
        ("S107", "S108", "S109"),
        frozenset({"м/ч", "m/h", "m/hr", "m/hour", "ě/÷"}),
    ),
    "TOTAL_GAS": (
        "S1600",
        ("S1601", "S1602", "S1603"),
        frozenset({"%", "pct", "percent"}),
    ),
}


def _geoscape_factory_source(dataset: Dataset, canonical: str) -> str | None:
    spec = _GEOSCAPE_FORM_CHANNELS.get(canonical)
    if spec is None:
        return None
    source, companion_codes, allowed_units = spec
    curve = dataset.curve_by_mnemonic(source)
    if curve is None or curve.metadata.original_mnemonic.strip().upper() != source:
        return None
    # The code must belong to the expected measurement family. A wrong unit is
    # a hard rejection, not something to silently relabel as metres/hour or %.
    unit = (curve.metadata.unit or "").strip().casefold().replace(" ", "")
    if unit not in allowed_units:
        return None
    companions = sum(
        bool(
            (sibling := dataset.curve_by_mnemonic(code)) is not None
            and sibling.metadata.original_mnemonic.strip().upper() == code
        )
        for code in companion_codes
    )
    # Two independent companion channels make a source code interpretation
    # auditable, rather than trusting a vendor-independent S-number alone.
    if companions < 2:
        return None
    return curve.metadata.original_mnemonic


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
        self.parameter_resolver = LasParameterResolver(self.catalog)

    def resolve_binding(
        self,
        dataset: Dataset,
        binding: ParameterBinding,
        semantic: DatasetParameterResolution | None = None,
    ) -> BindingResolution:
        if binding.source_mnemonic:
            curve = dataset.curve_by_mnemonic(binding.source_mnemonic)
            if curve is not None:
                return BindingResolution(
                    binding.binding_id,
                    binding.canonical_parameter_id,
                    curve.metadata.original_mnemonic,
                    "explicit",
                )

        canonical = binding.canonical_parameter_id.strip().upper()
        semantic = semantic or self.parameter_resolver.resolve_dataset(
            dataset, targets=(canonical,), minimum_confidence=0.65
        )
        if canonical in semantic.ambiguities:
            return BindingResolution(
                binding.binding_id,
                binding.canonical_parameter_id,
                None,
                "semantic_ambiguous",
            )
        semantic_match = semantic.get(canonical)
        if semantic_match is not None:
            return BindingResolution(
                binding.binding_id,
                binding.canonical_parameter_id,
                semantic_match.source_mnemonic,
                f"semantic_{semantic_match.matched_by}",
            )

        # GeoScape/GID LAS files encode parameter identity in S-series codes.
        # Use this fallback only after explicit/semantic mapping, and only when
        # companion channels corroborate the expected vendor family.
        geoscape_source = _geoscape_factory_source(dataset, canonical)
        if geoscape_source is not None:
            return BindingResolution(
                binding.binding_id,
                binding.canonical_parameter_id,
                geoscape_source,
                "geoscape_family",
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
            if (
                match is not None
                and normalize_sensor_key(match.definition.canonical_mnemonic) == wanted
            ):
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
        # Generic factory forms are dataset-driven: they must show the opened LAS
        # immediately instead of producing an empty tablet.
        materialized = materialize_form_for_dataset(form, dataset)
        if not materialized.compatible_axis:
            raise ValueError("В наборе данных нет оси, совместимой с выбранной формой")
        form = materialized.form
        semantic_targets = {
            binding.canonical_parameter_id.strip().upper()
            for column in form.columns
            for form_track in column.tracks
            for binding in form_track.bindings
            if binding.canonical_parameter_id.strip()
        }
        semantic = self.parameter_resolver.resolve_dataset(
            dataset, targets=semantic_targets, minimum_confidence=0.65
        )
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
                discrete_calcimetry = form_track.kind is TrackKind.CALCIMETRY
                for binding in form_track.bindings:
                    resolution = self.resolve_binding(dataset, binding, semantic)
                    resolutions.append(resolution)
                    if (
                        not binding.visible
                        or resolution.mnemonic is None
                        or discrete_calcimetry
                    ):
                        continue
                    resolved_mnemonics.append(resolution.mnemonic)
                    styles[resolution.mnemonic] = binding.style
                    display_settings[resolution.mnemonic] = CurveDisplaySettings(
                        display_name=binding.display_name,
                        x_scale=binding.x_scale,
                        x_min=binding.x_min,
                        x_max=binding.x_max,
                        unit_override=binding.unit or None,
                        header_text_color=binding.header_text_color,
                        header_line_color=binding.header_line_color,
                    )
                    if x_scale is None:
                        x_scale = binding.x_scale
                        x_min = binding.x_min
                        x_max = binding.x_max

                factory_vertical = (
                    form.origin is FormTemplateOrigin.FACTORY
                    and form_track.kind in COMPACT_TRACK_KINDS
                )
                is_lba = form_track.kind is TrackKind.LBA
                is_calcimetry = form_track.kind is TrackKind.CALCIMETRY
                tracks.append(
                    TrackDefinition(
                        track_id=form_track.track_id or new_id(),
                        title=form_track.title or column.title,
                        kind=form_track.kind,
                        group_title=column.group_title,
                        curve_mnemonics=resolved_mnemonics,
                        width=column.width,
                        visible=True,
                        # Factory/read-only protection belongs to the library document.
                        # Once applied, the tablet receives an editable working copy that
                        # can be customized and saved as a new user form.
                        locked=False,
                        x_scale=x_scale or XScale.LINEAR,
                        x_min=x_min,
                        x_max=x_max,
                        curve_styles=styles,
                        curve_display=display_settings,
                        grid_x=form_track.grid_x,
                        grid_y=form_track.grid_y,
                        grid_major_divisions=form_track.grid_major_divisions,
                        grid_minor_divisions=form_track.grid_minor_divisions,
                        grid_alpha=form_track.grid_alpha,
                        grid_print=form_track.grid_print,
                        show_x_scale=form_track.show_x_scale,
                        x_axis_label=form_track.x_axis_label,
                        title_orientation=(
                            "vertical_top_to_bottom"
                            if factory_vertical
                            else form_track.title_orientation
                        ),
                        title_position=form_track.title_position,
                        show_interval_labels=form_track.show_interval_labels,
                        lba_label_orientation=(
                            "vertical_top_to_bottom"
                            if is_lba
                            else form_track.lba_label_orientation
                        ),
                        calcimetry_label_orientation=(
                            "vertical_top_to_bottom"
                            if is_calcimetry
                            else form_track.calcimetry_label_orientation
                        ),
                        calcimetry_show_total=(
                            form_track.calcimetry_show_total
                            if form_track.calcimetry_show_total is not None
                            else any(
                                binding.visible
                                and binding.canonical_parameter_id.upper()
                                in TOTAL_CALCIMETRY_PARAMETERS
                                for binding in form_track.bindings
                            )
                            if is_calcimetry and form_track.bindings
                            else None
                        ),
                        show_description_borders=form_track.show_description_borders,
                        vertical_ruler=form_track.vertical_ruler,
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
            TabletLayout(
                tracks=tracks,
                vertical_index_id=preferred.index_id,
                annotation_scope_id=f"dataset:{dataset.dataset_id}:form:{form.form_id}",
                visible_depth_top=form.visible_axis_top,
                visible_depth_bottom=form.visible_axis_bottom,
                localize_factory_labels=form.origin is FormTemplateOrigin.FACTORY,
            ),
            resolutions,
        )
