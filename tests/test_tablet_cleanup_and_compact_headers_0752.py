from __future__ import annotations

from pathlib import Path

from geoworkbench.services.import_diagnostics import policy_diagnostic
from geoworkbench.tablet.track_lifecycle import TrackLifecycleCoordinator


ROOT = Path(__file__).resolve().parents[1]


def test_dispose_entries_continues_after_one_stale_qt_wrapper() -> None:
    coordinator = TrackLifecycleCoordinator()
    disposed: list[str] = []
    failures: list[tuple[str, str]] = []

    def dispose(entry: str) -> None:
        disposed.append(entry)
        if entry == "rendered:dead":
            raise RuntimeError("Internal C++ object already deleted")

    released = coordinator.dispose_entries(
        {
            "first": "rendered:first",
            "dead": "rendered:dead",
            "last": "rendered:last",
        },
        dispose,
        on_error=lambda track_id, exc: failures.append((track_id, str(exc))),
    )

    assert released == ("first", "dead", "last")
    assert disposed == ["rendered:last", "rendered:dead", "rendered:first"]
    assert failures == [("dead", "Internal C++ object already deleted")]


def test_tablet_cleanup_validates_shiboken_objects_before_event_filter_calls() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "from shiboken6 import isValid as shiboken_is_valid" in source
    assert "def _qt_object_is_alive(" in source
    assert "def _safe_remove_event_filter(" in source
    assert "if not _qt_object_is_alive(target):" in source
    assert "rendered.widget.prepare_for_disposal()" in source
    assert "target.removeEventFilter(self)" not in source
    assert "on_error=lambda track_id, exc: log_exception(" in source


def test_curve_headers_use_compact_professional_height_budget() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "CURVE_HEADER_EDITOR_HEIGHT = 58" in source
    assert "CURVE_HEADER_LABEL_HEIGHT = 40" in source
    assert "len(rows) * CURVE_HEADER_EDITOR_HEIGHT" in source
    assert "min(360" in source
    assert 'separator = QLabel("—")' in source
    assert "self.scale.setMaximumWidth(42)" in source
    assert "self.unit.setMaximumWidth(56)" in source


def test_las_spacing_warnings_have_specific_non_destructive_actions(tmp_path: Path) -> None:
    duplicate = policy_diagnostic(
        tmp_path / "well.las",
        code="duplicate-index-values",
        message="duplicates",
        warning=True,
    )
    irregular = policy_diagnostic(
        tmp_path / "well.las",
        code="non-uniform-step",
        message="step",
        warning=True,
    )
    gaps = policy_diagnostic(
        tmp_path / "well.las",
        code="index-gaps",
        message="gaps",
        warning=True,
    )

    assert "keep all" in duplicate.suggested_action.casefold()
    assert "0.2 m" in irregular.suggested_action
    assert "missing intervals" in gaps.suggested_action.casefold()
    assert duplicate.blocking is False
    assert irregular.blocking is False
    assert gaps.blocking is False
