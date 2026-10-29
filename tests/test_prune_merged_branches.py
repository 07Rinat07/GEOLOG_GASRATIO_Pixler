from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.prune_merged_branches import eligible_merged_branch, prune

REPOSITORY = "07Rinat07/GEOLOG_GASRATIO_Pixler"
MAIN_SHA = "a" * 40
BRANCH_SHA = "b" * 40
MERGE_SHA = "c" * 40


def _branch(name: str = "codex/merged", *, protected: bool = False) -> dict:
    return {"name": name, "commit": {"sha": BRANCH_SHA}, "protected": protected}


def _pull(name: str = "codex/merged") -> dict:
    return {
        "state": "closed",
        "merged_at": "2026-10-29T01:00:00Z",
        "merge_commit_sha": MERGE_SHA,
        "head": {
            "sha": BRANCH_SHA,
            "ref": name,
            "repo": {"full_name": REPOSITORY},
        },
        "base": {"ref": "main"},
    }


@pytest.mark.parametrize("name", ("codex/merged", "fix/merged", "feat/merged"))
def test_cleanup_accepts_verified_temporary_pr_prefixes(name: str) -> None:
    assert eligible_merged_branch(_branch(name), [_pull(name)], REPOSITORY) == MERGE_SHA
    assert eligible_merged_branch(
        _branch(name, protected=True), [_pull(name)], REPOSITORY
    ) is None
    open_pr = _pull(name)
    open_pr.update(state="open", merged_at=None)
    assert eligible_merged_branch(_branch(name), [_pull(name), open_pr], REPOSITORY) is None


def test_cleanup_accepts_only_exact_merged_temporary_branch() -> None:
    assert eligible_merged_branch(_branch(), [_pull()], REPOSITORY) == MERGE_SHA


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b, p: b.update(name="main"),
        lambda b, p: b.update(name="release/1.0"),
        lambda b, p: b.update(protected=True),
        lambda b, p: b["commit"].update(sha="d" * 40),
        lambda b, p: p[0].update(state="open"),
        lambda b, p: p[0].update(merged_at=None),
        lambda b, p: p[0].update(merge_commit_sha=None),
        lambda b, p: p[0]["head"].update(sha="e" * 40),
        lambda b, p: p[0]["head"].update(ref="codex/another"),
        lambda b, p: p[0]["head"]["repo"].update(full_name="another/fork"),
        lambda b, p: p[0]["base"].update(ref="develop"),
    ],
)
def test_cleanup_rejects_unverified_branch(mutation) -> None:
    branch = deepcopy(_branch())
    pulls = [_pull()]
    mutation(branch, pulls)
    assert eligible_merged_branch(branch, pulls, REPOSITORY) is None


def test_cleanup_rejects_even_one_open_pr_on_same_branch() -> None:
    open_pr = _pull()
    open_pr.update(state="open", merged_at=None)
    assert eligible_merged_branch(_branch(), [_pull(), open_pr], REPOSITORY) is None


class StubGitHub:
    def __init__(
        self,
        *,
        main_sha: str = MAIN_SHA,
        ref_sha: str = BRANCH_SHA,
        compare_status: str = "ahead",
        branch_name: str = "codex/merged",
    ) -> None:
        self.main_sha = main_sha
        self.ref_sha = ref_sha
        self.compare_status = compare_status
        self.branch_name = branch_name
        self.deleted: list[str] = []
        self.requests: list[tuple[str, str]] = []

    def request(self, method: str, path: str) -> object:
        self.requests.append((method, path))
        if method == "DELETE":
            self.deleted.append(path)
            return None
        if path == "/branches/main":
            return {"commit": {"sha": self.main_sha}}
        if path == f"/branches/{self.branch_name}":
            return {"commit": {"sha": self.ref_sha}, "protected": False}
        if path == f"/compare/{MERGE_SHA}...{MAIN_SHA}":
            return {"status": self.compare_status}
        raise AssertionError(f"Unexpected request {method} {path}")

    def all_pages(self, path: str) -> list[dict]:
        if path == "/branches":
            return [_branch(self.branch_name)]
        if path.startswith("/pulls?"):
            assert "state=all" in path
            return [_pull(self.branch_name)]
        raise AssertionError(path)


@pytest.mark.parametrize(
    "name", ("codex/merged", "fix/merged", "feat/merged")
)
def test_cleanup_deletes_only_exact_verified_temporary_prefixes(name: str) -> None:
    api = StubGitHub(branch_name=name)
    assert prune(api, repository=REPOSITORY, verified_sha=MAIN_SHA) == 1
    assert api.deleted == [f"/git/refs/heads/{name}"]


def test_cleanup_deletes_only_after_green_main_and_merged_commit() -> None:
    api = StubGitHub()
    assert prune(api, repository=REPOSITORY, verified_sha=MAIN_SHA) == 1
    assert api.deleted == ["/git/refs/heads/codex/merged"]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"main_sha": "x" * 40}, 0),
        ({"ref_sha": "y" * 40}, 0),
        ({"compare_status": "diverged"}, 0),
        ({"compare_status": "behind"}, 0),
    ],
)
def test_cleanup_preserves_refs_without_complete_proof(
    kwargs: dict, expected: int
) -> None:
    api = StubGitHub(**kwargs)
    assert prune(api, repository=REPOSITORY, verified_sha=MAIN_SHA) == expected
    assert api.deleted == []

@pytest.mark.parametrize('method,payload', [('GET', b'{"ok": true}'), ('DELETE', b'')])
def test_github_transport_supplies_required_user_agent(monkeypatch, method, payload):
    from scripts import prune_merged_branches as cleanup

    class Connection:
        closed = False

        def request(self, method, path, headers):
            self.status = 200 if headers.get('User-Agent') else 403

        def getresponse(self):
            return self

        def read(self):
            return payload

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(cleanup, 'HTTPSConnection', lambda *args, **kwargs: connection)
    result = cleanup.GitHub(REPOSITORY, 'test-token').request(method, '/branches/main')
    assert result == ({'ok': True} if payload else None)
    assert connection.closed
