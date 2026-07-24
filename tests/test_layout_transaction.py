from __future__ import annotations

import pytest

from geoworkbench.forms.layout_transaction import ReversibleApplyError, apply_reversibly


def test_reversible_apply_commits_only_after_candidate_rendered() -> None:
    calls: list[str] = []

    apply_reversibly(
        candidate="new",
        snapshot="old",
        render_candidate=lambda value: calls.append(f"render:{value}"),
        commit_candidate=lambda value: calls.append(f"commit:{value}"),
        restore_snapshot=lambda value: calls.append(f"restore:{value}"),
    )

    assert calls == ["render:new", "commit:new"]


def test_reversible_apply_restores_snapshot_after_render_failure() -> None:
    calls: list[str] = []

    def render(_value: str) -> None:
        calls.append("render")
        raise RuntimeError("broken widget")

    with pytest.raises(ReversibleApplyError) as raised:
        apply_reversibly(
            candidate="new",
            snapshot="old",
            render_candidate=render,
            commit_candidate=lambda _value: calls.append("commit"),
            restore_snapshot=lambda value: calls.append(f"restore:{value}"),
        )

    assert calls == ["render", "restore:old"]
    assert raised.value.restored is True
    assert str(raised.value.operation_error) == "broken widget"


def test_reversible_apply_restores_snapshot_after_commit_failure() -> None:
    calls: list[str] = []

    def commit(_value: str) -> None:
        calls.append("commit")
        raise RuntimeError("session commit failed")

    with pytest.raises(ReversibleApplyError) as raised:
        apply_reversibly(
            candidate="new",
            snapshot="old",
            render_candidate=lambda _value: calls.append("render"),
            commit_candidate=commit,
            restore_snapshot=lambda value: calls.append(f"restore:{value}"),
        )

    assert calls == ["render", "commit", "restore:old"]
    assert raised.value.restored is True


def test_reversible_apply_preserves_original_and_rollback_errors() -> None:
    def fail_render(_value: str) -> None:
        raise RuntimeError("render failed")

    def fail_restore(_value: str) -> None:
        raise RuntimeError("rollback failed")

    with pytest.raises(ReversibleApplyError) as raised:
        apply_reversibly(
            candidate="new",
            snapshot="old",
            render_candidate=fail_render,
            commit_candidate=lambda _value: None,
            restore_snapshot=fail_restore,
        )

    assert raised.value.restored is False
    assert str(raised.value.operation_error) == "render failed"
    assert str(raised.value.rollback_error) == "rollback failed"
