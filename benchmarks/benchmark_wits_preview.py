"""Isolated RSS scaling gate for the bounded WITS0 live preview.

Run: python -m benchmarks.benchmark_wits_preview --buffer-frames 100
Each fixture runs in a fresh subprocess so peak RSS is comparable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter

from benchmarks.benchmark_acquisition import _peak_rss_bytes
from geoworkbench.acquisition import Wits0StreamProcessor, load_builtin_wits0_profile
from geoworkbench.services.wits0_live_preview import Wits0LivePreview, Wits0LivePreviewConfig


MIB = 1024 * 1024
DEFAULT_MAX_GROWTH_MIB = 96.0


@dataclass(frozen=True, slots=True)
class PreviewMemoryResult:
    frames: int
    buffer_frames: int
    baseline_rss_mib: float
    peak_rss_mib: float
    elapsed_seconds: float
    retained_frames: int
    retained_rows: int
    retained_records: int
    compactions: int
    evicted_frames: int

    @classmethod
    def from_json(cls, data: dict[str, object]) -> PreviewMemoryResult:
        return cls(**data)  # type: ignore[arg-type]


def _frame(sequence: int) -> bytes:
    return ("\r\n".join((
        "&&", "0201WELL-8", "020201", "020302", f"0204{sequence}",
        "0205260924", "0206150000", "02070",
        f"0208{123 + sequence % 100 / 10:.1f}", "021011.2", "!!",
    ))).encode("ascii")


def measure_preview(*, frames: int, buffer_frames: int) -> PreviewMemoryResult:
    if frames < 1 or buffer_frames < 1:
        raise ValueError("frames and buffer_frames must be positive")
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    preview = Wits0LivePreview(profile, config=Wits0LivePreviewConfig(
        max_buffered_frames=buffer_frames,
    ))
    baseline = _peak_rss_bytes() / MIB
    started = perf_counter()
    origin = datetime(2026, 9, 24, 15, tzinfo=timezone.utc)
    for sequence in range(1, frames + 1):
        received_at = (origin + timedelta(seconds=sequence)).isoformat().replace("+00:00", "Z")
        parsed = processor.append(
            _frame(sequence), received_at=received_at, source_ref="benchmark.wits",
        )
        if len(parsed) != 1:
            raise AssertionError(f"expected one parsed frame at sequence {sequence}")
        preview.observe(parsed[0])
        if preview.last_error is not None:
            raise RuntimeError(f"preview failed at sequence {sequence}: {preview.last_error}")
    runtime = preview.runtime
    if runtime is None:
        raise RuntimeError("preview produced no runtime")
    return PreviewMemoryResult(
        frames=frames,
        buffer_frames=buffer_frames,
        baseline_rss_mib=baseline,
        peak_rss_mib=_peak_rss_bytes() / MIB,
        elapsed_seconds=perf_counter() - started,
        retained_frames=preview.buffered_frame_count,
        retained_rows=preview.retained_row_count,
        retained_records=len(runtime.session.records),
        compactions=preview.compaction_count,
        evicted_frames=preview.evicted_frame_count,
    )


def evaluate_results(
    short: PreviewMemoryResult,
    long: PreviewMemoryResult,
    *,
    max_growth_mib: float = DEFAULT_MAX_GROWTH_MIB,
) -> tuple[str, ...]:
    if max_growth_mib <= 0 or not (max_growth_mib < float("inf")):
        raise ValueError("max_growth_mib must be finite and positive")
    if short.buffer_frames != long.buffer_frames or long.frames < short.frames * 10:
        raise ValueError("compare the same buffer with at least 10x as many frames")
    violations: list[str] = []
    for result in (short, long):
        if result.retained_frames != min(result.frames, result.buffer_frames):
            violations.append(f"{result.frames} frames: retained frame count differs from window")
        if result.evicted_frames != max(0, result.frames - result.buffer_frames):
            violations.append(f"{result.frames} frames: eviction count differs from window")
        if result.retained_rows > result.buffer_frames * 2:
            violations.append(f"{result.frames} frames: Dataset rows exceed bounded runtime")
        if result.retained_records > result.buffer_frames * 2:
            violations.append(f"{result.frames} frames: session records exceed bounded runtime")
    if long.compactions < 1:
        violations.append("long stream did not exercise preview compaction")
    growth = long.peak_rss_mib - short.peak_rss_mib
    if growth > max_growth_mib:
        violations.append(f"peak RSS growth {growth:.1f} MiB exceeds {max_growth_mib:.1f} MiB")
    return tuple(violations)


def _worker(frames: int, buffer_frames: int) -> PreviewMemoryResult:
    process = subprocess.run(
        [sys.executable, "-m", "benchmarks.benchmark_wits_preview", "--worker-frames",
         str(frames), "--buffer-frames", str(buffer_frames)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"}, check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"{frames} frame worker failed: {process.stderr or process.stdout}")
    return PreviewMemoryResult.from_json(json.loads(process.stdout))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buffer-frames", type=int, default=100)
    parser.add_argument("--max-growth-mib", type=float, default=DEFAULT_MAX_GROWTH_MIB)
    parser.add_argument("--worker-frames", type=int, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.buffer_frames < 1:
        parser.error("--buffer-frames must be positive")
    if args.worker_frames is not None:
        print(json.dumps(asdict(measure_preview(
            frames=args.worker_frames, buffer_frames=args.buffer_frames,
        ))))
        return 0
    short = _worker(args.buffer_frames, args.buffer_frames)
    long = _worker(args.buffer_frames * 10, args.buffer_frames)
    violations = evaluate_results(short, long, max_growth_mib=args.max_growth_mib)
    print(json.dumps({"short": asdict(short), "long": asdict(long),
                      "max_growth_mib": args.max_growth_mib, "violations": violations}, indent=2))
    return int(bool(violations))


if __name__ == "__main__":
    sys.exit(main())
