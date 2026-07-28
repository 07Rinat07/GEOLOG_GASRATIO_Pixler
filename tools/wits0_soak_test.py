#!/usr/bin/env python3
"""Windows-friendly long-running loopback soak test for the WITS0 capture stack.

The tool deliberately exercises TCP reconnects, arbitrary chunk boundaries, sequence gaps,
duplicates, malformed values, raw rotation, retention, recovery metadata and the append-only
connection journal.  It imports no Qt modules and can therefore run unattended on a field PC.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import signal
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from geoworkbench.acquisition import (  # noqa: E402 - source path bootstrap
    Wits0CaptureConfig,
    Wits0CaptureEngine,
    Wits0CaptureEventKind,
    Wits0CaptureState,
    Wits0ConnectionMode,
    Wits0DiskSpacePolicy,
    Wits0RawRetentionPolicy,
    Wits0RecoveryStore,
)


@dataclass(slots=True)
class ProducerStats:
    connections: int = 0
    frames_sent: int = 0
    bytes_sent: int = 0
    send_errors: int = 0
    deliberate_gaps: int = 0
    deliberate_duplicates: int = 0
    malformed_values: int = 0


@dataclass(slots=True)
class EventStats:
    connections: int = 0
    disconnections: int = 0
    diagnostics: int = 0
    warnings: int = 0
    errors: int = 0
    disk_events: int = 0
    retention_events: int = 0
    recovery_events: int = 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _frame(sequence: int, *, malformed: bool = False) -> bytes:
    rop = "BAD" if malformed else f"{10.0 + (sequence % 100) / 10.0:.1f}"
    depth = 1000.0 + sequence * 0.1
    lines = (
        "&&",
        "020102",
        f"0202{sequence}",
        "0203SOAK-WELL",
        "02041",
        datetime.now(timezone.utc).strftime("0205%y%m%d"),
        datetime.now(timezone.utc).strftime("0206%H%M%S0"),
        "02070",
        f"0208{depth:.1f}",
        f"0210{rop}",
        f"0211{50.0 + (sequence % 20):.1f}",
        f"0212{80 + (sequence % 40)}",
        "!!",
    )
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def _producer(
    *,
    port: int,
    stop: threading.Event,
    stats: ProducerStats,
    rate_hz: float,
    disconnect_interval_s: float,
    malformed_every: int,
    duplicate_every: int,
    gap_every: int,
    seed: int,
) -> None:
    randomizer = random.Random(seed)
    sequence = 0
    next_send = time.monotonic()
    send_interval = 1.0 / rate_hz
    while not stop.is_set():
        try:
            connection = socket.create_connection(("127.0.0.1", port), timeout=2.0)
            connection.settimeout(2.0)
        except OSError:
            if stop.wait(0.25):
                break
            continue
        stats.connections += 1
        connected_at = time.monotonic()
        try:
            with connection:
                while not stop.is_set():
                    if time.monotonic() - connected_at >= disconnect_interval_s:
                        break
                    sequence += 1
                    if gap_every > 0 and sequence % gap_every == 0:
                        sequence += 1
                        stats.deliberate_gaps += 1
                    malformed = malformed_every > 0 and sequence % malformed_every == 0
                    if malformed:
                        stats.malformed_values += 1
                    payload = _frame(sequence, malformed=malformed)
                    repeat = duplicate_every > 0 and sequence % duplicate_every == 0
                    payloads = (payload, payload) if repeat else (payload,)
                    if repeat:
                        stats.deliberate_duplicates += 1
                    for item in payloads:
                        position = 0
                        while position < len(item):
                            width = randomizer.randint(1, min(64, len(item) - position))
                            chunk = item[position : position + width]
                            connection.sendall(chunk)
                            stats.bytes_sent += len(chunk)
                            position += width
                        stats.frames_sent += 1
                    next_send += send_interval
                    delay = next_send - time.monotonic()
                    if delay > 0 and stop.wait(delay):
                        break
                    if delay < -1.0:
                        next_send = time.monotonic()
        except OSError:
            stats.send_errors += 1
        if not stop.is_set():
            stop.wait(0.05)


def _drain_events(engine: Wits0CaptureEngine, stats: EventStats) -> None:
    for event in engine.drain_events(max_events=10_000):
        if event.kind is Wits0CaptureEventKind.CONNECTION:
            stats.connections += 1
        elif event.kind is Wits0CaptureEventKind.DISCONNECTION:
            stats.disconnections += 1
        elif event.kind is Wits0CaptureEventKind.DIAGNOSTIC:
            stats.diagnostics += 1
        elif event.kind is Wits0CaptureEventKind.WARNING:
            stats.warnings += 1
        elif event.kind is Wits0CaptureEventKind.ERROR:
            stats.errors += 1
        elif event.kind is Wits0CaptureEventKind.DISK:
            stats.disk_events += 1
        elif event.kind is Wits0CaptureEventKind.RETENTION:
            stats.retention_events += 1
        elif event.kind is Wits0CaptureEventKind.RECOVERY:
            stats.recovery_events += 1


def _raw_inventory(root: Path, *, include_hashes: bool) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in sorted(root.rglob("*.wits")):
        record: dict[str, object] = {
            "path": str(path.relative_to(root)),
            "size_bytes": path.stat().st_size,
        }
        if include_hashes:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            record["sha256"] = digest.hexdigest()
        items.append(record)
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=float, default=8 * 60 * 60)
    parser.add_argument("--rate-hz", type=float, default=20.0)
    parser.add_argument("--disconnect-interval-seconds", type=float, default=300.0)
    parser.add_argument("--malformed-every", type=int, default=997)
    parser.add_argument("--duplicate-every", type=int, default=499)
    parser.add_argument("--gap-every", type=int, default=751)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--raw-directory", type=Path, default=Path("soak-output/raw"))
    parser.add_argument("--report", type=Path, default=Path("soak-output/report.json"))
    parser.add_argument("--raw-segment-mb", type=int, default=64)
    parser.add_argument("--critical-free-mb", type=int, default=512)
    parser.add_argument("--warning-free-mb", type=int, default=2048)
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--retention-max-gb", type=int, default=20)
    parser.add_argument("--retention-keep-segments", type=int, default=4)
    parser.add_argument("--hash-raw", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.duration_seconds <= 0 or args.rate_hz <= 0:
        raise SystemExit("duration and rate must be positive")
    port = args.port or _free_port()
    args.raw_directory = args.raw_directory.resolve()
    args.report = args.report.resolve()
    args.raw_directory.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    engine = Wits0CaptureEngine(
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="127.0.0.1",
            port=port,
            raw_directory=args.raw_directory,
            source_name="windows-soak",
            socket_timeout_s=0.25,
            raw_segment_bytes=args.raw_segment_mb * 1024 * 1024,
            event_capacity=20_000,
            disk_policy=Wits0DiskSpacePolicy(
                critical_free_bytes=args.critical_free_mb * 1024 * 1024,
                warning_free_bytes=max(
                    args.critical_free_mb,
                    args.warning_free_mb,
                )
                * 1024
                * 1024,
            ),
            retention_policy=Wits0RawRetentionPolicy(
                max_age_days=args.retention_days,
                max_total_bytes=args.retention_max_gb * 1024**3,
                keep_min_segments=args.retention_keep_segments,
            ),
        )
    )
    stop = threading.Event()
    producer_stats = ProducerStats()
    event_stats = EventStats()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, request_stop)
        except (AttributeError, ValueError):
            pass

    started_at = _utc_now()
    started_clock = time.monotonic()
    engine.start()
    deadline = started_clock + min(10.0, args.duration_seconds)
    while engine.snapshot().state is not Wits0CaptureState.LISTENING:
        if engine.snapshot().state is Wits0CaptureState.FAILED:
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)
    producer = threading.Thread(
        target=_producer,
        kwargs={
            "port": port,
            "stop": stop,
            "stats": producer_stats,
            "rate_hz": args.rate_hz,
            "disconnect_interval_s": args.disconnect_interval_seconds,
            "malformed_every": args.malformed_every,
            "duplicate_every": args.duplicate_every,
            "gap_every": args.gap_every,
            "seed": args.seed,
        },
        name="wits0-soak-producer",
        daemon=True,
    )
    producer.start()
    try:
        while not stop.is_set() and time.monotonic() - started_clock < args.duration_seconds:
            _drain_events(engine, event_stats)
            if engine.snapshot().state is Wits0CaptureState.FAILED:
                break
            stop.wait(0.25)
    finally:
        stop.set()
        producer.join(timeout=5.0)
        engine.stop(timeout=5.0)
        _drain_events(engine, event_stats)

    finished_at = _utc_now()
    elapsed = time.monotonic() - started_clock
    snapshot = engine.snapshot()
    source_root = args.raw_directory / "windows-soak"
    recovery = Wits0RecoveryStore(source_root / ".wits0-recovery.json").load()
    raw_inventory = _raw_inventory(args.raw_directory, include_hashes=args.hash_raw)
    report = {
        "schema_version": 1,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed,
        "configuration": {
            "port": port,
            "duration_seconds": args.duration_seconds,
            "rate_hz": args.rate_hz,
            "disconnect_interval_seconds": args.disconnect_interval_seconds,
            "malformed_every": args.malformed_every,
            "duplicate_every": args.duplicate_every,
            "gap_every": args.gap_every,
            "seed": args.seed,
            "raw_directory": str(args.raw_directory),
        },
        "producer": asdict(producer_stats),
        "events": asdict(event_stats),
        "capture_snapshot": asdict(snapshot),
        "recovery_manifest": asdict(recovery) if recovery is not None else None,
        "raw_files": raw_inventory,
        "raw_bytes": sum(int(item["size_bytes"]) for item in raw_inventory),
    }
    success = (
        snapshot.state is Wits0CaptureState.STOPPED
        and snapshot.frames_received > 0
        and snapshot.errors == 0
        and recovery is not None
        and recovery.clean_shutdown
    )
    report["success"] = success
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"success": success, "report": str(args.report)}, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
