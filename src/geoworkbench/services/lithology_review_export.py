"""Save an operator review as a detached record, never as geological approval."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.lithology_source_mapping import (
    ReviewedLithologyMapping, evaluate_lithology_mapping,
)


def export_lithology_review(
    session: ProjectSession, mapping: ReviewedLithologyMapping, destination: str | Path,
    *, overwrite: bool = False,
) -> Path:
    """Publish a UTF-8 JSON record atomically after rechecking source freshness.

    Source fingerprints describe the reviewed input, not a signature or approval.
    This file cannot reactivate a mapping and does not modify project storage.
    """
    evaluate_lithology_mapping(session, mapping)
    target = Path(destination)
    if target.suffix.casefold() != ".json":
        raise ValueError("Lithology review requires a JSON destination")
    payload = {
        "schema_version": 1,
        "artifact_kind": "lithology_mapping_review",
        "review_status": "operator_review_not_geological_approval",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": session.project.project_id,
        "mapping": asdict(mapping),
    }
    # Serialize before creating any file; enum values are explicit strings.
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=target.parent,
            prefix=".lithology-review-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        # A file chooser or write may outlive an edit to the source.
        evaluate_lithology_mapping(session, mapping)
        if overwrite:
            os.replace(temporary, target)
        else:
            # Same-directory hard-link publication is atomic and refuses an
            # existing name, including one created after the write started.
            os.link(temporary, target)
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
