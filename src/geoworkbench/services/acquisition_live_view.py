from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.acquisition import (
    AcquisitionDataRowPayload,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
)
from geoworkbench.domain.models import CurveData, Dataset, DatasetIndex, IndexRole, IndexType
from geoworkbench.tablet.sampling import select_visible_samples


class AcquisitionLiveAxisMode(StrEnum):
    AUTO = "auto"
    TIME = "time"
    DEPTH = "depth"


class AcquisitionLiveQuality(StrEnum):
    GOOD = "good"
    MISSING = "missing"
    INVALID = "invalid"
    SOURCE_GAP = "source_gap"
    STALE = "stale"


class AcquisitionLiveMarkerKind(StrEnum):
    SOURCE_SEQUENCE_GAP = "source_sequence_gap"
    AXIS_GAP = "axis_gap"
    INVALID_VALUE = "invalid_value"
    MISSING_SPAN = "missing_span"


@dataclass(frozen=True, slots=True)
class AcquisitionLiveViewConfig:
    max_points_per_curve: int = 2_000
    time_window_seconds: float = 600.0
    depth_window: float = 100.0
    axis_gap_factor: float = 5.0
    stale_after_seconds: float = 10.0
    max_markers: int = 500

    def __post_init__(self) -> None:
        for value, name in (
            (self.max_points_per_curve, "max_points_per_curve"),
            (self.max_markers, "max_markers"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 2:
                raise ValueError(f"{name} must be an integer >= 2")
        for numeric_value, name in (
            (self.time_window_seconds, "time_window_seconds"),
            (self.depth_window, "depth_window"),
            (self.axis_gap_factor, "axis_gap_factor"),
            (self.stale_after_seconds, "stale_after_seconds"),
        ):
            if (
                isinstance(numeric_value, bool)
                or not isinstance(numeric_value, (int, float))
                or not isfinite(float(numeric_value))
                or float(numeric_value) <= 0.0
            ):
                raise ValueError(f"{name} must be a finite positive number")


@dataclass(frozen=True, slots=True)
class AcquisitionCurrentValue:
    curve_id: str
    mnemonic: str
    unit: str | None
    value: float | None
    quality: AcquisitionLiveQuality
    quality_codes: tuple[str, ...]
    sample_row_index: int | None
    latest_row_index: int | None
    axis_value: float | None
    received_at: str | None
    source_sequence_no: int | None
    age_rows: int | None

    def __post_init__(self) -> None:
        _required_text(self.curve_id, "curve_id")
        _required_text(self.mnemonic, "mnemonic")
        if self.value is not None and not isfinite(float(self.value)):
            raise ValueError("Current value must be finite or None")


@dataclass(frozen=True, slots=True)
class AcquisitionLiveSeries:
    curve_id: str
    mnemonic: str
    unit: str | None
    axis_values: tuple[float, ...]
    values: tuple[float, ...]
    source_point_count: int
    rendered_point_count: int

    def __post_init__(self) -> None:
        _required_text(self.curve_id, "curve_id")
        _required_text(self.mnemonic, "mnemonic")
        if len(self.axis_values) != len(self.values):
            raise ValueError("Live series axis and values must have the same length")
        if self.rendered_point_count != len(self.values):
            raise ValueError("rendered_point_count does not match live series values")


@dataclass(frozen=True, slots=True)
class AcquisitionLiveMarker:
    kind: AcquisitionLiveMarkerKind
    axis_start: float
    axis_end: float | None
    row_start: int
    row_end: int
    record_sequence: int | None
    curve_id: str | None
    code: str
    label: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AcquisitionLiveMarkerKind):
            raise ValueError("Marker kind must use AcquisitionLiveMarkerKind")
        if not isfinite(float(self.axis_start)):
            raise ValueError("Marker axis_start must be finite")
        if self.axis_end is not None and not isfinite(float(self.axis_end)):
            raise ValueError("Marker axis_end must be finite or None")
        if self.row_start < 0 or self.row_end < self.row_start:
            raise ValueError("Marker row range is invalid")
        _required_text(self.code, "marker.code")
        _required_text(self.label, "marker.label")


@dataclass(frozen=True, slots=True)
class AcquisitionLiveSnapshot:
    dataset_id: str
    session_id: str
    axis_mode: AcquisitionLiveAxisMode
    index_id: str
    index_type: IndexType
    index_role: IndexRole
    index_mnemonic: str
    index_unit: str | None
    axis_is_datetime: bool
    window_start: float | None
    window_end: float | None
    auto_follow: bool
    paused: bool
    visible_row_count: int
    total_row_count: int
    source_point_count: int
    rendered_point_count: int
    current_values: tuple[AcquisitionCurrentValue, ...]
    series: tuple[AcquisitionLiveSeries, ...]
    markers: tuple[AcquisitionLiveMarker, ...]
    revision: tuple[int, int, bool, bool, str]

    @property
    def has_data(self) -> bool:
        return self.visible_row_count > 0


@dataclass(frozen=True, slots=True)
class _SourceMetadata:
    record_no: int | None = None
    source_sequence_no: int | None = None
    sequence_status: str | None = None
    quality_by_source: tuple[tuple[str, tuple[str, ...]], ...] = ()
    global_quality: tuple[str, ...] = ()

    def quality_for(self, source_id: str | None) -> tuple[str, ...]:
        values = list(self.global_quality)
        if source_id is not None:
            for candidate, codes in self.quality_by_source:
                if candidate == source_id:
                    values.extend(codes)
        return tuple(sorted(set(values)))


class AcquisitionLiveView:
    """Read-only live/history projection over a growing append-only acquisition dataset.

    The view never mutates :class:`Dataset` or :class:`AcquisitionSession`. Pause freezes the
    visible row count, not acquisition itself. Auto-follow controls only the visible window.
    """

    def __init__(
        self,
        dataset: Dataset,
        session: AcquisitionSession,
        *,
        config: AcquisitionLiveViewConfig | None = None,
        axis_mode: AcquisitionLiveAxisMode = AcquisitionLiveAxisMode.AUTO,
    ) -> None:
        self.dataset = dataset
        self.session = session
        self.config = config or AcquisitionLiveViewConfig()
        self._axis_mode = AcquisitionLiveAxisMode(axis_mode)
        self._auto_follow = True
        self._paused = False
        self._frozen_row_count: int | None = None
        self._manual_window: tuple[float, float] | None = None
        self._selected_curve_ids: tuple[str, ...] = ()
        self._validate_projection()

    @property
    def axis_mode(self) -> AcquisitionLiveAxisMode:
        return self._axis_mode

    @property
    def auto_follow(self) -> bool:
        return self._auto_follow

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def selected_curve_ids(self) -> tuple[str, ...]:
        return self._selected_curve_ids

    @property
    def history_window(self) -> tuple[float, float] | None:
        return self._manual_window

    def available_axis_modes(self) -> tuple[AcquisitionLiveAxisMode, ...]:
        modes = [AcquisitionLiveAxisMode.AUTO]
        for mode in (
            AcquisitionLiveAxisMode.TIME,
            AcquisitionLiveAxisMode.DEPTH,
        ):
            try:
                self._resolve_index(mode)
            except ValueError:
                continue
            modes.append(mode)
        return tuple(modes)

    def set_axis_mode(self, mode: AcquisitionLiveAxisMode) -> None:
        resolved = AcquisitionLiveAxisMode(mode)
        self._resolve_index(resolved)
        self._axis_mode = resolved
        self._manual_window = None

    def set_selected_curves(self, curve_ids: Iterable[str]) -> None:
        materialized = tuple(dict.fromkeys(curve_ids))
        unknown = set(materialized) - set(self.dataset.curves)
        if unknown:
            raise KeyError(f"Unknown acquisition curve IDs: {sorted(unknown)}")
        self._selected_curve_ids = materialized

    def set_auto_follow(self, enabled: bool) -> None:
        self._auto_follow = bool(enabled)
        if self._auto_follow:
            self._manual_window = None

    def set_follow_span(self, span: float) -> None:
        value = float(span)
        if not isfinite(value) or value <= 0.0:
            raise ValueError("Follow span must be a finite positive number")
        index = self._resolve_index(self._axis_mode)
        if index.role is IndexRole.TIME:
            self.config = replace(self.config, time_window_seconds=value)
        else:
            self.config = replace(self.config, depth_window=value)

    def set_history_window(self, start: float, end: float) -> None:
        start_value = float(start)
        end_value = float(end)
        if not isfinite(start_value) or not isfinite(end_value) or start_value == end_value:
            raise ValueError("History window requires two different finite boundaries")
        self._manual_window = (
            min(start_value, end_value),
            max(start_value, end_value),
        )
        self._auto_follow = False

    def clear_history_window(self) -> None:
        self._manual_window = None

    def pause(self) -> None:
        if self._paused:
            return
        self._frozen_row_count = len(self.dataset.depth)
        self._paused = True

    def resume(self) -> None:
        self._frozen_row_count = None
        self._paused = False

    def snapshot(
        self,
        *,
        curve_ids: Iterable[str] | None = None,
        now: datetime | None = None,
        max_points_per_curve: int | None = None,
    ) -> AcquisitionLiveSnapshot:
        self._validate_projection()
        index = self._resolve_index(self._axis_mode)
        resolved_mode = (
            AcquisitionLiveAxisMode.TIME
            if index.role is IndexRole.TIME
            else AcquisitionLiveAxisMode.DEPTH
        )
        row_count = self._visible_row_count()
        axis = _index_as_plot_values(index)[:row_count]
        records = _data_records(self.session)[:row_count]
        selected = self._resolve_curve_ids(curve_ids)
        window_start, window_end = self._window(axis, resolved_mode)
        max_points = max_points_per_curve or self.config.max_points_per_curve
        if isinstance(max_points, bool) or not isinstance(max_points, int) or max_points < 2:
            raise ValueError("max_points_per_curve must be an integer >= 2")

        series: list[AcquisitionLiveSeries] = []
        rendered_total = 0
        source_total = 0
        for curve_id in selected:
            curve = self.dataset.curves[curve_id]
            values = np.asarray(curve.values, dtype=np.float64)[:row_count]
            if window_start is None or window_end is None:
                rendered_values = np.asarray([], dtype=np.float64)
                rendered_axis = np.asarray([], dtype=np.float64)
                source_count = 0
            else:
                visible_mask = (
                    np.isfinite(axis)
                    & (axis >= window_start)
                    & (axis <= window_end)
                )
                source_count = int(np.count_nonzero(visible_mask))
                rendered_values, rendered_axis = select_visible_samples(
                    axis,
                    values,
                    window_start,
                    window_end,
                    max_points=max_points,
                )
            rendered_count = int(rendered_values.size)
            source_total += source_count
            rendered_total += rendered_count
            metadata = curve.metadata
            series.append(
                AcquisitionLiveSeries(
                    curve_id=curve_id,
                    mnemonic=metadata.canonical_mnemonic
                    or metadata.original_mnemonic,
                    unit=metadata.unit,
                    axis_values=tuple(float(item) for item in rendered_axis),
                    values=tuple(float(item) for item in rendered_values),
                    source_point_count=source_count,
                    rendered_point_count=rendered_count,
                )
            )

        current_values = self._current_values(
            selected,
            axis,
            records,
            row_count,
            now=now,
        )
        markers = self._markers(
            selected,
            axis,
            records,
            window_start,
            window_end,
        )
        return AcquisitionLiveSnapshot(
            dataset_id=self.dataset.dataset_id,
            session_id=self.session.session_id,
            axis_mode=resolved_mode,
            index_id=index.index_id,
            index_type=index.index_type,
            index_role=index.role,
            index_mnemonic=index.mnemonic,
            index_unit=index.unit,
            axis_is_datetime=index.index_type is IndexType.DATETIME,
            window_start=window_start,
            window_end=window_end,
            auto_follow=self._auto_follow,
            paused=self._paused,
            visible_row_count=row_count,
            total_row_count=len(self.dataset.depth),
            source_point_count=source_total,
            rendered_point_count=rendered_total,
            current_values=current_values,
            series=tuple(series),
            markers=markers,
            revision=(
                len(self.dataset.depth),
                row_count,
                self._paused,
                self._auto_follow,
                f"{resolved_mode.value}:{window_start}:{window_end}:{','.join(selected)}",
            ),
        )

    def _resolve_curve_ids(self, curve_ids: Iterable[str] | None) -> tuple[str, ...]:
        if curve_ids is not None:
            selected = tuple(dict.fromkeys(curve_ids))
        elif self._selected_curve_ids:
            selected = self._selected_curve_ids
        else:
            selected = tuple(self.dataset.curves)
        unknown = set(selected) - set(self.dataset.curves)
        if unknown:
            raise KeyError(f"Unknown acquisition curve IDs: {sorted(unknown)}")
        return selected

    def _visible_row_count(self) -> int:
        if not self._paused:
            return len(self.dataset.depth)
        return min(self._frozen_row_count or 0, len(self.dataset.depth))

    def _resolve_index(self, mode: AcquisitionLiveAxisMode) -> DatasetIndex:
        if mode is AcquisitionLiveAxisMode.AUTO:
            return self.dataset.active_index
        wanted_role = (
            IndexRole.TIME
            if mode is AcquisitionLiveAxisMode.TIME
            else IndexRole.DEPTH
        )
        active = self.dataset.active_index
        if active.role is wanted_role:
            return active
        for index in self.dataset.indexes.values():
            if index.role is wanted_role:
                return index
        if wanted_role is IndexRole.TIME:
            derived = self._received_at_index()
        else:
            derived = self._depth_curve_index()
        if derived is not None:
            return derived
        raise ValueError(
            f"Dataset {self.dataset.dataset_id} has no {wanted_role.value} index"
        )

    def _received_at_index(self) -> DatasetIndex | None:
        records = _data_records(self.session)
        if not records:
            return None
        values = np.full(len(records), np.datetime64("NaT"), dtype="datetime64[ns]")
        valid_count = 0
        for row, record in enumerate(records):
            try:
                timestamp = _parse_utc(record.received_at)
            except (AttributeError, TypeError, ValueError):
                continue
            values[row] = np.datetime64(timestamp.replace(tzinfo=None), "ns")
            valid_count += 1
        if not valid_count:
            return None
        return DatasetIndex(
            index_id=f"{self.dataset.dataset_id}:received-at",
            mnemonic="RECEIVED_AT",
            index_type=IndexType.DATETIME,
            role=IndexRole.TIME,
            unit=None,
            values=values,
            confidence=0.8,
            evidence=(
                "Derived read-only live axis from AcquisitionRecord.received_at",
            ),
            datetime_format="ISO-8601",
            timezone="UTC",
        )

    def _depth_curve_index(self) -> DatasetIndex | None:
        ranked: list[tuple[int, str, CurveData]] = []
        priorities = {
            "MD": 0,
            "HOLE_DEPTH": 1,
            "BIT_DEPTH": 2,
            "DEPT": 3,
            "GAS_DEPTH": 4,
            "INCLINATION_DEPTH": 5,
        }
        for curve_id, curve in self.dataset.curves.items():
            metadata = curve.metadata
            mnemonic = (
                metadata.canonical_mnemonic or metadata.original_mnemonic
            ).strip().upper()
            semantic = metadata.semantic
            depth_semantic = (
                semantic is not None
                and (
                    semantic.family == "drilling_depth"
                    or semantic.canonical_kind.startswith("depth.")
                )
            )
            mnemonic_hint = mnemonic in priorities or "DEPTH" in mnemonic
            if not depth_semantic and not mnemonic_hint:
                continue
            values = np.asarray(curve.values, dtype=np.float64)
            if not np.any(np.isfinite(values)):
                continue
            rank = priorities.get(mnemonic, 50)
            ranked.append((rank, curve_id, curve))
        if not ranked:
            return None
        _rank, curve_id, curve = min(ranked, key=lambda item: (item[0], item[1]))
        metadata = curve.metadata
        mnemonic = (
            metadata.canonical_mnemonic or metadata.original_mnemonic
        ).strip().upper()
        index_type = (
            IndexType.TVDSS
            if "TVDSS" in mnemonic
            else IndexType.TVD
            if mnemonic == "TVD" or mnemonic.endswith("_TVD")
            else IndexType.MD
        )
        return DatasetIndex(
            index_id=f"{self.dataset.dataset_id}:curve-index:{curve_id}",
            mnemonic=mnemonic,
            index_type=index_type,
            role=IndexRole.DEPTH,
            unit=metadata.unit,
            values=np.asarray(curve.values, dtype=np.float64),
            confidence=(
                metadata.semantic.confidence
                if metadata.semantic is not None
                else 0.7
            ),
            evidence=(
                f"Derived read-only live axis from curve {curve_id}",
                metadata.provenance,
            ),
        )

    def _window(
        self,
        axis: NDArray[np.float64],
        mode: AcquisitionLiveAxisMode,
    ) -> tuple[float | None, float | None]:
        finite = axis[np.isfinite(axis)]
        if finite.size == 0:
            return None, None
        minimum = float(np.min(finite))
        maximum = float(np.max(finite))
        if self._manual_window is not None and not self._auto_follow:
            start, end = self._manual_window
            return max(minimum, start), min(maximum, end)
        if not self._auto_follow:
            return minimum, maximum
        span = (
            self.config.time_window_seconds
            if mode is AcquisitionLiveAxisMode.TIME
            else self.config.depth_window
        )
        return max(minimum, maximum - float(span)), maximum

    def _current_values(
        self,
        curve_ids: tuple[str, ...],
        axis: NDArray[np.float64],
        records: tuple[AcquisitionRecord, ...],
        row_count: int,
        *,
        now: datetime | None,
    ) -> tuple[AcquisitionCurrentValue, ...]:
        if row_count == 0:
            return tuple(
                AcquisitionCurrentValue(
                    curve_id=curve_id,
                    mnemonic=self.dataset.curves[curve_id].metadata.canonical_mnemonic
                    or self.dataset.curves[curve_id].metadata.original_mnemonic,
                    unit=self.dataset.curves[curve_id].metadata.unit,
                    value=None,
                    quality=AcquisitionLiveQuality.MISSING,
                    quality_codes=(AcquisitionLiveQuality.MISSING.value,),
                    sample_row_index=None,
                    latest_row_index=None,
                    axis_value=None,
                    received_at=None,
                    source_sequence_no=None,
                    age_rows=None,
                )
                for curve_id in curve_ids
            )
        reference_now = now or datetime.now(timezone.utc)
        if reference_now.tzinfo is None:
            reference_now = reference_now.replace(tzinfo=timezone.utc)
        else:
            reference_now = reference_now.astimezone(timezone.utc)
        latest_row = row_count - 1
        output: list[AcquisitionCurrentValue] = []
        for curve_id in curve_ids:
            curve = self.dataset.curves[curve_id]
            values = np.asarray(curve.values, dtype=np.float64)[:row_count]
            finite_rows = np.flatnonzero(np.isfinite(values))
            sample_row = int(finite_rows[-1]) if finite_rows.size else None
            value = float(values[sample_row]) if sample_row is not None else None
            row_for_metadata = sample_row if sample_row is not None else latest_row
            record = records[row_for_metadata] if row_for_metadata < len(records) else None
            metadata = _parse_source_metadata(record.source if record is not None else "")
            source_id = _curve_source_id(curve.metadata.provenance)
            codes = list(metadata.quality_for(source_id))
            quality = AcquisitionLiveQuality.GOOD
            if sample_row is None or sample_row < latest_row:
                quality = AcquisitionLiveQuality.MISSING
                codes.append(AcquisitionLiveQuality.MISSING.value)
            if any("invalid" in code for code in codes):
                quality = AcquisitionLiveQuality.INVALID
            elif metadata.sequence_status == "gap":
                quality = AcquisitionLiveQuality.SOURCE_GAP
                codes.append(AcquisitionLiveQuality.SOURCE_GAP.value)
            received_at = record.received_at if record is not None else None
            if received_at is not None:
                try:
                    parsed = _parse_utc(received_at)
                except ValueError:
                    parsed = None
                if (
                    parsed is not None
                    and (reference_now - parsed).total_seconds()
                    > self.config.stale_after_seconds
                ):
                    if quality is AcquisitionLiveQuality.GOOD:
                        quality = AcquisitionLiveQuality.STALE
                    codes.append(AcquisitionLiveQuality.STALE.value)
            output.append(
                AcquisitionCurrentValue(
                    curve_id=curve_id,
                    mnemonic=curve.metadata.canonical_mnemonic
                    or curve.metadata.original_mnemonic,
                    unit=curve.metadata.unit,
                    value=value,
                    quality=quality,
                    quality_codes=tuple(sorted(set(codes))),
                    sample_row_index=sample_row,
                    latest_row_index=latest_row,
                    axis_value=(
                        float(axis[sample_row])
                        if sample_row is not None and np.isfinite(axis[sample_row])
                        else None
                    ),
                    received_at=received_at,
                    source_sequence_no=metadata.source_sequence_no,
                    age_rows=(latest_row - sample_row) if sample_row is not None else None,
                )
            )
        return tuple(output)

    def _markers(
        self,
        curve_ids: tuple[str, ...],
        axis: NDArray[np.float64],
        records: tuple[AcquisitionRecord, ...],
        window_start: float | None,
        window_end: float | None,
    ) -> tuple[AcquisitionLiveMarker, ...]:
        if window_start is None or window_end is None or axis.size == 0:
            return ()
        markers: list[AcquisitionLiveMarker] = []
        visible_rows = np.flatnonzero(
            np.isfinite(axis) & (axis >= window_start) & (axis <= window_end)
        )
        if visible_rows.size == 0:
            return ()
        visible_set = set(int(item) for item in visible_rows)

        for row_index in visible_rows:
            index = int(row_index)
            record = records[index] if index < len(records) else None
            if record is None:
                continue
            metadata = _parse_source_metadata(record.source)
            if metadata.sequence_status == "gap":
                markers.append(
                    AcquisitionLiveMarker(
                        kind=AcquisitionLiveMarkerKind.SOURCE_SEQUENCE_GAP,
                        axis_start=float(axis[index]),
                        axis_end=None,
                        row_start=index,
                        row_end=index,
                        record_sequence=record.sequence,
                        curve_id=None,
                        code="sequence_gap",
                        label="Source sequence gap",
                    )
                )

        finite_axis = axis[visible_rows]
        if finite_axis.size >= 3:
            order = np.argsort(finite_axis, kind="stable")
            sorted_axis = finite_axis[order]
            sorted_rows = visible_rows[order]
            deltas = np.diff(sorted_axis)
            positive = deltas[np.isfinite(deltas) & (deltas > 0.0)]
            if positive.size >= 2:
                normal_step = float(np.median(positive))
                threshold = normal_step * self.config.axis_gap_factor
                for position in np.flatnonzero(deltas > threshold):
                    left_row = int(sorted_rows[int(position)])
                    right_row = int(sorted_rows[int(position) + 1])
                    markers.append(
                        AcquisitionLiveMarker(
                            kind=AcquisitionLiveMarkerKind.AXIS_GAP,
                            axis_start=float(
                                (sorted_axis[int(position)] + sorted_axis[int(position) + 1])
                                / 2.0
                            ),
                            axis_end=None,
                            row_start=left_row,
                            row_end=right_row,
                            record_sequence=None,
                            curve_id=None,
                            code="axis_gap",
                            label=(
                                f"Axis gap: {float(deltas[int(position)]):g} "
                                f"(normal step {normal_step:g})"
                            ),
                        )
                    )

        for curve_id in curve_ids:
            curve = self.dataset.curves[curve_id]
            values = np.asarray(curve.values, dtype=np.float64)[: axis.size]
            source_id = _curve_source_id(curve.metadata.provenance)
            for row_index in visible_rows:
                index = int(row_index)
                record = records[index] if index < len(records) else None
                if record is None:
                    continue
                metadata = _parse_source_metadata(record.source)
                codes = metadata.quality_for(source_id)
                invalid_codes = tuple(code for code in codes if "invalid" in code)
                if invalid_codes:
                    markers.append(
                        AcquisitionLiveMarker(
                            kind=AcquisitionLiveMarkerKind.INVALID_VALUE,
                            axis_start=float(axis[index]),
                            axis_end=None,
                            row_start=index,
                            row_end=index,
                            record_sequence=record.sequence,
                            curve_id=curve_id,
                            code=",".join(invalid_codes),
                            label=f"{curve.metadata.original_mnemonic}: invalid source value",
                        )
                    )

            missing_mask = np.zeros(axis.shape, dtype=bool)
            missing_mask[visible_rows] = ~np.isfinite(values[visible_rows])
            for start, end in _true_segments(missing_mask):
                if start not in visible_set and end - 1 not in visible_set:
                    continue
                start_axis = float(axis[start])
                end_axis = float(axis[end - 1])
                markers.append(
                    AcquisitionLiveMarker(
                        kind=AcquisitionLiveMarkerKind.MISSING_SPAN,
                        axis_start=start_axis,
                        axis_end=end_axis,
                        row_start=start,
                        row_end=end - 1,
                        record_sequence=None,
                        curve_id=curve_id,
                        code="missing_span",
                        label=f"{curve.metadata.original_mnemonic}: missing values",
                    )
                )

        markers.sort(
            key=lambda item: (
                item.axis_start,
                item.kind.value,
                item.curve_id or "",
                item.row_start,
            )
        )
        return tuple(markers[: self.config.max_markers])

    def _validate_projection(self) -> None:
        if self.dataset.dataset_id != self.session.dataset_schema.dataset_id:
            raise ValueError("Dataset does not belong to the supplied acquisition session")
        if len(self.dataset.depth) != len(_data_records(self.session)):
            raise ValueError(
                "Growing dataset row count does not match append-only acquisition data rows"
            )
        expected_curves = {
            item.metadata.curve_id for item in self.session.dataset_schema.curves
        }
        if set(self.dataset.curves) != expected_curves:
            raise ValueError("Dataset curves do not match acquisition session schema")
        expected_indexes = {item.index_id for item in self.session.dataset_schema.indexes}
        if set(self.dataset.indexes) != expected_indexes:
            raise ValueError("Dataset indexes do not match acquisition session schema")


def _data_records(session: AcquisitionSession) -> tuple[AcquisitionRecord, ...]:
    return tuple(
        record
        for record in session.records
        if record.kind is AcquisitionRecordKind.DATA_ROW
        and isinstance(record.payload, AcquisitionDataRowPayload)
    )


def _index_as_plot_values(index: DatasetIndex) -> NDArray[np.float64]:
    values = np.asarray(index.values)
    if index.index_type is IndexType.DATETIME:
        if np.issubdtype(values.dtype, np.datetime64):
            raw_ns = values.astype("datetime64[ns]").astype(np.int64)
        elif np.issubdtype(values.dtype, np.integer):
            raw_ns = values.astype(np.int64)
        else:
            raise ValueError("DATETIME live index must be datetime64 or Unix ns")
        output = raw_ns.astype(np.float64) / 1_000_000_000.0
        output[raw_ns == np.iinfo(np.int64).min] = np.nan
        return output
    try:
        return values.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("Live index must be numeric") from exc


def _parse_source_metadata(source: str) -> _SourceMetadata:
    if not isinstance(source, str):
        return _SourceMetadata()
    record_no: int | None = None
    source_sequence_no: int | None = None
    sequence_status: str | None = None
    global_quality: list[str] = []
    quality_by_source: dict[str, list[str]] = {}
    for token in source.split(";"):
        candidate = token.strip()
        if not candidate:
            continue
        if candidate.startswith("wits0:record="):
            raw = candidate.removeprefix("wits0:record=")
            try:
                record_no = int(raw)
            except ValueError:
                pass
        elif candidate.startswith("source-sequence="):
            raw = candidate.removeprefix("source-sequence=")
            try:
                source_sequence_no = int(raw)
            except ValueError:
                pass
        elif candidate.startswith("sequence-status="):
            sequence_status = candidate.removeprefix("sequence-status=") or None
        elif candidate.startswith("quality="):
            raw_entries = candidate.removeprefix("quality=")
            for entry in raw_entries.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                if ":" not in entry:
                    global_quality.append(entry)
                    continue
                source_id, code = entry.split(":", 1)
                source_id = source_id.strip()
                code = code.strip()
                if source_id and code:
                    quality_by_source.setdefault(source_id, []).append(code)
        elif candidate.startswith("frame-quality="):
            raw_entries = candidate.removeprefix("frame-quality=")
            global_quality.extend(
                entry.strip() for entry in raw_entries.split(",") if entry.strip()
            )
    return _SourceMetadata(
        record_no=record_no,
        source_sequence_no=source_sequence_no,
        sequence_status=sequence_status,
        quality_by_source=tuple(
            (source_id, tuple(sorted(set(codes))))
            for source_id, codes in sorted(quality_by_source.items())
        ),
        global_quality=tuple(sorted(set(global_quality))),
    )


def _curve_source_id(provenance: str | None) -> str | None:
    if not provenance:
        return None
    candidate = provenance.strip()
    if candidate.startswith("wits0:"):
        source_id = candidate.removeprefix("wits0:")
        return source_id if len(source_id) == 4 and source_id.isdigit() else None
    return None


def _true_segments(mask: NDArray[np.bool_]) -> tuple[tuple[int, int], ...]:
    if mask.size == 0:
        return ()
    padded = np.concatenate((np.asarray([False]), mask, np.asarray([False])))
    changes = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    return tuple(
        (int(start), int(end)) for start, end in zip(starts, ends, strict=True)
    )


def _parse_utc(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def _required_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
