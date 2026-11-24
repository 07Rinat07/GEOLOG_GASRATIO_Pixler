from __future__ import annotations

from pathlib import Path
import re


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
    for repetition in ("1", "2", "3", "4"):
        assert f'          - "{repetition}"' in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "cancel-in-progress: false" in workflow


def test_native_replay_passes_only_the_fixed_profile_choices_to_the_cli() -> None:
    workflow = MANUAL.read_text(encoding="utf-8")
    profile = re.search(r"(?m)^      profile:\n((?: {8,}[^\n]+\n)+)", workflow)
    assert profile is not None
    field = profile.group(1)
    assert "        type: choice\n" in field
    assert re.search(r'(?m)^        default: ["\']?default["\']?$', field)
    assert re.findall(r'(?m)^          - ["\']?([\w-]+)["\']?$', field) == [
        "default", "adaptive-geology",
    ]
    assert "GEOLOG_REPLAY_PROFILE: ${{ inputs.profile }}" in workflow
    assert re.search(r'--profile\s+"?\$env:GEOLOG_REPLAY_PROFILE"?', workflow)


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
    from tools.replay_windows_qt_native import (
        CHILD_TIMEOUT_SECONDS,
        MAX_REPETITIONS,
        replay_plan,
    )

    workflow = MANUAL.read_text(encoding="utf-8")
    assert "timeout-minutes: 145" in workflow
    maximum_children = len(replay_plan(MAX_REPETITIONS, "both"))
    assert MAX_REPETITIONS == 4
    assert maximum_children == 4 * (10 + 1)
    # Reserve at least 30 minutes for setup, artifact uploads and overhead.
    # Ten isolated selectors plus one shared process per repetition need
    # 110 minutes at the unchanged 150-second child timeout.
    assert maximum_children * CHILD_TIMEOUT_SECONDS <= (145 - 30) * 60
    focused_children = len(replay_plan(MAX_REPETITIONS, "both", profile="adaptive-geology"))
    assert focused_children == 4 * (5 + 1)
    assert focused_children * CHILD_TIMEOUT_SECONDS <= 60 * 60
