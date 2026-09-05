"""Import coded LAS geology without guessing the geological meaning of a code.

Source-code entries live in the existing project lithotype catalog. Their stable
IDs keep imported intervals linked when a geologist edits names and symbols.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import (
    CuttingsComponent,
    CuttingsSample,
    LithologyInterval,
    ProjectLithotype,
    new_id,
)
from geoworkbench.services.rock_code_dictionary import (
    apply_dictionary,
    dictionary_from_las_bytes,
)

if TYPE_CHECKING:
    from geoworkbench.project.session import ProjectSession


_UNKNOWN_PATTERNS = (
    "dots", "dense_dots", "sand_dots", "clay_dash", "silt_dash",
    "gravel_circles", "conglomerate", "carbonate", "evaporite", "coal",
    "metamorphic", "volcanic",
)
_UNKNOWN_COLORS = (
    "#d1d5db", "#cbd5e1", "#e5e7eb", "#d6d3d1", "#c7d2fe",
    "#ddd6fe", "#bfdbfe", "#bae6fd", "#a7f3d0", "#fde68a",
    "#fed7aa", "#fecaca",
)


@dataclass(frozen=True, slots=True)
class LasGeologyResult:
    lithology_intervals: int = 0
    cuttings_intervals: int = 0
    unconfigured_codes: tuple[int, ...] = ()
    invalid_composition_rows: int = 0


def las_code_id(code: int) -> str:
    if isinstance(code, bool) or not isinstance(code, int) or not 1 <= code <= 999999:
        raise ValueError("LAS rock code must be an integer from 1 to 999999")
    return f"las-code-{code}"


def unmapped_las_lithotype(code: int) -> ProjectLithotype:
    """Build the editable neutral catalog record for one LAS source code."""

    identity = las_code_id(code)
    return ProjectLithotype(
        identity,
        str(code),
        f"Неопознанная порода, код {code}",
        f"Unidentified rock, code {code}",
        "LAS: unmapped",
        _UNKNOWN_COLORS[(code - 1) % len(_UNKNOWN_COLORS)],
        _UNKNOWN_PATTERNS[(code - 1) % len(_UNKNOWN_PATTERNS)],
        f"Анықталмаған жыныс, код {code}",
    )


def _code(value: float) -> int | None:
    if not np.isfinite(value) or value != int(value) or not 1 <= value <= 999999:
        return None
    return int(value)


def import_las_geology(session: ProjectSession) -> LasGeologyResult:
    """Read coded geology and populate empty well layers without overwriting LAS.

    Only exact coded-geology channels are accepted. Invalid/non-monotonic axes and
    ambiguous duplicate channels are not interpreted. Percentages are not normalized.
    Existing lithology and cuttings layers are scanned for source codes, but remain
    unchanged so the catalog tab can be refreshed safely at any time.
    """
    dataset, well = session.current_dataset, session.current_well
    if dataset is None or well is None:
        return LasGeologyResult()
    source_document = session.source_documents.get(dataset.dataset_id)
    if source_document is not None:
        embedded = dictionary_from_las_bytes(source_document.raw_bytes)
        if embedded is not None:
            apply_dictionary(session, embedded, overwrite=False)
    if not any("ПОРОД" in c.metadata.original_mnemonic.upper() for c in dataset.curves.values()):
        return LasGeologyResult()
    depth = np.asarray(dataset.depth, dtype=float)
    if depth.size < 2 or not np.all(np.isfinite(depth)):
        return LasGeologyResult()
    differences = np.diff(depth)
    reverse = bool(np.all(differences < 0))
    if not reverse and not np.all(differences > 0):
        return LasGeologyResult()
    if reverse:
        depth = depth[::-1]

    def values(name: str) -> NDArray[np.float64] | None:
        matches = [c for c in dataset.curves.values()
                   if c.metadata.original_mnemonic.upper().replace(" ", "_") == name]
        if len(matches) != 1:
            return None
        array = np.asarray(matches[0].values, dtype=float)
        if array.shape != depth.shape:
            return None
        return array[::-1] if reverse else array

    primary = values("КОД_ПОРОДЫ")
    slots = [(values(f"ПОРОДА{i}_КОД"), values(f"ПОРОДА{i}_КОЛИЧ")) for i in range(1, 6)]
    edges = np.concatenate(([depth[0]], (depth[:-1] + depth[1:]) / 2, [depth[-1]]))
    typical_step = float(np.median(np.diff(depth)))
    codes: set[int] = set()
    lithology: list[LithologyInterval] = []
    cuttings: list[CuttingsSample] = []
    invalid_rows = 0
    populate_lithology = not well.lithology
    populate_cuttings = not well.cuttings
    for i in range(depth.size):
        # Do not extend sampled geology through a missing depth run.
        top = float(edges[i] if i == 0 or depth[i] - depth[i-1] <= typical_step * 3 else depth[i])
        bottom = float(edges[i+1] if i == depth.size-1 or depth[i+1] - depth[i] <= typical_step * 3 else depth[i])
        if bottom <= top:
            continue
        rock = _code(float(primary[i])) if primary is not None else None
        if rock is not None:
            codes.add(rock)
            if populate_lithology:
                identity = las_code_id(rock)
                if lithology and lithology[-1].lithotype_id == identity and lithology[-1].bottom_depth == top:
                    lithology[-1].bottom_depth = bottom
                else:
                    lithology.append(LithologyInterval(new_id(), top, bottom, identity))
        composition: dict[int, float] = {}
        valid = True
        for code_values, amounts in slots:
            if code_values is None and amounts is None:
                continue
            if code_values is None or amounts is None:
                valid = False
                break
            amount = float(amounts[i])
            if amount == 0:
                continue
            code = _code(float(code_values[i]))
            if code is None or not np.isfinite(amount) or not 0 < amount <= 100:
                valid = False
                break
            composition[code] = composition.get(code, 0.0) + amount
        if not valid or (composition and abs(sum(composition.values()) - 100) > 1e-6):
            invalid_rows += 1
            continue
        if not composition:
            continue
        codes.update(composition)
        if not populate_cuttings:
            continue
        components = [CuttingsComponent(las_code_id(code), amount) for code, amount in sorted(composition.items())]
        if cuttings and cuttings[-1].components == components and cuttings[-1].bottom_depth == top:
            cuttings[-1].bottom_depth = bottom
        else:
            cuttings.append(CuttingsSample(new_id(), top, bottom, components))
    unknown: list[int] = []
    catalog_changed = False
    for code in sorted(codes):
        identity = las_code_id(code)
        if identity not in session.project.lithotypes:
            session.project.lithotypes[identity] = unmapped_las_lithotype(code)
            catalog_changed = True
        if session.project.lithotypes[identity].category == "LAS: unmapped":
            unknown.append(code)
    well.lithology.extend(lithology)
    well.cuttings.extend(cuttings)
    if lithology or cuttings:
        well.content_revision += 1
    if lithology or cuttings or catalog_changed:
        session.dirty = True
    return LasGeologyResult(len(lithology), len(cuttings), tuple(unknown), invalid_rows)


def dataset_with_well_geology(session: ProjectSession):
    """Return an export-only dataset containing the current well geology.

    Manual lithology and cuttings are project data, not source LAS curves.  A
    normal LAS export should nevertheless carry them in the same coded channels
    understood by :func:`import_las_geology`.  The source dataset is copied so
    exporting never mutates the open LAS or adds derived curves to the project.
    """

    dataset, well = session.current_dataset, session.current_well
    if dataset is None or well is None or (not well.lithology and not well.cuttings):
        return dataset

    exported = deepcopy(dataset)
    depth = np.asarray(exported.active_index.values, dtype=np.float64)
    if depth.ndim != 1 or not depth.size:
        return exported

    if well.lithology:
        primary = np.full(depth.shape, np.nan, dtype=np.float64)
        for index, value in enumerate(depth):
            interval = _lithology_interval_at(well.lithology, float(value))
            if interval is None:
                continue
            code = _project_lithotype_code(session, interval.lithotype_id)
            if code is not None:
                primary[index] = code
        if np.isfinite(primary).any():
            exported.upsert_curve(
                "КОД_ПОРОДЫ",
                primary,
                description="Primary lithology source code",
                provenance="derived:project-geology",
            )

    if well.cuttings:
        code_columns = [np.full(depth.shape, np.nan, dtype=np.float64) for _ in range(5)]
        amount_columns = [np.full(depth.shape, np.nan, dtype=np.float64) for _ in range(5)]
        for index, value in enumerate(depth):
            sample = _cuttings_sample_at(well.cuttings, float(value))
            if sample is None:
                continue
            components: list[tuple[int, float]] = []
            for component in sample.components:
                code = _project_lithotype_code(session, component.lithotype_id)
                percentage = float(component.percentage)
                if code is None or not np.isfinite(percentage) or not 0 < percentage <= 100:
                    continue
                components.append((code, percentage))
            components.sort(key=lambda item: (-item[1], item[0]))
            for slot, (code, percentage) in enumerate(components[:5]):
                code_columns[slot][index] = code
                amount_columns[slot][index] = percentage
        if any(np.isfinite(column).any() for column in code_columns):
            for slot, (codes, amounts) in enumerate(zip(code_columns, amount_columns), start=1):
                exported.upsert_curve(
                    f"ПОРОДА{slot}_КОД",
                    codes,
                    description=f"Cuttings component {slot} rock code",
                    provenance="derived:project-geology",
                )
                exported.upsert_curve(
                    f"ПОРОДА{slot}_КОЛИЧ",
                    amounts,
                    description=f"Cuttings component {slot} percentage",
                    provenance="derived:project-geology",
                )
    return exported


def _lithology_interval_at(
    intervals: list[LithologyInterval],
    depth: float,
) -> LithologyInterval | None:
    """Find the first interval containing a sampled depth, including endpoints."""

    for interval in intervals:
        top = min(float(interval.top_depth), float(interval.bottom_depth))
        bottom = max(float(interval.top_depth), float(interval.bottom_depth))
        if top <= depth <= bottom:
            return interval
    return None


def _cuttings_sample_at(
    samples: list[CuttingsSample],
    depth: float,
) -> CuttingsSample | None:
    for sample in samples:
        top = min(float(sample.top_depth), float(sample.bottom_depth))
        bottom = max(float(sample.top_depth), float(sample.bottom_depth))
        if top <= depth <= bottom:
            return sample
    return None


def _project_lithotype_code(session: ProjectSession, lithotype_id: str) -> int | None:
    record = session.project.lithotypes.get(lithotype_id)
    if record is None:
        return None
    try:
        code = int(record.code)
    except (TypeError, ValueError):
        return None
    if 1 <= code <= 999999:
        return code
    return None
