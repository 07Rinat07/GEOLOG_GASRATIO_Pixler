from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / ".github" / "workflows" / "qt-native-replay.yml"
GATE = ROOT / ".github" / "workflows" / "release-gate.yml"


def test_native_replay_is_manual_only_with_bounded_inputs() -> None:
    workflow = MANUAL.read_text(encoding="utf-8")
    assert "  workflow_dispatch:" in workflow
    assert "  pull_request:" not in workflow
    assert "  push:" not in workflow
    for mode in ("isolated", "sequence", "both"):
        assert f"          - {mode}" in workflow
    for repetition in ("1", "2", "3", "5"):
        assert f'          - "{repetition}"' in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "cancel-in-progress: false" in workflow


def test_native_replay_uses_pinned_release_env_and_preserves_failures() -> None:
    workflow = MANUAL.read_text(encoding="utf-8")
    assert "uv pip sync requirements/release.lock --python .venv --require-hashes" in workflow
    assert "tools/capture_windows_native_runtime.py" in workflow
    assert "tools/replay_windows_qt_native.py" in workflow
    assert '--commit "${{ github.sha }}"' in workflow
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in workflow
    assert "LocalDumps\\python.exe" in workflow
    assert "DumpType -Value 1" in workflow
    assert "DumpCount -Value 2" in workflow
    assert "retention-days: 3" in workflow
    assert "retention-days: 7" in workflow
    assert "if: always()" in workflow
    release = GATE.read_text(encoding="utf-8")
    for mandatory in (
        "Windows quality gate",
        "Windows GUI, HiDPI and PDF acceptance",
        "Windows dependency and source security gate",
    ):
        assert mandatory in release
    assert "qt-native-replay" not in release


def test_maximum_replay_budget_fits_workflow_timeout_with_headroom() -> None:
    from tools.replay_windows_qt_native import CHILD_TIMEOUT_SECONDS, replay_plan

    workflow = MANUAL.read_text(encoding="utf-8")
    assert "timeout-minutes: 120" in workflow
    maximum_children = len(replay_plan(5, "both"))
    assert maximum_children == 40
    # Keep at most 100 minutes of child runtime inside the 120-minute Windows job.
    # Preserve 20 minutes for checkout, installation, artifact uploads and overhead.
    assert maximum_children * CHILD_TIMEOUT_SECONDS <= (120 - 20) * 60
