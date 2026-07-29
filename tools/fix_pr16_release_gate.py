from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected fragment not found in {path}: {old!r}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    Path("src/geoworkbench/files/document_service.py"),
    "from typing import Any\n\n",
    "",
)
replace_once(
    Path("src/geoworkbench/files/archive_service.py"),
    "                    archive.extractall(path=staging)  # nosec B202 - 7Z paths were validated by _validate_entries\n",
    "                    archive.extract(path=staging, targets=archive.getnames())\n",
)
