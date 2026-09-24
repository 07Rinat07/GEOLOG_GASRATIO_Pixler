from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Iterable
from uuid import uuid4

from geoworkbench.acquisition.wits0 import Wits0Profile
from geoworkbench.acquisition.wits0_parser import Wits0ParsedFrame
from geoworkbench.domain.models import Well
from geoworkbench.services.wits0_acquisition import (
    Wits0AcquisitionConfig,
    Wits0AcquisitionRuntime,
    Wits0BackpressurePolicy,
    Wits0FrameNormalizerPolicy,
)
from geoworkbench.services.wits0_import_review import (
    Wits0DiscoveryAccumulator,
    Wits0DiscoverySnapshot,
    Wits0ImportReviewCommit,
    Wits0ImportReviewController,
)


@dataclass(frozen=True, slots=True)
class Wits0LivePreviewConfig:
    """Limits for the non-persistent WITS0 preview projection."""

    max_buffered_frames: int = 2_000
    max_pending_records: int = 256
    drain_batch_size: int = 64
    runtime_compaction_factor: int = 2

    def __post_init__(self) -> None:
        for value, label in (
            (self.max_buffered_frames, "max_buffered_frames"),
            (self.max_pending_records, "max_pending_records"),
            (self.drain_batch_size, "drain_batch_size"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if (
            isinstance(self.runtime_compaction_factor, bool)
            or not isinstance(self.runtime_compaction_factor, int)
            or self.runtime_compaction_factor < 2
        ):
            raise ValueError("runtime_compaction_factor must be an integer >= 2")

    @property
    def max_runtime_rows(self) -> int:
        return self.max_buffered_frames * self.runtime_compaction_factor


class Wits0LivePreview:
    """Build a bounded in-memory Dataset before an operator starts acquisition.

    Automatic mapping is used only for visualization. Persisted acquisition still
    requires the explicit Import Review commit owned by the capture workflow.
    """

    def __init__(
        self,
        profile: Wits0Profile,
        *,
        config: Wits0LivePreviewConfig | None = None,
        review_controller: Wits0ImportReviewController | None = None,
    ) -> None:
        self.profile = profile
        self.config = config or Wits0LivePreviewConfig()
        self.discovery = Wits0DiscoveryAccumulator(profile)
        self._review_controller = review_controller or Wits0ImportReviewController()
        self._frames: deque[Wits0ParsedFrame] = deque(
            maxlen=self.config.max_buffered_frames
        )
        self._runtime: Wits0AcquisitionRuntime | None = None
        self._preview_commit: Wits0ImportReviewCommit | None = None
        self._schema_fingerprint: str | None = None
        self._last_error: str | None = None
        self._evicted_frame_count = 0
        self._compaction_count = 0

    @property
    def runtime(self) -> Wits0AcquisitionRuntime | None:
        return self._runtime

    @property
    def buffered_frame_count(self) -> int:
        return len(self._frames)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def evicted_frame_count(self) -> int:
        return self._evicted_frame_count

    @property
    def compaction_count(self) -> int:
        return self._compaction_count

    @property
    def retained_row_count(self) -> int:
        if self._runtime is None:
            return 0
        return len(self._runtime.controller.dataset.active_index.values)

    @property
    def history_is_truncated(self) -> bool:
        return self._evicted_frame_count > 0

    def observe(self, frame: Wits0ParsedFrame) -> Wits0AcquisitionRuntime | None:
        """Observe one frame and return the current renderable preview runtime."""

        if len(self._frames) == self.config.max_buffered_frames:
            self._evicted_frame_count += 1
        self._frames.append(frame)
        self.discovery.observe(frame)
        snapshot = self.discovery.snapshot()
        if not snapshot.channels:
            return self._runtime
        if self._runtime is None or self._schema_fingerprint != snapshot.fingerprint:
            self._rebuild(snapshot, reuse_commit=False)
            return self._runtime
        try:
            self._runtime.submit_frame(frame)
            self._runtime.flush()
        except (ValueError, RuntimeError) as exc:
            self._last_error = str(exc)
        else:
            self._last_error = None
        if self.retained_row_count > self.config.max_runtime_rows:
            self._rebuild(snapshot, reuse_commit=True)
            self._compaction_count += 1
        return self._runtime

    def observe_discovery_only(self, frame: Wits0ParsedFrame) -> None:
        """Update discovery while a persisted acquisition runtime owns the frame."""

        self.discovery.observe(frame)

    def backfill(self, runtime: Wits0AcquisitionRuntime) -> int:
        """Submit buffered preview frames through a reviewed persistent runtime."""

        results = runtime.submit_frames(tuple(self._frames))
        runtime.flush()
        return sum(result.accepted for result in results)

    def reset(self) -> None:
        self.discovery.reset()
        self._frames.clear()
        self._runtime = None
        self._preview_commit = None
        self._schema_fingerprint = None
        self._last_error = None
        self._evicted_frame_count = 0
        self._compaction_count = 0

    def _rebuild(
        self,
        snapshot: Wits0DiscoverySnapshot,
        *,
        reuse_commit: bool,
    ) -> None:
        try:
            commit = (
                self._preview_commit
                if reuse_commit
                and self._preview_commit is not None
                and self._schema_fingerprint == snapshot.fingerprint
                else None
            )
            if commit is None:
                plan = self._review_controller.initial_plan(
                    snapshot,
                    dataset_name="WITS0 Live Preview",
                )
                candidates = self._review_controller.index_candidates(snapshot)
                selected_index = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.candidate_id == plan.index_candidate_id
                    ),
                    None,
                )
                # Preview displays source values as received. Unit conversion remains
                # an explicit Import Review decision for the persisted Dataset.
                plan = replace(
                    plan,
                    index_unit=(
                        selected_index.source_uom
                        if selected_index is not None
                        else plan.index_unit
                    ),
                    channels=tuple(
                        replace(channel, canonical_uom=channel.source_uom)
                        for channel in plan.channels
                    ),
                )
                commit = self._review_controller.commit(snapshot, self.profile, plan)
            runtime = Wits0AcquisitionRuntime(
                Well("wits0-preview", "WITS0 Live Preview"),
                commit,
                session_id=f"wits0-preview-{uuid4()}",
                config=Wits0AcquisitionConfig(
                    max_pending_records=self.config.max_pending_records,
                    drain_batch_size=self.config.drain_batch_size,
                    checkpoint_every_records=self.config.max_buffered_frames + 1,
                    checkpoint_interval_seconds=86_400.0,
                    backpressure_policy=Wits0BackpressurePolicy.DRAIN_THEN_RETRY,
                ),
                normalizer_policy=Wits0FrameNormalizerPolicy(
                    fallback_header_datetime_to_received_at=True,
                ),
            )
            runtime.submit_frames(self._frames)
            runtime.flush()
        except (ValueError, RuntimeError) as exc:
            self._last_error = str(exc)
            return
        self._runtime = runtime
        self._preview_commit = commit
        self._schema_fingerprint = snapshot.fingerprint
        self._last_error = None

    def buffered_frames(self) -> Iterable[Wits0ParsedFrame]:
        """Return an immutable iteration boundary for diagnostics and tests."""

        return tuple(self._frames)
