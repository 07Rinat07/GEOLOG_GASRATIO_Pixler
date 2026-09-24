from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import numpy as np


class Wits0GasOperation(StrEnum):
    """Operational context used to separate gas origin from fluid interpretation."""

    DRILLING = "drilling"
    CONNECTION = "connection"
    TRIP = "trip"
    CIRCULATION = "circulation"
    UNKNOWN = "unknown"


class Wits0GasOriginKind(StrEnum):
    """Screening class for the likely operational origin of a mud-gas response."""

    BACKGROUND = "background"
    FORMATION_SHOW = "formation_show"
    CONNECTION_GAS = "connection_gas"
    TRIP_GAS = "trip_gas"
    CIRCULATED_GAS = "circulated_gas"
    ELEVATED_UNCLASSIFIED = "elevated_unclassified"
    INSUFFICIENT_CONTEXT = "insufficient_context"


@dataclass(frozen=True, slots=True)
class Wits0GasContextObservation:
    total_gas: float | None
    operation: Wits0GasOperation = Wits0GasOperation.UNKNOWN
    pumps_on: bool | None = None
    on_bottom: bool | None = None
    connection_lag_fraction: float | None = None

    def __post_init__(self) -> None:
        if self.total_gas is not None:
            value = float(self.total_gas)
            if not isfinite(value) or value < 0.0:
                raise ValueError("total_gas must be finite and non-negative")
        if self.connection_lag_fraction is not None:
            value = float(self.connection_lag_fraction)
            if not isfinite(value) or value < 0.0:
                raise ValueError("connection_lag_fraction must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class Wits0GasContextAssessment:
    kind: Wits0GasOriginKind
    total_gas: float | None
    background: float | None
    threshold: float | None
    ratio_to_background: float | None
    confidence: float
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within 0..1")


@dataclass(frozen=True, slots=True)
class Wits0GasContextClassifierConfig:
    baseline_window: int = 120
    baseline_min_samples: int = 12
    minimum_absolute_rise: float = 0.05
    minimum_ratio_to_background: float = 1.5
    robust_sigma_multiplier: float = 4.0
    connection_lag_min_fraction: float = 0.55
    connection_lag_max_fraction: float = 1.45

    def __post_init__(self) -> None:
        if self.baseline_window < 8:
            raise ValueError("baseline_window must be >= 8")
        if not 3 <= self.baseline_min_samples <= self.baseline_window:
            raise ValueError("baseline_min_samples must fit baseline_window")
        for value, name in (
            (self.minimum_absolute_rise, "minimum_absolute_rise"),
            (self.minimum_ratio_to_background, "minimum_ratio_to_background"),
            (self.robust_sigma_multiplier, "robust_sigma_multiplier"),
            (self.connection_lag_min_fraction, "connection_lag_min_fraction"),
            (self.connection_lag_max_fraction, "connection_lag_max_fraction"),
        ):
            if not isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.minimum_ratio_to_background < 1.0:
            raise ValueError("minimum_ratio_to_background must be >= 1")
        if self.connection_lag_max_fraction < self.connection_lag_min_fraction:
            raise ValueError("connection lag maximum must be >= minimum")


class Wits0GasContextClassifier:
    """Stateful robust baseline and operational gas-origin screening.

    The classifier deliberately separates *where a gas response likely came from*
    from Haworth/Pixler fluid screening. Formation-show classification requires
    stable drilling context plus an excursion above a rolling robust background.
    Connection/trip/circulation context takes precedence over formation-show
    screening so operational transients are not mislabeled as reservoir evidence.
    """

    def __init__(
        self,
        config: Wits0GasContextClassifierConfig | None = None,
    ) -> None:
        self.config = config or Wits0GasContextClassifierConfig()
        self._baseline: deque[float] = deque(maxlen=self.config.baseline_window)

    @property
    def baseline_sample_count(self) -> int:
        return len(self._baseline)

    def reset(self) -> None:
        self._baseline.clear()

    def assess(
        self,
        observation: Wits0GasContextObservation,
    ) -> Wits0GasContextAssessment:
        value = observation.total_gas
        background, threshold = self._background_and_threshold()
        if value is None:
            return Wits0GasContextAssessment(
                kind=Wits0GasOriginKind.INSUFFICIENT_CONTEXT,
                total_gas=None,
                background=background,
                threshold=threshold,
                ratio_to_background=None,
                confidence=0.0,
                reason_codes=("total_gas_missing",),
            )

        numeric = float(value)
        baseline_ready = background is not None and threshold is not None
        elevated = (
            numeric > threshold
            if background is not None and threshold is not None
            else False
        )
        ratio = (
            numeric / background
            if background is not None and background > np.finfo(np.float64).eps
            else None
        )
        ratio_elevated = (
            ratio is not None
            and ratio >= self.config.minimum_ratio_to_background
        )
        elevated = elevated and ratio_elevated

        if elevated and observation.operation is Wits0GasOperation.TRIP:
            assessment = self._assessment(
                Wits0GasOriginKind.TRIP_GAS,
                numeric,
                background,
                threshold,
                ratio,
                0.95,
                "trip_context",
                "gas_above_background",
            )
        elif elevated and self._is_connection_arrival(observation):
            assessment = self._assessment(
                Wits0GasOriginKind.CONNECTION_GAS,
                numeric,
                background,
                threshold,
                ratio,
                0.93,
                "connection_context",
                "arrival_near_lag",
                "gas_above_background",
            )
        elif (
            elevated
            and observation.operation is Wits0GasOperation.CIRCULATION
            and observation.on_bottom is not True
        ):
            assessment = self._assessment(
                Wits0GasOriginKind.CIRCULATED_GAS,
                numeric,
                background,
                threshold,
                ratio,
                0.82,
                "circulation_context",
                "off_bottom",
                "gas_above_background",
            )
        elif elevated and self._stable_drilling_context(observation):
            assessment = self._assessment(
                Wits0GasOriginKind.FORMATION_SHOW,
                numeric,
                background,
                threshold,
                ratio,
                0.84,
                "stable_drilling_context",
                "gas_above_background",
            )
        elif baseline_ready and not elevated:
            assessment = self._assessment(
                Wits0GasOriginKind.BACKGROUND,
                numeric,
                background,
                threshold,
                ratio,
                0.88 if self._stable_drilling_context(observation) else 0.72,
                "within_robust_background",
            )
        elif baseline_ready:
            assessment = self._assessment(
                Wits0GasOriginKind.ELEVATED_UNCLASSIFIED,
                numeric,
                background,
                threshold,
                ratio,
                0.55,
                "gas_above_background",
                "operation_context_inconclusive",
            )
        else:
            assessment = self._assessment(
                Wits0GasOriginKind.INSUFFICIENT_CONTEXT,
                numeric,
                background,
                threshold,
                ratio,
                0.35,
                "background_initializing",
            )

        if self._eligible_for_background(observation, assessment):
            self._baseline.append(numeric)
        return assessment

    def _background_and_threshold(self) -> tuple[float | None, float | None]:
        if len(self._baseline) < self.config.baseline_min_samples:
            return None, None
        values = np.asarray(tuple(self._baseline), dtype=np.float64)
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        robust_sigma = 1.4826 * mad
        robust_rise = self.config.robust_sigma_multiplier * robust_sigma
        rise = max(self.config.minimum_absolute_rise, robust_rise)
        return median, median + rise

    def _stable_drilling_context(
        self,
        observation: Wits0GasContextObservation,
    ) -> bool:
        return (
            observation.operation is Wits0GasOperation.DRILLING
            and observation.pumps_on is not False
            and observation.on_bottom is not False
        )

    def _is_connection_arrival(
        self,
        observation: Wits0GasContextObservation,
    ) -> bool:
        if observation.operation is not Wits0GasOperation.CONNECTION:
            return False
        fraction = observation.connection_lag_fraction
        if fraction is None:
            return True
        return (
            self.config.connection_lag_min_fraction
            <= fraction
            <= self.config.connection_lag_max_fraction
        )

    def _eligible_for_background(
        self,
        observation: Wits0GasContextObservation,
        assessment: Wits0GasContextAssessment,
    ) -> bool:
        return (
            self._stable_drilling_context(observation)
            and assessment.kind
            in {
                Wits0GasOriginKind.BACKGROUND,
                Wits0GasOriginKind.INSUFFICIENT_CONTEXT,
            }
        )

    @staticmethod
    def _assessment(
        kind: Wits0GasOriginKind,
        total_gas: float,
        background: float | None,
        threshold: float | None,
        ratio: float | None,
        confidence: float,
        *reason_codes: str,
    ) -> Wits0GasContextAssessment:
        return Wits0GasContextAssessment(
            kind=kind,
            total_gas=total_gas,
            background=background,
            threshold=threshold,
            ratio_to_background=ratio,
            confidence=confidence,
            reason_codes=tuple(reason_codes),
        )
