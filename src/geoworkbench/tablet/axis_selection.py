from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset, DatasetIndex, IndexRole, IndexType


@dataclass(frozen=True, slots=True)
class VerticalAxisResolution:
    """Result of reconciling a saved form axis with the current dataset.

    ``replace_layout_index`` is true only when the saved identifier is stale,
    incompatible with a vertical axis, or an old GeoScape relative-time axis
    must be migrated to the companion calendar-time index.
    """

    index: DatasetIndex | None
    replace_layout_index: bool = False
    calendar_time_preferred: bool = False


def dataset_has_absolute_calendar_time(dataset: Dataset) -> bool:
    """Return whether import provenance proves that calendar timestamps exist."""

    representation = dataset.parameters.get("PARADOX_TIME_REPRESENTATION", "").casefold()
    source_format = dataset.parameters.get("SOURCE_FORMAT", "").casefold()
    return representation.startswith(("ole-", "unix-")) or (
        "geoscape" in source_format
        and any(
            index.index_type is IndexType.DATETIME
            for index in dataset.indexes.values()
        )
    )


def resolve_vertical_axis(
    dataset: Dataset,
    requested_index_id: str | None,
    *,
    prefer_calendar_time: bool,
) -> VerticalAxisResolution:
    """Resolve a safe depth/time axis for a dataset and saved form layout.

    A form may retain an index id from the previously displayed dataset.  Such
    an id must never be dereferenced without checking membership in the new
    dataset.  The fallback order is:

    1. requested depth/time index when it exists;
    2. active dataset depth/time index;
    3. first available depth/time index;
    4. no axis.

    For absolute GeoScape/Paradox time sources, an old relative TIME selection
    is upgraded to the highest-confidence DATETIME index with matching rows.
    Explicit depth selections are preserved.
    """

    requested = (
        dataset.indexes.get(requested_index_id)
        if requested_index_id
        else None
    )
    requested_is_vertical = requested is not None and requested.role in {
        IndexRole.DEPTH,
        IndexRole.TIME,
    }
    saved_request_is_invalid = requested_index_id is not None and not requested_is_vertical

    selected = requested if requested_is_vertical else None
    if selected is None:
        try:
            active = dataset.active_index
        except RuntimeError:
            active = None
        if active is not None and active.role in {IndexRole.DEPTH, IndexRole.TIME}:
            selected = active

    if selected is None:
        selected = next(
            (
                index
                for index in dataset.indexes.values()
                if index.role in {IndexRole.DEPTH, IndexRole.TIME}
            ),
            None,
        )

    if selected is None:
        return VerticalAxisResolution(index=None)

    if (
        prefer_calendar_time
        and selected.role is IndexRole.TIME
        and selected.index_type is not IndexType.DATETIME
    ):
        candidates = [
            index
            for index in dataset.indexes.values()
            if index.role is IndexRole.TIME
            and index.index_type is IndexType.DATETIME
            and index.values.shape == selected.values.shape
        ]
        if candidates:
            preferred = max(candidates, key=lambda item: item.confidence)
            return VerticalAxisResolution(
                index=preferred,
                replace_layout_index=preferred.index_id != requested_index_id,
                calendar_time_preferred=True,
            )

    return VerticalAxisResolution(
        index=selected,
        replace_layout_index=(
            saved_request_is_invalid and selected.index_id != requested_index_id
        ),
    )
