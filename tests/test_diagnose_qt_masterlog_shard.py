from __future__ import annotations

import pytest

from tools.diagnose_qt_masterlog_shard import debugger_replay_passed


@pytest.mark.parametrize(
    ("status", "output", "expected"),
    (
        (0, "================= 330 passed in 11.35s =================", True),
        (1, "================= 330 passed in 11.35s =================", False),
        (0, "CDB captured an exception and quit", False),
        (0, "ExceptionCode: c0000005 (Access violation)", False),
        (0, "Windows fatal exception: code 0xc0000374", False),
        (0, "(123.4): Access violation (!!! second chance !!!)", False),
        (0, "================= 329 passed, 1 failed in 11.35s =================", False),
        (0, "tests/test_masterlog_columns_dialog.py::test_still_running PASSED", False),
        (0, "================= 329 passed, 1 skipped in 11.35s =================", True),
    ),
)
def test_cdb_exit_does_not_mask_incomplete_or_crashed_pytest(
    status: int, output: str, expected: bool
) -> None:
    assert debugger_replay_passed(status, output) is expected
