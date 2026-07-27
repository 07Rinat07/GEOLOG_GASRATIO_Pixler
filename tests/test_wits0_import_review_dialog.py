from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from geoworkbench.acquisition import Wits0StreamProcessor, load_builtin_wits0_profile
from geoworkbench.services.wits0_import_review import discover_wits0_frames


ROOT = Path(__file__).resolve().parents[1]
DIALOG_SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "wits0_import_review_dialog.py"
CAPTURE_SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "wits0_capture_dialog.py"


def _frame() -> bytes:
    return (
        "&&\r\n"
        "0201SG-8\r\n"
        "020201\r\n"
        "020302\r\n"
        "02041\r\n"
        "0205260727\r\n"
        "02060215450\r\n"
        "02070\r\n"
        "0208123.4\r\n"
        "021011.2\r\n"
        "!!\r\n"
    ).encode("ascii")


def test_capture_dialog_integrates_immutable_import_review_boundary() -> None:
    capture = CAPTURE_SOURCE.read_text(encoding="utf-8")
    review = DIALOG_SOURCE.read_text(encoding="utf-8")

    assert "Wits0DiscoveryAccumulator" in capture
    assert "Wits0ImportReviewDialog" in capture
    assert "save_wits0_custom_profile" in capture
    assert "review_commit" in capture
    assert "AcquisitionDatasetSchema" not in capture
    assert "controller.commit(" in review
    assert "commit_result" in review


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed in the headless test environment",
)
def test_wits0_import_review_dialog_constructs_and_commits_offscreen(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_import_review_dialog import Wits0ImportReviewDialog

    profile = load_builtin_wits0_profile()
    frames = Wits0StreamProcessor(profile).append(_frame())
    snapshot = discover_wits0_frames(profile, frames)
    app = QApplication.instance() or QApplication([])
    dialog = Wits0ImportReviewDialog(
        snapshot,
        profile,
        language=AppLanguage.RU,
        profile_directory=tmp_path,
    )
    try:
        assert dialog.table.rowCount() == 2
        assert dialog.index_candidate.count() >= 2
        dialog._accept_review()
        assert dialog.commit_result is not None
        assert dialog.commit_result.schema.curves
        assert dialog.commit_result.custom_profile.revision == 1
    finally:
        dialog.close()
        app.processEvents()
