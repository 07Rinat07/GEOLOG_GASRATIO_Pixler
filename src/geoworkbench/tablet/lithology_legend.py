from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import LithologyInterval
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype


@dataclass(frozen=True, slots=True)
class LithologyLegendEntry:
    lithotype_id: str
    code: str
    name: str
    color: str
    pattern_key: str


def build_lithology_legend(
    intervals: list[LithologyInterval] | tuple[LithologyInterval, ...],
    catalog: tuple[CatalogLithotype, ...],
) -> tuple[LithologyLegendEntry, ...]:
    definitions = {item.lithotype_id: item for item in catalog}
    result: list[LithologyLegendEntry] = []
    seen: set[str] = set()
    for interval in intervals:
        if interval.lithotype_id in seen:
            continue
        seen.add(interval.lithotype_id)
        definition = definitions.get(interval.lithotype_id)
        if definition is None:
            result.append(
                LithologyLegendEntry(
                    interval.lithotype_id,
                    interval.lithotype_id,
                    interval.description or "Неизвестный литотип",
                    "#b0b0b0",
                    "solid",
                )
            )
            continue
        result.append(
            LithologyLegendEntry(
                definition.lithotype_id,
                definition.code,
                definition.name_ru,
                definition.color,
                definition.pattern_key,
            )
        )
    return tuple(result)
