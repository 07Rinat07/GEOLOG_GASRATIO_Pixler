from __future__ import annotations

from pathlib import Path


def replace_if_present(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if old in content:
        path.write_text(content.replace(old, new, 1), encoding="utf-8")


def replace_required(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected fragment not found in {path}: {old!r}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_if_present(
    Path("src/geoworkbench/files/document_service.py"),
    "from typing import Any\n\n",
    "",
)
replace_required(
    Path("src/geoworkbench/files/archive_service.py"),
    "archive.extractall(path=staging)",
    "archive.extract(path=staging, targets=archive.getnames())",
)
