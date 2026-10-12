#!/usr/bin/env python3
"""Fetch pinned open upstream format fixtures with exact Git-blob verification.

Standard library only; never executes source files or mutates original data.
Download is an explicit maintenance step. CI uses --check without network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "external_formats"
MANIFEST = CORPUS / "manifest.json"
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_REPOSITORIES = frozenset({"kinverarity1/lasio", "equinor/dlisio", "equinor/segyio"})
ALLOWED_SCENARIOS = frozenset({"reference", "exploratory", "edge_case", "negative"})


def blob_sha1(content: bytes) -> str:
    """Git SHA-1 includes a typed, byte-length-prefixed blob header."""
    header = f"blob {len(content)}\\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _read_manifest() -> list[dict[str, object]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("fixtures"), list):
        raise ValueError("Unsupported fixture manifest schema")
    return manifest["fixtures"]


def _validate(entry: dict[str, object]) -> tuple[Path, str, int, str]:
    destination = entry.get("destination")
    source = entry.get("source_path")
    repository = entry.get("repository")
    revision = entry.get("revision")
    size = entry.get("size_bytes")
    sha = entry.get("git_blob_sha")
    scenario = entry.get("scenario")
    if not all(isinstance(value, str) and value for value in
               (destination, source, repository, revision, sha)):
        raise ValueError("Fixture requires strings for source, destination and identity")
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_FILE_SIZE:
        raise ValueError("Fixture size must be a bounded positive integer")
    if repository not in ALLOWED_REPOSITORIES or scenario not in ALLOWED_SCENARIOS:
        raise ValueError("Unapproved source repository or scenario")
    if len(revision) != 40 or len(sha) != 40 or any(
        character not in "0123456789abcdef" for value in (revision, sha) for character in value
    ):
        raise ValueError("Revision and blob hashes must be lowercase SHA-1")
    for value in (destination, source):
        parts = PurePosixPath(value)
        if parts.is_absolute() or ".." in parts.parts or "\\\\" in value:
            raise ValueError(f"Unsafe relative fixture path: {value!r}")
    target = CORPUS / destination
    # Every source URL is pinned to a commit and a fixed approved GitHub org.
    url = (
        "https://raw.githubusercontent.com/"
        + repository + "/" + revision + "/"
        + "/".join(quote(segment, safe="") for segment in PurePosixPath(source).parts)
    )
    return target, url, size, sha


def _verify(path: Path, expected_size: int, expected_git_sha: str) -> str:
    payload = path.read_bytes()
    if len(payload) != expected_size or blob_sha1(payload) != expected_git_sha:
        raise ValueError(f"Content mismatch: {path} (file not trusted)")
    return hashlib.sha256(payload).hexdigest()


def _download(url: str, max_size: int) -> bytes:
    request = Request(url, headers={"User-Agent": "GEOLOG-fixture-audit/1.0"})
    with urlopen(request, timeout=35) as response:
        if response.geturl().split("/")[2] != "raw.githubusercontent.com":
            raise ValueError("Unexpected fixture download host")
        payload = response.read(max_size + 1)
    if len(payload) > max_size:
        raise ValueError("Fixture download exceeded manifest size")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed fixtures offline")
    parser.add_argument("--group", choices=["all", "las", "dlis", "lis79", "segy", "su"],
                        default="all")
    args = parser.parse_args(argv)
    entries = _read_manifest()
    selected = [entry for entry in entries
                if args.group == "all" or str(entry["destination"]).split("/")[0] == args.group]
    if not selected:
        raise ValueError(f"No fixtures for group {args.group}")
    seen: set[Path] = set()
    for item in selected:
        target, url, size, git_sha = _validate(item)
        if target in seen:
            raise ValueError(f"Duplicate fixture path: {target}")
        seen.add(target)
        if args.check or target.exists():
            try:
                digest = _verify(target, size, git_sha)
                print(f"OK {target.relative_to(CORPUS)} SHA256={digest}")
                continue
            except (OSError, ValueError):
                if args.check:
                    raise
                # Re-fetch only when explicitly downloading; never accept changed bytes.
        if args.check:
            raise FileNotFoundError(f"Missing committed fixture: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = _download(url, size)
        if len(payload) != size or blob_sha1(payload) != git_sha:
            raise ValueError(f"Untrusted payload (size/blob mismatch): {url}")
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as scratch:
            staged = Path(scratch.name)
            scratch.write(payload)
        try:
            os.replace(staged, target)
        finally:
            staged.unlink(missing_ok=True)
        digest = _verify(target, size, git_sha)
        print(f"DOWNLOADED {target.relative_to(CORPUS)} SHA256={digest}")
        time.sleep(0.05)
    print(f"Verified {len(selected)} files; raw sources remain immutable.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Fixture validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
