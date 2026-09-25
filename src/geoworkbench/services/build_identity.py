from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import metadata
import json
import os
from pathlib import Path
import re
from typing import Mapping


_DISTRIBUTION_NAME = "geolog-gasratio-pixler"
_ENVIRONMENT_COMMIT_KEYS = (
    "GEOLOG_BUILD_COMMIT",
    "GITHUB_SHA",
    "CI_COMMIT_SHA",
)
_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
_UNKNOWN_COMMIT = "unknown"


@dataclass(frozen=True, slots=True)
class BuildIdentity:
    """Immutable support identity for one application build."""

    version: str
    commit: str = _UNKNOWN_COMMIT
    source: str = "unknown"

    def __post_init__(self) -> None:
        version = str(self.version).strip()
        source = str(self.source).strip()
        if not version:
            raise ValueError("build version must not be empty")
        if not source:
            raise ValueError("build identity source must not be empty")
        commit = _UNKNOWN_COMMIT
        if self.commit != _UNKNOWN_COMMIT:
            normalized_commit = _normalize_commit(self.commit)
            if normalized_commit is None:
                raise ValueError("build commit must be a 7-64 character hexadecimal SHA")
            commit = normalized_commit
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "commit", commit)
        object.__setattr__(self, "source", source)

    @property
    def short_commit(self) -> str:
        return self.commit[:12] if self.commit != _UNKNOWN_COMMIT else _UNKNOWN_COMMIT

    @property
    def display(self) -> str:
        return f"{self.version}+{self.short_commit}"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _normalize_commit(value: object) -> str | None:
    candidate = str(value).strip()
    if not _COMMIT_PATTERN.fullmatch(candidate):
        return None
    return candidate.lower()


def _distribution_commit(distribution_name: str) -> str | None:
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError:
        return None
    raw_direct_url = distribution.read_text("direct_url.json")
    if not raw_direct_url:
        return None
    try:
        direct_url = json.loads(raw_direct_url)
    except (TypeError, ValueError):
        return None
    if not isinstance(direct_url, dict):
        return None
    vcs_info = direct_url.get("vcs_info")
    if not isinstance(vcs_info, dict):
        return None
    return _normalize_commit(vcs_info.get("commit_id"))


def _git_directory(marker: Path) -> Path | None:
    if marker.is_dir():
        return marker
    if not marker.is_file():
        return None
    try:
        descriptor = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir:"
    if not descriptor.lower().startswith(prefix):
        return None
    raw_path = descriptor[len(prefix) :].strip()
    if not raw_path:
        return None
    git_directory = Path(raw_path)
    if not git_directory.is_absolute():
        git_directory = marker.parent / git_directory
    return git_directory.resolve()


def _checkout_commit(start: Path) -> str | None:
    current = start if start.is_dir() else start.parent
    for directory in (current, *current.parents):
        git_directory = _git_directory(directory / ".git")
        if git_directory is None:
            continue
        try:
            head = (git_directory / "HEAD").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        direct = _normalize_commit(head)
        if direct is not None:
            return direct
        if not head.startswith("ref:"):
            return None
        reference = head.partition(":")[2].strip()
        if not reference:
            return None
        try:
            ref_value = (git_directory / reference).read_text(encoding="utf-8").strip()
        except OSError:
            ref_value = ""
        normalized = _normalize_commit(ref_value)
        if normalized is not None:
            return normalized
        try:
            packed_refs = (git_directory / "packed-refs").read_text(encoding="utf-8")
        except OSError:
            return None
        for line in packed_refs.splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            commit, separator, name = line.partition(" ")
            if separator and name.strip() == reference:
                return _normalize_commit(commit)
        return None
    return None


def resolve_build_identity(
    application_version: str,
    *,
    environ: Mapping[str, str] | None = None,
    distribution_name: str = _DISTRIBUTION_NAME,
    checkout_start: Path | None = None,
) -> BuildIdentity:
    """Resolve build identity without invoking Git or exposing environment contents."""

    environment = os.environ if environ is None else environ
    for key in _ENVIRONMENT_COMMIT_KEYS:
        commit = _normalize_commit(environment.get(key, ""))
        if commit is not None:
            return BuildIdentity(
                version=str(application_version),
                commit=commit,
                source=f"environment:{key}",
            )

    commit = _distribution_commit(distribution_name)
    if commit is not None:
        return BuildIdentity(
            version=str(application_version),
            commit=commit,
            source="package-metadata",
        )

    commit = _checkout_commit(
        checkout_start if checkout_start is not None else Path(__file__).resolve()
    )
    if commit is not None:
        return BuildIdentity(
            version=str(application_version),
            commit=commit,
            source="git-checkout",
        )

    return BuildIdentity(version=str(application_version))


__all__ = ["BuildIdentity", "resolve_build_identity"]
