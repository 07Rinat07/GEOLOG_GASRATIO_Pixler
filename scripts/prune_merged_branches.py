"""Prune already merged temporary PR branches only after a green main Release gate.

This is invoked by workflow_run on the trusted default branch, not from PR code.
"""
from __future__ import annotations

import json
import os
from http.client import HTTPSConnection
from urllib.parse import quote, urlencode

_TEMP_PREFIXES = ("codex/", "fix/")
_API_HOST = "api.github.com"


def eligible_merged_branch(
    branch: dict[str, object],
    pulls: list[dict[str, object]],
    repository: str,
) -> str | None:
    """Return a merged commit to verify, or refuse branch deletion."""

    name = branch.get("name")
    commit = branch.get("commit")
    if (
        not isinstance(name, str)
        or not name.startswith(_TEMP_PREFIXES)
        or branch.get("protected") is not False
        or not isinstance(commit, dict)
        or not isinstance(commit.get("sha"), str)
    ):
        return None
    sha = commit["sha"]
    if any(pull.get("state") == "open" for pull in pulls):
        return None
    for pull in pulls:
        head = pull.get("head")
        base = pull.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            continue
        head_repo = head.get("repo")
        if (
            pull.get("state") == "closed"
            and pull.get("merged_at") is not None
            and isinstance(head_repo, dict)
            and head_repo.get("full_name") == repository
            and head.get("ref") == name
            and head.get("sha") == sha
            and base.get("ref") == "main"
            and isinstance(pull.get("merge_commit_sha"), str)
        ):
            return pull["merge_commit_sha"]
    return None


class GitHub:
    def __init__(self, repository: str, token: str) -> None:
        self.root = f"/repos/{repository}"
        self.token = token

    def request(self, method: str, path: str) -> object:
        connection = HTTPSConnection(_API_HOST, timeout=25)
        try:
            connection.request(
                method,
                self.root + path,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response = connection.getresponse()
            payload = response.read()
            if not 200 <= response.status < 300:
                raise RuntimeError(f"GitHub API {method} failed: HTTP {response.status}")
        finally:
            connection.close()
        return json.loads(payload) if payload else None

    def all_pages(self, path: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 21):
            chunk = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(chunk, list):
                raise RuntimeError("Expected a paginated GitHub collection")
            items.extend(chunk)
            if len(chunk) < 100:
                return items
        # Never prune from an incomplete list.
        raise RuntimeError("GitHub pagination safety limit reached")


def prune(github: GitHub, *, repository: str, verified_sha: str) -> int:
    """Perform deletion only if the exact successful main SHA still matches."""

    main = github.request("GET", "/branches/main")
    if not isinstance(main, dict) or main.get("commit", {}).get("sha") != verified_sha:
        print("Main moved since the green Release gate; no branches deleted")
        return 0

    branches = github.all_pages("/branches")
    owner = repository.split("/", 1)[0]
    removed = 0
    for candidate in branches:
        name = candidate.get("name")
        if not isinstance(name, str) or not name.startswith(_TEMP_PREFIXES):
            continue
        query = urlencode({"head": f"{owner}:{name}", "state": "all"})
        pulls = github.all_pages(f"/pulls?{query}")
        merged_sha = eligible_merged_branch(candidate, pulls, repository)
        if merged_sha is None:
            print(f"Retained: {name} (not verified merged or still active)")
            continue

        # Verify the merge commit is actually contained in current main.
        comparison = github.request(
            "GET", f"/compare/{quote(merged_sha, safe='')}...{quote(verified_sha, safe='')}"
        )
        if not isinstance(comparison, dict) or comparison.get("status") not in (
            "ahead", "identical"
        ):
            print(f"Retained: {name} (merge commit not in current main)")
            continue

        current_main = github.request("GET", "/branches/main")
        current_branch = github.request(
            "GET", f"/branches/{quote(name, safe='/')}"
        )
        if (
            not isinstance(current_main, dict)
            or current_main.get("commit", {}).get("sha") != verified_sha
            or not isinstance(current_branch, dict)
            or current_branch.get("commit", {}).get("sha")
            != candidate["commit"]["sha"]
            or current_branch.get("protected") is not False
        ):
            print(f"Retained: {name} (refs changed during recheck)")
            continue

        github.request("DELETE", f"/git/refs/heads/{quote(name, safe='/')}")
        removed += 1
        print(f"Deleted merged temporary branch: {name}")
    return removed


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    sha = os.environ["VERIFIED_MAIN_SHA"]
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha.lower()):
        raise ValueError("VERIFIED_MAIN_SHA must be a full Git commit SHA")
    if "/" not in repo:
        raise ValueError("GITHUB_REPOSITORY must be owner/repo")
    count = prune(GitHub(repo, token), repository=repo, verified_sha=sha)
    print(f"Pruned {count} merged temporary branch(es)")


if __name__ == "__main__":
    main()
