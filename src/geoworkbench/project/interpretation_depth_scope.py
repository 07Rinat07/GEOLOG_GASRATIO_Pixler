from __future__ import annotations

from dataclasses import replace

from geoworkbench.domain.depth_interval import DepthInterval, scope_dataset
from geoworkbench.project.session import ProjectSession


def scope_interpretation_session(
    session: ProjectSession, interval: DepthInterval
) -> ProjectSession:
    """Build an isolated analysis view, including matching geology and manual context."""
    dataset = session.current_dataset
    well = session.current_well
    if dataset is None or well is None:
        raise RuntimeError("Для расчёта выберите набор данных скважины")
    selected = scope_dataset(dataset, interval)

    def overlaps(top: float, bottom: float) -> bool:
        return bottom >= interval.top_depth and top <= interval.bottom_depth

    scoped_well = replace(
        well,
        datasets={**well.datasets, dataset.dataset_id: selected},
        cuttings=[
            replace(
                item,
                top_depth=max(item.top_depth, interval.top_depth),
                bottom_depth=min(item.bottom_depth, interval.bottom_depth),
            )
            for item in well.cuttings
            if overlaps(item.top_depth, item.bottom_depth)
        ],
        lithology=[
            replace(
                item,
                top_depth=max(item.top_depth, interval.top_depth),
                bottom_depth=min(item.bottom_depth, interval.bottom_depth),
            )
            for item in well.lithology
            if overlaps(item.top_depth, item.bottom_depth)
        ],
        stratigraphy=[
            replace(
                item,
                top_depth=max(item.top_depth, interval.top_depth),
                bottom_depth=min(item.bottom_depth, interval.bottom_depth),
            )
            for item in well.stratigraphy
            if overlaps(item.top_depth, item.bottom_depth)
        ],
        interpretations={
            key: replace(
                item,
                intervals=[
                    replace(
                        record,
                        top_depth=max(record.top_depth, interval.top_depth),
                        bottom_depth=min(record.bottom_depth, interval.bottom_depth),
                    )
                    for record in item.intervals
                    if overlaps(record.top_depth, record.bottom_depth)
                ],
            )
            for key, item in well.interpretations.items()
        },
        gas_context_events=[
            replace(
                item,
                top_depth=max(item.top_depth, interval.top_depth),
                bottom_depth=min(item.bottom_depth, interval.bottom_depth),
            )
            for item in well.gas_context_events
            if overlaps(item.top_depth, item.bottom_depth)
        ],
    )
    return replace(
        session,
        project=replace(
            session.project, wells={**session.project.wells, well.well_id: scoped_well}
        ),
        dirty=False,
    )
