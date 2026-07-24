from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar


CandidateT = TypeVar("CandidateT")
SnapshotT = TypeVar("SnapshotT")


@dataclass(frozen=True, slots=True)
class ReversibleApplyError(RuntimeError):
    """An apply failed and the previous state was restored, or rollback also failed."""

    operation_error: Exception
    rollback_error: Exception | None = None

    @property
    def restored(self) -> bool:
        return self.rollback_error is None

    def __str__(self) -> str:
        if self.rollback_error is None:
            return str(self.operation_error)
        return f"{self.operation_error}; rollback: {self.rollback_error}"


def apply_reversibly(
    *,
    candidate: CandidateT,
    snapshot: SnapshotT,
    render_candidate: Callable[[CandidateT], None],
    commit_candidate: Callable[[CandidateT], None],
    restore_snapshot: Callable[[SnapshotT], None],
) -> None:
    """Render a candidate before committing it and restore on any failure.

    Rendering is intentionally first because Qt widget construction is the most
    failure-prone part of applying a large form.  The project/session state is not
    committed until the candidate has rendered successfully.  A later commit error
    is handled by the same rollback path.
    """

    try:
        render_candidate(candidate)
        commit_candidate(candidate)
    except Exception as operation_error:
        rollback_error: Exception | None = None
        try:
            restore_snapshot(snapshot)
        except Exception as exc:  # rollback failures must not hide the original cause
            rollback_error = exc
        raise ReversibleApplyError(operation_error, rollback_error) from operation_error
