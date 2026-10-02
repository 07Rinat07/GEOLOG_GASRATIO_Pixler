from __future__ import annotations

import json
from typing import TYPE_CHECKING

from geoworkbench.services.fluid_phase_contract import fluid_phase_from_hypothesis

if TYPE_CHECKING:
    from geoworkbench.services.hydrocarbon_interpretation_legacy import (
        HydrocarbonInterpretationReport,
    )


CLASSIFICATION_AUDIT_SCHEMA = "geolog.interpretation.classification.v1"
CLASSIFICATION_AUDIT_META = "geolog-classification-audit"
CLASSIFICATION_AUDIT_SHEET = "_classification_audit"
CLASSIFICATION_AUDIT_DOCX_PART = "customXml/geolog-classification-audit.xml"


def interpretation_classification_audit(
    report: HydrocarbonInterpretationReport,
) -> dict[str, object]:
    """Preserve detailed classification independently of the bounded visible phase."""
    interval = report.analysis_depth_interval
    return {
        "schema": CLASSIFICATION_AUDIT_SCHEMA,
        "dataset_id": report.dataset_id,
        "report_profile": report.report_profile,
        "depth_unit": report.depth_unit,
        "analysis_depth_interval": (
            [interval.top_depth, interval.bottom_depth] if interval is not None else None
        ),
        "candidates": [
            {
                "status": status,
                "top_depth": candidate.top_depth,
                "bottom_depth": candidate.bottom_depth,
                "fluid_hypothesis": candidate.fluid_hypothesis,
                "phase": fluid_phase_from_hypothesis(candidate.fluid_hypothesis).value,
                "evidence": list(candidate.evidence),
            }
            for status, candidates in (
                ("active", report.candidates),
                ("suppressed", report.suppressed_candidates),
            )
            for candidate in candidates
        ],
    }


def interpretation_classification_audit_json(report: HydrocarbonInterpretationReport) -> str:
    return json.dumps(
        interpretation_classification_audit(report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
