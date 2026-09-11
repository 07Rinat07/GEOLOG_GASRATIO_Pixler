"""Profile-bound, append-only geology review and preparation.

O(N + B log B + P) time, O(N + B + P + K) memory: samples N,
existing intervals B, catalog/profile P, proposals K <= 10000.
Sample intervals stream through coverage cursors; no per-sample objects survive.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, TYPE_CHECKING
from uuid import uuid4

import numpy as np

from geoworkbench.domain.geology_update import GeologyUpdateRecord
from geoworkbench.domain.models import (
    CuttingsComponent, CuttingsSample, Dataset, DepthDomain, IndexRole,
    LithologyInterval, ProjectLithotype, Well,
)
if TYPE_CHECKING:
    from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError, dataset_append_state_sha256, _validate_well_identity,
)
from geoworkbench.services.las_geology import _code
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary


@dataclass(frozen=True, slots=True)
class GeologyAddition:
    layer: str
    top: float
    bottom: float
    components: tuple[tuple[int, float], ...]


@dataclass(frozen=True, slots=True)
class WellGeologyUpdatePlan:
    well_id: str
    target_dataset_id: str
    source_name: str
    source_sha256: str
    source_state_sha256: str
    target_state_sha256: str
    well_state_sha256: str
    profile_json: str
    profile_sha256: str
    additions: tuple[GeologyAddition, ...]
    lithotypes: tuple[tuple[int, ProjectLithotype], ...]
    unknown_codes: tuple[int, ...]
    invalid_composition_rows: int
    invalid_primary_rows: int
    occupied_pieces: int
    code_remaps: tuple[tuple[int, str], ...]

    @property
    def lithology_count(self) -> int:
        return sum(item.layer == "lithology" for item in self.additions)

    @property
    def cuttings_count(self) -> int:
        return sum(item.layer == "cuttings" for item in self.additions)


def _well_digest(well: Well, catalog: dict[str, ProjectLithotype]) -> str:
    value = {"well_id": well.well_id, "revision": well.content_revision,
             "lithology": [asdict(item) for item in well.lithology],
             "cuttings": [asdict(item) for item in well.cuttings],
             "catalog": {key: asdict(item) for key, item in catalog.items()}}
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()


class _Coverage:
    def __init__(self, intervals: list[Any]):
        pairs = []
        for item in intervals:
            top, bottom = float(item.top_depth), float(item.bottom_depth)
            if not np.isfinite(top) or not np.isfinite(bottom) or bottom < top:
                raise DailyLasGrowthError("Некорректные границы сохранённых геологических интервалов")
            if bottom > top:
                pairs.append((top, bottom))
        self.spans: list[tuple[float, float]] = []
        for top, bottom in sorted(pairs):
            if self.spans and top <= self.spans[-1][1]:
                self.spans[-1] = (self.spans[-1][0], max(bottom, self.spans[-1][1]))
            else:
                self.spans.append((top, bottom))
        self.cursor = 0
        self.occupied = 0

    def gaps(self, top: float, bottom: float):
        while self.cursor < len(self.spans) and self.spans[self.cursor][1] <= top:
            self.cursor += 1
        index = self.cursor
        while index < len(self.spans) and self.spans[index][0] < bottom:
            left, right = self.spans[index]
            if left > top:
                yield top, min(left, bottom)
            if right > top:
                self.occupied += 1
                top = max(top, right)
            if top >= bottom:
                break
            index += 1
        if top < bottom:
            yield top, bottom


def analyze_well_geology_update(
    session: ProjectSession, target: Dataset, source: Dataset, profile: RockCodeDictionary,
    *, source_name: str, source_sha256: str,
) -> WellGeologyUpdatePlan:
    well = session.current_well
    if well is None or well.datasets.get(target.dataset_id) is not target:
        raise DailyLasGrowthError("Геологический план требует dataset текущей скважины")
    if not source_name.strip() or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise DailyLasGrowthError("Некорректный источник геологического обновления")
    _validate_well_identity(target, source)
    for dataset in (target, source):
        if (dataset.active_index.role is not IndexRole.DEPTH or dataset.depth_domain is not DepthDomain.MD
                or (dataset.active_index.unit or "").strip().casefold() not in {"m", "м"}):
            raise DailyLasGrowthError("Геологическое дополнение требует MD в метрах")
    depth = np.asarray(source.active_index.values, dtype=float)
    if depth.ndim != 1 or depth.size < 2 or not np.isfinite(depth).all():
        raise DailyLasGrowthError("Нужна конечная шкала глубины минимум из двух точек")
    differences = np.diff(depth)
    reverse = bool(np.all(differences < 0))
    if not np.isfinite(differences).all() or (not reverse and not np.all(differences > 0)):
        raise DailyLasGrowthError("Шкала глубины должна быть строго монотонной")
    if reverse:
        depth = depth[::-1]
    step = float(np.median(np.diff(depth)))
    edges = np.concatenate(([depth[0]], depth[:-1] + np.diff(depth) / 2, [depth[-1]]))

    def values(name: str):
        found = [c for c in source.curves.values()
                 if c.metadata.original_mnemonic.strip().upper().replace(" ", "_") == name]
        if len(found) > 1:
            raise DailyLasGrowthError(f"Неоднозначный геологический канал: {name}")
        if not found:
            return None
        array = np.asarray(found[0].values, dtype=float)
        if array.shape != depth.shape:
            raise DailyLasGrowthError(f"Длина геологического канала не совпадает: {name}")
        return array[::-1] if reverse else array

    primary = values("КОД_ПОРОДЫ")
    slots = [(values(f"ПОРОДА{i}_КОД"), values(f"ПОРОДА{i}_КОЛИЧ")) for i in range(1, 6)]
    profile_json = profile.to_json()
    if len(profile_json.encode("utf-8")) > 4 * 1024 * 1024:
        raise DailyLasGrowthError("Профиль слишком большой")
    profile_hash = sha256(profile_json.encode("utf-8")).hexdigest()
    entries = {entry.source_code: entry for entry in profile.entries}
    coverage = {"lithology": _Coverage(well.lithology), "cuttings": _Coverage(well.cuttings)}
    additions: dict[str, list[GeologyAddition]] = {"lithology": [], "cuttings": []}
    unknown: set[int] = set()
    used: set[int] = set()
    invalid = invalid_primary = 0
    total = 0

    def add(layer: str, top: float, bottom: float, components: tuple[tuple[int, float], ...]):
        nonlocal total
        unknown.update(code for code, _ in components if code not in entries)
        if any(code not in entries for code, _ in components):
            return
        for left, right in coverage[layer].gaps(top, bottom):
            items = additions[layer]
            if items and items[-1].bottom == left and items[-1].components == components:
                items[-1] = replace(items[-1], bottom=right)
            else:
                if total >= 10_000:
                    raise DailyLasGrowthError("Более 10000 новых интервалов: разделите исходный LAS")
                items.append(GeologyAddition(layer, left, right, components))
                total += 1
            used.update(code for code, _ in components)

    for row, value in enumerate(depth):
        top = float(edges[row] if row == 0 or (value - depth[row - 1]) / step <= 3 else value)
        bottom = float(edges[row + 1] if row == len(depth) - 1 or (depth[row + 1] - value) / step <= 3 else value)
        if bottom <= top:
            continue
        code = _code(float(primary[row])) if primary is not None else None
        if code is not None:
            add("lithology", top, bottom, ((code, 100.0),))
        elif primary is not None and not np.isnan(primary[row]):
            invalid_primary += 1
        composition: dict[int, float] = {}
        valid = True
        for codes, amounts in slots:
            if codes is None and amounts is None:
                continue
            if codes is None or amounts is None:
                valid = False
                break
            amount = float(amounts[row])
            if amount == 0:
                continue
            rock = _code(float(codes[row]))
            if rock is None or not np.isfinite(amount) or not 0 < amount <= 100:
                valid = False
                break
            composition[rock] = composition.get(rock, 0.0) + amount
        if not valid or (composition and abs(sum(composition.values()) - 100) > 1e-6):
            invalid += 1
        elif composition:
            add("cuttings", top, bottom, tuple(sorted(composition.items())))
    # Profile identity separates vendors. Unique project export codes keep the
    # existing portable LAS dictionary unambiguous without changing source bytes.
    occupied_codes = {int(record.code) for record in session.project.lithotypes.values()
                      if record.code.isascii() and record.code.isdecimal()}
    records = []
    remaps = []
    next_code = 1
    for code in sorted(used):
        entry = entries[code]
        identity = f"las-profile-{profile_hash[:48]}-{code}"
        existing = session.project.lithotypes.get(identity)
        if existing is not None:
            export_code = existing.code
        elif code not in occupied_codes:
            export_code = str(code)
        else:
            while next_code in occupied_codes:
                next_code += 1
            if next_code > 999999:
                raise DailyLasGrowthError("Исчерпаны свободные коды экспорта пород")
            export_code = str(next_code)
        record = ProjectLithotype(identity, export_code, entry.name_ru, entry.name_en,
                                  entry.category, entry.color.lower(), entry.pattern_key, entry.name_kk)
        if existing is not None and existing != record:
            raise DailyLasGrowthError("Литотип профиля изменён вручную; создайте отдельную версию профиля")
        occupied_codes.add(int(export_code))
        if export_code != str(code):
            remaps.append((code, export_code))
        records.append((code, record))
    return WellGeologyUpdatePlan(
        well.well_id, target.dataset_id, source_name, source_sha256,
        dataset_append_state_sha256(source), dataset_append_state_sha256(target),
        _well_digest(well, session.project.lithotypes), profile_json, profile_hash,
        tuple(additions["lithology"] + additions["cuttings"]), tuple(records),
        tuple(sorted(unknown)), invalid, invalid_primary, sum(c.occupied for c in coverage.values()), tuple(remaps),
    )


@dataclass(slots=True)
class PreparedGeologyUpdate:
    lithology: list[LithologyInterval]
    cuttings: list[CuttingsSample]
    catalog: dict[str, ProjectLithotype]
    revision: int
    record: GeologyUpdateRecord


def prepare_well_geology_update(
    session: ProjectSession, target: Dataset, source: Dataset, plan: WellGeologyUpdatePlan,
    *, source_name: str, source_sha256: str, append_rows: bool,
) -> PreparedGeologyUpdate | None:
    current = analyze_well_geology_update(
        session, target, source, RockCodeDictionary.from_json(plan.profile_json),
        source_name=source_name, source_sha256=source_sha256,
    )
    if current != plan:
        raise DailyLasGrowthError("Геология, профиль или источник изменились; повторите анализ")
    if not plan.additions:
        return None
    axis = np.asarray(target.active_index.values, dtype=float)
    low, high = float(np.min(axis)), float(np.max(axis))
    if append_rows:
        incoming = np.asarray(source.active_index.values, dtype=float)
        low, high = min(low, float(incoming.min())), max(high, float(incoming.max()))
    if any(item.top < low or item.bottom > high for item in plan.additions):
        raise DailyLasGrowthError("Для новой геологии отметьте добавление новых строк LAS")
    well = session.current_well
    assert well is not None
    lithology, cuttings = list(well.lithology), list(well.cuttings)
    catalog = dict(session.project.lithotypes)
    mapping = dict(plan.lithotypes)
    catalog.update((record.lithotype_id, record) for record in mapping.values())
    lithology_ids, cuttings_ids = [], []
    for item in plan.additions:
        identity = str(uuid4())
        if item.layer == "lithology":
            lithology.append(LithologyInterval(identity, item.top, item.bottom,
                                              mapping[item.components[0][0]].lithotype_id))
            lithology_ids.append(identity)
        else:
            components = [CuttingsComponent(mapping[code].lithotype_id, amount) for code, amount in item.components]
            cuttings.append(CuttingsSample(identity, item.top, item.bottom, components))
            cuttings_ids.append(identity)
    staged_well = replace(well, lithology=lithology, cuttings=cuttings, content_revision=well.content_revision + 1)
    record = GeologyUpdateRecord(
        str(uuid4()), well.well_id, source_name, source_sha256, datetime.now(timezone.utc).isoformat(),
        plan.profile_json, plan.profile_sha256, plan.well_state_sha256,
        _well_digest(staged_well, catalog), tuple(lithology_ids), tuple(cuttings_ids),
    )
    return PreparedGeologyUpdate(lithology, cuttings, catalog, staged_well.content_revision, record)
