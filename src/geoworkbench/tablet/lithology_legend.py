from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from geoworkbench.domain.models import LithologyInterval
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype


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
    """Build a depth-ordered legend for lithotypes used on the tablet."""

    unknown_descriptions = {
        interval.lithotype_id: interval.description
        for interval in intervals
        if interval.description
    }
    return build_lithology_legend_from_ids(
        (interval.lithotype_id for interval in intervals),
        catalog,
        name_resolver=name_resolver,
        unknown_name=unknown_name,
        unknown_descriptions=unknown_descriptions,
    )


def build_lithology_legend_from_ids(
    lithotype_ids: Iterable[str],
    catalog: Iterable[CatalogLithotype],
    *,
    name_resolver: Callable[[CatalogLithotype], str] | None = None,
    unknown_name: str = "Неизвестный литотип",
    unknown_descriptions: Mapping[str, str] | None = None,
) -> tuple[LithologyLegendEntry, ...]:
    """Resolve an ordered ID stream into one deterministic legend contract.

    Both the screen legend and Masterlog use this function.  Selection of the
    relevant IDs remains surface-specific, while labels, colours, patterns,
    unknown fallback behaviour, and duplicate removal are shared.
    """

    definitions = {item.lithotype_id: item for item in catalog}
    descriptions = dict(unknown_descriptions or {})
    result: list[LithologyLegendEntry] = []
    seen: set[str] = set()
    for raw_id in lithotype_ids:
        lithotype_id = str(raw_id)
        if lithotype_id in seen:
            continue
        seen.add(lithotype_id)
        definition = definitions.get(lithotype_id)
        if definition is None:
            result.append(
                LithologyLegendEntry(
                    lithotype_id,
                    lithotype_id,
                    descriptions.get(lithotype_id) or unknown_name,
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
