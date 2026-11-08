"""Bounded, read-only snapshot and freshness checks for background GIS review."""

from __future__ import annotations

from collections.abc import Callable
from copy import copy
from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.models import CalculationState, CurveData, CurveMetadata, Dataset, DatasetIndex
from geoworkbench.services.gis_interval_sample_review import GisIntervalReviewCancelled


class GisIntervalSourceChanged(ValueError):
    """The live source no longer matches the background review snapshot."""


@dataclass(frozen=True, slots=True)
class _CurveState:
    curve: CurveData
    metadata: CurveMetadata
    values: np.ndarray
    version: int
    state: CalculationState


def _axis_signature(axis: DatasetIndex) -> tuple[object, ...]:
    return (
        axis.index_id, axis.mnemonic, axis.index_type, axis.role, axis.unit,
        axis.confidence, axis.evidence, axis.datetime_format, axis.timezone,
    )


def _check_cancel(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise GisIntervalReviewCancelled


def _same_array(source: np.ndarray, saved: np.ndarray, cancelled: Callable[[], bool]) -> bool:
    if source.shape != saved.shape or source.dtype != saved.dtype:
        return False
    # Chunked flat iteration avoids allocating another full LAS-sized mask.
    for start in range(0, source.size, 65_536):
        _check_cancel(cancelled)
        left = source.flat[start:start + 65_536]
        right = saved.flat[start:start + 65_536]
        if not np.array_equal(left, right, equal_nan=source.dtype.kind in "fc"):
            return False
    return True


class GisIntervalSnapshot:
    """Own selected numeric copies and detect source changes without editing them.

    Non-selected curve metadata is retained for manifest/identity checks, but its
    numeric array is not copied. Results are a snapshot, not a live subscription.
    """

    def __init__(self, source: Dataset, keys: tuple[str, ...], cancelled: Callable[[], bool]) -> None:
        _check_cancel(cancelled)
        self.source = source
        self.dataset_id = source.dataset_id
        self.kind = source.kind
        if source.active_index_id is None:
            raise ValueError("A current index is required")
        self.active_index_id = source.active_index_id
        self.axis = source.active_index
        self.axis_values = self.axis.values
        self.axis_signature = _axis_signature(self.axis)
        self.headers = dict(source.headers)
        self.parameters = dict(source.parameters)
        self.curves = {
            key: _CurveState(curve, curve.metadata, curve.values, curve.version, curve.state)
            for key, curve in source.curves.items()
        }
        copied_axis = copy(self.axis)
        copied_axis.values = np.array(self.axis_values, copy=True, order="C")
        _check_cancel(cancelled)
        copied_curves: dict[str, CurveData] = {}
        for key, state in self.curves.items():
            _check_cancel(cancelled)
            values = np.array(state.values, copy=True, order="C") if key in keys else np.empty(0)
            copied_curves[key] = CurveData(state.metadata, values, state.version, state.state)
        snapshot = copy(source)
        snapshot.depth = copied_axis.values
        snapshot.indexes = {self.active_index_id: copied_axis}
        snapshot.active_index_id = self.active_index_id
        snapshot.curves = copied_curves
        snapshot.headers = dict(self.headers)
        snapshot.parameters = dict(self.parameters)
        self.dataset = snapshot
        self.keys = keys
        if not self.matches(cancelled):
            raise GisIntervalSourceChanged("GIS source changed while making the snapshot")

    def structure_matches(self) -> bool:
        """Cheap GUI-thread check after the worker has verified array contents."""
        source = self.source
        if (
            source.dataset_id != self.dataset_id or source.kind is not self.kind
            or source.active_index_id != self.active_index_id
            or source.headers != self.headers or source.parameters != self.parameters
            or len(source.curves) != len(self.curves)
        ):
            return False
        try:
            axis = source.active_index
            if axis is not self.axis or axis.values is not self.axis_values or _axis_signature(axis) != self.axis_signature:
                return False
            for key, state in self.curves.items():
                curve = source.curves.get(key)
                if (
                    curve is not state.curve or curve.metadata is not state.metadata
                    or curve.values is not state.values or curve.version != state.version or curve.state is not state.state
                ):
                    return False
        except (RuntimeError, AttributeError, KeyError):
            return False
        return True

    def matches(self, cancelled: Callable[[], bool]) -> bool:
        """Check current identity and numerical content against the copied input."""
        _check_cancel(cancelled)
        if not self.structure_matches():
            return False
        if not _same_array(np.asarray(self.axis_values), np.asarray(self.dataset.active_index.values), cancelled):
            return False
        for key in self.keys:
            _check_cancel(cancelled)
            state = self.curves.get(key)
            if state is not None and not _same_array(
                np.asarray(state.values), self.dataset.curves[key].values, cancelled,
            ):
                return False
        return self.structure_matches()
