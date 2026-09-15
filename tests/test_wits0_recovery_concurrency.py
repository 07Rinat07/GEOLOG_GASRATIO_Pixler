from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import threading
import time

import pytest

from geoworkbench.acquisition import (
    Wits0CaptureConfig,
    Wits0CaptureEngine,
    Wits0ConnectionMode,
    Wits0RecoveryManifest,
    Wits0RecoveryState,
)


def test_recovery_manifest_updates_are_serialized_and_preserve_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = Wits0CaptureEngine(
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_CLIENT,
            host="192.168.0.100",
            port=2041,
            raw_directory=tmp_path,
            source_name="geoscape-halliburton",
        )
    )
    engine._manifest = Wits0RecoveryManifest(
        run_id=engine.run_id,
        state=Wits0RecoveryState.RUNNING,
        clean_shutdown=False,
        process_id=123,
        started_at="2026-09-15T00:00:00.000Z",
        updated_at="2026-09-15T00:00:00.000Z",
        mode=Wits0ConnectionMode.TCP_CLIENT.value,
        host="192.168.0.100",
        port=2041,
        source_name="geoscape-halliburton",
        raw_directory=str(tmp_path),
    )

    state_lock = threading.Lock()
    active_updates = 0
    peak_updates = 0

    def delayed_update(
        manifest: Wits0RecoveryManifest,
        **changes: object,
    ) -> Wits0RecoveryManifest:
        nonlocal active_updates, peak_updates
        with state_lock:
            active_updates += 1
            peak_updates = max(peak_updates, active_updates)
        try:
            time.sleep(0.05)
            return replace(
                manifest,
                updated_at="2026-09-15T00:00:01.000Z",
                **changes,
            )
        finally:
            with state_lock:
                active_updates -= 1

    monkeypatch.setattr(engine._recovery_store, "update", delayed_update)

    start_barrier = threading.Barrier(3)
    errors: list[BaseException] = []

    def update_peer() -> None:
        try:
            start_barrier.wait(timeout=2.0)
            engine._update_manifest(current_peer="192.168.0.100:2041")
        except BaseException as exc:  # pragma: no cover - assertion reports worker failure
            errors.append(exc)

    def update_profile() -> None:
        try:
            start_barrier.wait(timeout=2.0)
            engine._update_manifest(custom_profile_path="profile.json")
        except BaseException as exc:  # pragma: no cover - assertion reports worker failure
            errors.append(exc)

    peer_thread = threading.Thread(target=update_peer)
    profile_thread = threading.Thread(target=update_profile)
    peer_thread.start()
    profile_thread.start()
    start_barrier.wait(timeout=2.0)
    peer_thread.join(timeout=2.0)
    profile_thread.join(timeout=2.0)

    assert not peer_thread.is_alive()
    assert not profile_thread.is_alive()
    assert not errors
    assert peak_updates == 1
    assert engine._manifest is not None
    assert engine._manifest.current_peer == "192.168.0.100:2041"
    assert engine._manifest.custom_profile_path == "profile.json"
