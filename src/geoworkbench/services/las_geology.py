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
    StratigraphyInterval,
    new_id,
)
from geoworkbench.services.las_geology_dialect import (
    GeologyChannelRole,
    resolve_geology_channel,
)
from geoworkbench.services.las_geology_metadata import (
    LasGeologyMetadata,
    geology_metadata_from_las_bytes,
)
from geoworkbench.services.lba_standard import (
    lba_color_code,
    lba_standard_group,
    lba_standard_type,
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
    stratigraphy_intervals: int = 0


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
    """Materialize portable LAS geology into empty well layers.

    Coded lithology/cuttings remain the primary compatibility contract. Optional
    calcimetry, LBA and stratigraphy channels enrich the same samples when present.
    Portable metadata is advisory and bounded; malformed metadata is ignored so it
    can never make an otherwise readable LAS fail to open.
    """

    dataset, well = session.current_dataset, session.current_well
    if dataset is None or well is None:
        return LasGeologyResult()

    source_document = session.source_documents.get(dataset.dataset_id)
    metadata: LasGeologyMetadata | None = None
    if source_document is not None:
        embedded = dictionary_from_las_bytes(source_document.raw_bytes)
        if embedded is not None:
            apply_dictionary(session, embedded, overwrite=False)
        metadata = geology_metadata_from_las_bytes(source_document.raw_bytes)

    geology_curves: dict[
        tuple[GeologyChannelRole, int | None],
        list[object],
    ] = {}
    for curve in dataset.curves.values():
        match = resolve_geology_channel(
            curve.metadata.original_mnemonic,
            description=curve.metadata.description or "",
            unit=curve.metadata.unit or "",
        )
        if match is None:
            continue
        geology_curves.setdefault((match.role, match.slot), []).append(curve)

    if not geology_curves and metadata is None:
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

    def values_for(
        role: GeologyChannelRole,
        *,
        slot: int | None = None,
    ) -> NDArray[np.float64] | None:
        matches = geology_curves.get((role, slot), [])
        if len(matches) != 1:
            return None
        curve = matches[0]
        array = np.asarray(curve.values, dtype=float)
        if array.shape != depth.shape:
            return None
        return array[::-1] if reverse else array

    primary = values_for(GeologyChannelRole.PRIMARY_LITHOLOGY)
    slots = [
        (
            values_for(GeologyChannelRole.CUTTINGS_CODE, slot=i),
            values_for(GeologyChannelRole.CUTTINGS_AMOUNT, slot=i),
        )
        for i in range(1, 6)
    ]
    calcite_values = values_for(GeologyChannelRole.CALCITE)
    legacy_carbonate_values = values_for(GeologyChannelRole.LEGACY_CARBONATE)
    if calcite_values is None:
        # Legacy single-channel carbonate data is surfaced through the existing
        # calcimetry field without fabricating a dolomite split.
        calcite_values = legacy_carbonate_values
    dolomite_values = values_for(GeologyChannelRole.DOLOMITE)
    lba_group_values = values_for(GeologyChannelRole.LBA_GROUP)
    lba_intensity_values = values_for(GeologyChannelRole.LBA_INTENSITY)
    lba_type_values = values_for(GeologyChannelRole.LBA_TYPE)
    lba_color_values = values_for(GeologyChannelRole.LBA_COLOR)
    description_values = values_for(GeologyChannelRole.DESCRIPTION_ID)
    stratigraphy_values = values_for(GeologyChannelRole.STRATIGRAPHY_CODE)

    edges = np.concatenate(
        ([depth[0]], (depth[:-1] + depth[1:]) / 2, [depth[-1]])
    )
    typical_step = float(np.median(np.diff(depth)))
    codes: set[int] = set()
    lithology: list[LithologyInterval] = []
    cuttings: list[CuttingsSample] = []
    invalid_rows = 0
    populate_lithology = not well.lithology
    populate_cuttings = not well.cuttings

    for index in range(depth.size):
        # Do not extend sampled geology through a missing depth run.
        top = float(
            edges[index]
            if index == 0 or depth[index] - depth[index - 1] <= typical_step * 3
            else depth[index]
        )
        bottom = float(
            edges[index + 1]
            if index == depth.size - 1
            or depth[index + 1] - depth[index] <= typical_step * 3
            else depth[index]
        )
        if bottom <= top:
            continue

        description_id = (
            _code(float(description_values[index]))
            if description_values is not None
            else None
        )
        description = (
            metadata.description(description_id)
            if metadata is not None
            else None
        )

        rock = _code(float(primary[index])) if primary is not None else None
        if rock is not None:
            codes.add(rock)
            if populate_lithology:
                identity = las_code_id(rock)
                if (
                    lithology
                    and lithology[-1].lithotype_id == identity
                    and lithology[-1].description == description
                    and lithology[-1].bottom_depth == top
                ):
                    lithology[-1].bottom_depth = bottom
                else:
                    lithology.append(
                        LithologyInterval(
                            new_id(),
                            top,
                            bottom,
                            identity,
                            description=description,
                        )
                    )

        composition: dict[int, float] = {}
        valid_composition = True
        for code_values, amounts in slots:
            if code_values is None and amounts is None:
                continue
            if code_values is None or amounts is None:
                valid_composition = False
                break
            amount = float(amounts[index])
            if amount == 0:
                continue
            code = _code(float(code_values[index]))
            if code is None or not np.isfinite(amount) or not 0 < amount <= 100:
                valid_composition = False
                break
            composition[code] = composition.get(code, 0.0) + amount
        if not valid_composition or (
            composition and abs(sum(composition.values()) - 100) > 1e-6
        ):
            invalid_rows += 1
            composition = {}

        calcite = (
            _percentage(float(calcite_values[index]))
            if calcite_values is not None
            else None
        )
        dolomite = (
            _percentage(float(dolomite_values[index]))
            if dolomite_values is not None
            else None
        )
        if (
            calcite is not None
            and dolomite is not None
            and calcite + dolomite > 100.0 + 1e-6
        ):
            calcite = None
            dolomite = None

        lba_group = (
            _bounded_integer(float(lba_group_values[index]), 1, 5)
            if lba_group_values is not None
            else None
        )
        lba_intensity = (
            _bounded_integer(float(lba_intensity_values[index]), 1, 5)
            if lba_intensity_values is not None
            else None
        )
        lba_type_code = (
            _code(float(lba_type_values[index]))
            if lba_type_values is not None
            else None
        )
        lba_color_code = (
            _code(float(lba_color_values[index]))
            if lba_color_values is not None
            else None
        )
        metadata_type = (
            metadata.lba_type(lba_type_code)
            if metadata is not None
            else None
        )
        standard = lba_standard_type(metadata_type) if metadata_type else None
        if standard is None:
            standard = lba_standard_group(lba_group)
        if standard is not None and lba_group is None:
            lba_group = standard.group
        lba_type_id = standard.type_id if standard is not None else None
        lba_color = (
            metadata.lba_color(lba_color_code)
            if metadata is not None
            else None
        )

        if composition:
            codes.update(composition)
        has_sample_payload = bool(composition) or any(
            value is not None
            for value in (
                calcite,
                dolomite,
                lba_group,
                lba_type_id,
                lba_intensity,
                lba_color,
                description,
            )
        )
        if not has_sample_payload or not populate_cuttings:
            continue

        components = [
            CuttingsComponent(las_code_id(code), amount)
            for code, amount in sorted(composition.items())
        ]
        sample = CuttingsSample(
            new_id(),
            top,
            bottom,
            components,
            lba_group=lba_group,
            lba_type_id=lba_type_id,
            lba_intensity=lba_intensity,
            lba_color=lba_color,
            calcite_percent=calcite,
            dolomite_percent=dolomite,
            description=description,
        )
        if (
            cuttings
            and cuttings[-1].bottom_depth == top
            and _same_cuttings_payload(cuttings[-1], sample)
        ):
            cuttings[-1].bottom_depth = bottom
        else:
            cuttings.append(sample)

    unknown: list[int] = []
    catalog_changed = False
    for code in sorted(codes):
        identity = las_code_id(code)
        if identity not in session.project.lithotypes:
            session.project.lithotypes[identity] = unmapped_las_lithotype(code)
            catalog_changed = True
        if session.project.lithotypes[identity].category == "LAS: unmapped":
            unknown.append(code)

    stratigraphy: list[StratigraphyInterval] = []
    if not well.stratigraphy and stratigraphy_values is not None:
        if metadata is not None:
            stratigraphy = _stratigraphy_from_metadata(metadata, depth)
        if not stratigraphy:
            stratigraphy = _stratigraphy_from_codes(
                depth,
                edges,
                stratigraphy_values,
                typical_step,
            )

    well.lithology.extend(lithology)
    well.cuttings.extend(cuttings)
    well.stratigraphy.extend(stratigraphy)
    if lithology or cuttings or stratigraphy:
        well.content_revision += 1
    if lithology or cuttings or stratigraphy or catalog_changed:
        session.dirty = True
    return LasGeologyResult(
        lithology_intervals=len(lithology),
        cuttings_intervals=len(cuttings),
        unconfigured_codes=tuple(unknown),
        invalid_composition_rows=invalid_rows,
        stratigraphy_intervals=len(stratigraphy),
    )


def _percentage(value: float) -> float | None:
    if not np.isfinite(value) or not 0.0 <= value <= 100.0:
        return None
    return value


def _bounded_integer(value: float, minimum: int, maximum: int) -> int | None:
    if (
        not np.isfinite(value)
        or value != int(value)
        or not minimum <= int(value) <= maximum
    ):
        return None
    return int(value)


def _same_cuttings_payload(left: CuttingsSample, right: CuttingsSample) -> bool:
    return (
        left.components == right.components
        and left.lba_group == right.lba_group
        and left.lba_type_id == right.lba_type_id
        and left.lba_intensity == right.lba_intensity
        and left.lba_color == right.lba_color
        and left.calcite_percent == right.calcite_percent
        and left.dolomite_percent == right.dolomite_percent
        and left.description == right.description
    )


def _stratigraphy_from_metadata(
    metadata: LasGeologyMetadata,
    depth: NDArray[np.float64],
) -> list[StratigraphyInterval]:
    start = float(depth[0])
    stop = float(depth[-1])
    result: list[StratigraphyInterval] = []
    for entry in metadata.stratigraphy:
        top = max(start, float(entry.top_depth))
        bottom = min(stop, float(entry.bottom_depth))
        if bottom <= top:
            continue
        result.append(
            StratigraphyInterval(
                new_id(),
                top,
                bottom,
                entry.code,
                name=entry.name_ru,
                rank=entry.rank,
                color=entry.color or "#dbeafe",
                description=entry.description_ru,
            )
        )
    return result


def _stratigraphy_from_codes(
    depth: NDArray[np.float64],
    edges: NDArray[np.float64],
    values: NDArray[np.float64],
    typical_step: float,
) -> list[StratigraphyInterval]:
    result: list[StratigraphyInterval] = []
    for index, raw in enumerate(values):
        code = _code(float(raw))
        if code is None:
            continue
        top = float(
            edges[index]
            if index == 0 or depth[index] - depth[index - 1] <= typical_step * 3
            else depth[index]
        )
        bottom = float(
            edges[index + 1]
            if index == depth.size - 1
            or depth[index + 1] - depth[index] <= typical_step * 3
            else depth[index]
        )
        if bottom <= top:
            continue
        code_text = str(code)
        if (
            result
            and result[-1].code == code_text
            and result[-1].bottom_depth == top
        ):
            result[-1].bottom_depth = bottom
        else:
            result.append(
                StratigraphyInterval(
                    new_id(),
                    top,
                    bottom,
                    code_text,
                )
            )
    return result

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
        def source_curve_for_role(role: GeologyChannelRole):
            matches = []
            for existing in exported.curves.values():
                match = resolve_geology_channel(
                    existing.metadata.original_mnemonic,
                    description=existing.metadata.description or "",
                    unit=existing.metadata.unit or "",
                )
                if match is not None and match.role is role and match.slot is None:
                    matches.append(existing)
            return matches[0] if len(matches) == 1 else None

        def source_values_for_role(role: GeologyChannelRole) -> NDArray[np.float64]:
            existing = source_curve_for_role(role)
            if existing is None:
                return np.full(depth.shape, np.nan, dtype=np.float64)
            values = np.asarray(existing.values, dtype=np.float64)
            if values.shape != depth.shape:
                return np.full(depth.shape, np.nan, dtype=np.float64)
            return values.copy()

        calcite_source_role = (
            GeologyChannelRole.CALCITE
            if source_curve_for_role(GeologyChannelRole.CALCITE) is not None
            else GeologyChannelRole.LEGACY_CARBONATE
        )
        calcite_column = source_values_for_role(calcite_source_role)
        dolomite_column = source_values_for_role(GeologyChannelRole.DOLOMITE)
        lba_group_column = source_values_for_role(GeologyChannelRole.LBA_GROUP)
        lba_intensity_column = source_values_for_role(GeologyChannelRole.LBA_INTENSITY)
        lba_type_column = source_values_for_role(GeologyChannelRole.LBA_TYPE)
        lba_color_column = source_values_for_role(GeologyChannelRole.LBA_COLOR)

        source_document = session.source_documents.get(dataset.dataset_id)
        export_metadata = (
            geology_metadata_from_las_bytes(source_document.raw_bytes)
            if source_document is not None
            else None
        )
        lba_type_code_by_type: dict[str, int] = {}
        lba_color_code_by_label: dict[str, int] = {}
        if export_metadata is not None:
            for code, label in export_metadata.lba_type_codes.items():
                standard = lba_standard_type(label)
                if standard is not None:
                    lba_type_code_by_type.setdefault(standard.type_id, code)
            for code, label in export_metadata.lba_color_codes.items():
                normalized = lba_color_code(label)
                if normalized:
                    lba_color_code_by_label.setdefault(normalized, code)

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

            if sample.calcite_percent is not None:
                calcite_column[index] = float(sample.calcite_percent)
            if sample.dolomite_percent is not None:
                dolomite_column[index] = float(sample.dolomite_percent)
            if sample.lba_group is not None:
                lba_group_column[index] = float(sample.lba_group)
            if sample.lba_intensity is not None:
                lba_intensity_column[index] = float(sample.lba_intensity)
            if sample.lba_type_id:
                standard = lba_standard_type(sample.lba_type_id)
                if standard is not None:
                    code = lba_type_code_by_type.get(standard.type_id)
                    if code is not None:
                        lba_type_column[index] = float(code)
            if sample.lba_color:
                code = lba_color_code_by_label.get(lba_color_code(sample.lba_color))
                if code is not None:
                    lba_color_column[index] = float(code)

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

        def upsert_geology_curve(
            role: GeologyChannelRole,
            fallback: str,
            values: NDArray[np.float64],
            *,
            unit: str,
            description: str,
        ) -> None:
            if not np.isfinite(values).any():
                return
            existing = source_curve_for_role(role)
            mnemonic = (
                existing.metadata.original_mnemonic
                if existing is not None
                else fallback
            )
            exported.upsert_curve(
                mnemonic,
                values,
                unit=unit,
                description=description,
                provenance="derived:project-geology",
            )

        upsert_geology_curve(
            calcite_source_role,
            "CACO3",
            calcite_column,
            unit="%",
            description="Calcite",
        )
        upsert_geology_curve(
            GeologyChannelRole.DOLOMITE,
            "CAMG_CO3_2",
            dolomite_column,
            unit="%",
            description="Dolomite",
        )
        upsert_geology_curve(
            GeologyChannelRole.LBA_GROUP,
            "LBA_GROUP",
            lba_group_column,
            unit="CODE",
            description="LBA group",
        )
        upsert_geology_curve(
            GeologyChannelRole.LBA_INTENSITY,
            "INTENSITY_LBA",
            lba_intensity_column,
            unit="CODE",
            description="LBA intensity",
        )
        upsert_geology_curve(
            GeologyChannelRole.LBA_TYPE,
            "LBA_TYPE",
            lba_type_column,
            unit="CODE",
            description="LBA type code",
        )
        upsert_geology_curve(
            GeologyChannelRole.LBA_COLOR,
            "ZVET_LBA",
            lba_color_column,
            unit="CODE",
            description="LBA colour code",
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
