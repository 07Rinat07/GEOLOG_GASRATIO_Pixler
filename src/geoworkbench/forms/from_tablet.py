from __future__ import annotations

from geoworkbench.domain.models import Dataset, IndexRole
from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.parameter_labels import localized_curve_name
from geoworkbench.tablet.models import CurveStyle, TabletLayout


def form_from_tablet_layout(
    layout: TabletLayout,
    dataset: Dataset,
    name: str,
    *,
    description: str = "",
    language: AppLanguage = AppLanguage.RU,
) -> FormDocument:
    """Create an editable user form from the current live tablet layout.

    The conversion preserves column order, widths, captions, curve styles,
    ranges, grids and title presentation. Source mnemonics remain explicit so
    reopening the form against the same or a compatible LAS resolves quickly.
    """

    index = (
        dataset.indexes.get(layout.vertical_index_id)
        if layout.vertical_index_id is not None
        else dataset.active_index
    )
    if index is None:
        index = dataset.active_index
    axis_kind = FormAxisKind.TIME if index.role is IndexRole.TIME else FormAxisKind.DEPTH
    form = FormDocument.create(name.strip(), axis_kind, description=description)

    for live_track in layout.tracks:
        bindings: list[ParameterBinding] = []
        for mnemonic in live_track.curve_mnemonics:
            curve = dataset.curve_by_mnemonic(mnemonic)
            display = live_track.curve_display_settings(mnemonic)
            style = live_track.curve_style(mnemonic) or CurveStyle()
            unit = ""
            canonical = mnemonic
            if curve is not None:
                unit = (curve.metadata.unit or "").strip()
                canonical = (
                    curve.metadata.canonical_mnemonic
                    or curve.metadata.original_mnemonic
                    or mnemonic
                )
            friendly_name = localized_curve_name(
                canonical,
                description=(curve.metadata.description or "") if curve is not None else "",
                unit=unit,
                language=language,
                configured=display.display_name,
            )
            bindings.append(
                ParameterBinding.create(
                    canonical_parameter_id=canonical,
                    display_name=friendly_name or mnemonic,
                    source_mnemonic=mnemonic,
                    unit=unit,
                    style=style,
                    x_scale=display.x_scale,
                    x_min=display.x_min,
                    x_max=display.x_max,
                )
            )

        track = FormTrack.create(
            live_track.title,
            live_track.kind,
            bindings=bindings,
            visible=live_track.visible,
            locked=False,
            grid_x=live_track.grid_x,
            grid_y=live_track.grid_y,
            grid_alpha=live_track.grid_alpha,
            x_axis_label=live_track.x_axis_label,
            title_orientation=live_track.title_orientation,
            title_position=live_track.title_position,
            show_interval_labels=live_track.show_interval_labels,
        )
        # Preserve the stable live identifier when possible so later edits and
        # Masterlog linking can track the same logical column.
        track.track_id = live_track.track_id
        column = FormColumn.create(
            live_track.title,
            group_title=live_track.group_title,
            width=live_track.width,
            visible=live_track.visible,
            locked=False,
            tracks=[track],
            title_orientation=live_track.title_orientation,
            title_position=live_track.title_position,
        )
        form.add_column(column)
    form.validate()
    return form
