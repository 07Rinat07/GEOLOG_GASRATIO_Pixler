from __future__ import annotations

from pathlib import Path

from geoworkbench.forms.layout_transaction import ReversibleApplyError, apply_reversibly


ROOT = Path(__file__).resolve().parents[1]


def test_reversible_apply_restores_once_from_model_snapshot() -> None:
    calls: list[tuple[str, str]] = []

    def render(candidate: str) -> None:
        calls.append(("render", candidate))
        raise RuntimeError("render failed")

    def commit(candidate: str) -> None:
        calls.append(("commit", candidate))

    def restore(snapshot: str) -> None:
        calls.append(("restore", snapshot))

    try:
        apply_reversibly(
            candidate="candidate",
            snapshot="working-model",
            render_candidate=render,
            commit_candidate=commit,
            restore_snapshot=restore,
        )
    except ReversibleApplyError as exc:
        assert str(exc.operation_error) == "render failed"
        assert exc.rollback_error is None
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("apply_reversibly must report the failed render")

    assert calls == [("render", "candidate"), ("restore", "working-model")]


def test_curve_header_disposal_stops_deferred_qt_callbacks() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "self._disposed = False" in source
    assert "def dispose(self) -> None:" in source
    assert "self._range_commit_timer.stop()" in source
    assert "control.blockSignals(True)" in source
    assert "if self._disposed or self._loading:" in source
    assert "def _dispose_curve_header_editors(self) -> None:" in source
    assert "rendered.widget.prepare_for_disposal()" in source
    assert "def is_rebuilding_layout(self) -> bool:" in source


def test_form_manager_uses_one_model_rollback_not_two_widget_restores() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert "rollback_snapshot: _TabletFormSnapshot | None = None" in source
    assert "dialog.selected_form, rollback_snapshot=snapshot" in source
    assert "snapshot = rollback_snapshot or self._capture_tablet_form_snapshot()" in source
    assert "previous_transaction_state = self._form_layout_transaction_active" in source
    assert "widgets from the failed candidate are never reused" in source
    assert "self._form_layout_transaction_active or self.tablet_view.is_rebuilding_layout" in source

    # The accepted manager path must not call a second restore after the
    # reversible apply has already restored the model snapshot.
    manager_block = source[source.index("    def show_form_manager") : source.index(
        "    def _choose_and_import_skf"
    )]
    final_apply = "        self.apply_form_to_tablet(\n            dialog.selected_form"
    accepted_block = manager_block[manager_block.index(final_apply) :]
    assert "_restore_tablet_form_snapshot" not in accepted_block
