from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

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
    *,
    name_resolver: Callable[[CatalogLithotype], str] | None = None,
    unknown_name: str = "Неизвестный литотип",
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
                    interval.description or unknown_name,
                    "#b0b0b0",
                    "solid",
                )
            )
            continue
        result.append(
            LithologyLegendEntry(
                definition.lithotype_id,
                definition.code,
                name_resolver(definition) if name_resolver is not None else definition.name_ru,
                definition.color,
                definition.pattern_key,
            )
        )
    return tuple(result)
