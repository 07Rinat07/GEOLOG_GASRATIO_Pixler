from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

import numpy as np

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleScopeKind,
)
from geoworkbench.domain.models import CalculationState, Dataset, MasterlogTemplate
from geoworkbench.project.document_bundle_preflight import (
    DocumentBundlePreflightCategory,
    DocumentBundlePreflightIssue,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    LoadedDocumentBundleSnapshot,
)
from geoworkbench.services.las_parameter_resolver import LasParameterResolver


class BundleSnapshotLoader(Protocol):
    def load(
        self,
        binding: DocumentBundleSnapshotBinding,
    ) -> LoadedDocumentBundleSnapshot:
        """Load the verified persisted project revision."""


@dataclass(slots=True)
class MasterlogBundlePreflightValidator:
    snapshot_loader: BundleSnapshotLoader

    def validate(
        self,
        snapshot: DocumentBundleSnapshotBinding,
        output: DocumentBundleOutputSpec,
    ) -> tuple[DocumentBundlePreflightIssue, ...]:
        issues: list[DocumentBundlePreflightIssue] = []
        if output.exporter_kind != "masterlog":
            return ()

        if output.file_format is not DocumentBundleOutputFormat.PDF:
            return (
                _issue(
                    output,
                    "masterlog.format",
                    "Masterlog final output currently supports PDF only",
                    DocumentBundlePreflightCategory.CONFIGURATION,
                ),
            )
        if output.dataset_id is None:
            return (
                _issue(
                    output,
                    "masterlog.dataset_missing",
                    "Masterlog output requires a bound dataset",
                    DocumentBundlePreflightCategory.DATA,
                ),
            )

        loaded = self.snapshot_loader.load(snapshot)
        project = loaded.document.project
        well = project.wells.get(snapshot.request.well_id)
        if well is None:
            return (
                _issue(
                    output,
                    "masterlog.well_missing",
                    "The selected well is missing from the persisted snapshot",
                    DocumentBundlePreflightCategory.DATA,
                ),
            )

        dataset = well.datasets.get(output.dataset_id)
        if dataset is None:
            return (
                _issue(
                    output,
                    "masterlog.dataset_not_found",
                    f"Dataset {output.dataset_id!r} is missing from the selected well",
                    DocumentBundlePreflightCategory.DATA,
                ),
            )
        template = project.masterlog_templates.get(output.source_id)
        if template is None:
            return (
                _issue(
                    output,
                    "masterlog.template_not_found",
                    f"Masterlog template {output.source_id!r} is missing from the snapshot",
                    DocumentBundlePreflightCategory.CONFIGURATION,
                ),
            )

        depth_range = _dataset_depth_range(dataset)
        if depth_range is None:
            issues.append(
                _issue(
                    output,
                    "masterlog.depth_range",
                    "The bound dataset has no finite printable depth range",
                    DocumentBundlePreflightCategory.DATA,
                )
            )
        else:
            issues.extend(_scope_issues(snapshot, output, depth_range))

        if (
            template.page_format.casefold() == "roll"
            and "landscape" in snapshot.request.orientations
        ):
            issues.append(
                _issue(
                    output,
                    "masterlog.roll_landscape",
                    "Roll Masterlog output supports portrait orientation only",
                    DocumentBundlePreflightCategory.CONFIGURATION,
                )
            )

        issues.extend(_dependency_issues(output, template, dataset))
        return tuple(issues)


def _dataset_depth_range(dataset: Dataset) -> tuple[float, float] | None:
    try:
        values = np.asarray(dataset.active_index.values, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return None
    top = float(np.min(finite))
    bottom = float(np.max(finite))
    if not isfinite(top) or not isfinite(bottom) or bottom <= top:
        return None
    return top, bottom


def _scope_issues(
    snapshot: DocumentBundleSnapshotBinding,
    output: DocumentBundleOutputSpec,
    available: tuple[float, float],
) -> tuple[DocumentBundlePreflightIssue, ...]:
    scope = snapshot.request.scope
    if scope.kind is DocumentBundleScopeKind.WHOLE_WELL:
        return ()
    if scope.top_depth is None or scope.bottom_depth is None:
        return (
            _issue(
                output,
                "masterlog.scope_unresolved",
                "The requested depth interval has no resolved bounds",
                DocumentBundlePreflightCategory.DATA,
            ),
        )
    if scope.top_depth < available[0] or scope.bottom_depth > available[1]:
        return (
            _issue(
                output,
                "masterlog.scope_outside_dataset",
                (
                    f"Requested interval {scope.top_depth:g}–{scope.bottom_depth:g} "
                    f"is outside dataset range {available[0]:g}–{available[1]:g}"
                ),
                DocumentBundlePreflightCategory.DATA,
            ),
        )
    return ()


def _dependency_issues(
    output: DocumentBundleOutputSpec,
    template: MasterlogTemplate,
    dataset: Dataset,
) -> tuple[DocumentBundlePreflightIssue, ...]:
    targets = tuple(
        dict.fromkeys(
            mnemonic.strip().upper()
            for column in template.columns
            for mnemonic in column.curve_mnemonics
            if mnemonic.strip()
        )
    )
    if not targets:
        return ()

    resolved = _resolved_curve_ids(template, dataset, targets)
    missing = tuple(target for target in targets if target not in resolved)
    issues: list[DocumentBundlePreflightIssue] = []
    if missing:
        issues.append(
            _issue(
                output,
                "masterlog.dependencies_missing",
                "Unresolved required Masterlog curves: " + ", ".join(missing),
                DocumentBundlePreflightCategory.DEPENDENCY,
            )
        )

    invalid_states: list[str] = []
    for target, curve_id in resolved.items():
        curve = dataset.curves.get(curve_id)
        if curve is None:
            continue
        if curve.state in {
            CalculationState.STALE,
            CalculationState.CALCULATING,
            CalculationState.ERROR,
        }:
            invalid_states.append(f"{target}:{curve.state.value}")
    if invalid_states:
        issues.append(
            _issue(
                output,
                "masterlog.dependencies_not_current",
                "Masterlog curves are not current: " + ", ".join(sorted(invalid_states)),
                DocumentBundlePreflightCategory.DEPENDENCY,
            )
        )
    return tuple(issues)


def _resolved_curve_ids(
    template: MasterlogTemplate,
    dataset: Dataset,
    targets: tuple[str, ...],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    profiles = template.properties.get("dataset_curve_bindings", {})
    if isinstance(profiles, dict):
        raw = profiles.get(dataset.dataset_id, {})
        if isinstance(raw, dict):
            for mnemonic, curve_id in raw.items():
                canonical = str(mnemonic).strip().upper()
                if (
                    canonical in targets
                    and isinstance(curve_id, str)
                    and curve_id in dataset.curves
                ):
                    resolved[canonical] = curve_id

    for target in targets:
        if target in resolved:
            continue
        direct = dataset.curve_by_mnemonic(target)
        if direct is not None:
            resolved[target] = direct.metadata.curve_id

    remaining = set(targets) - set(resolved)
    if remaining:
        resolution = LasParameterResolver().resolve_dataset(
            dataset,
            targets=remaining,
            minimum_confidence=0.65,
        )
        for canonical, match in resolution.matches.items():
            if canonical in remaining and match.curve_id in dataset.curves:
                resolved[canonical] = match.curve_id
    return resolved


def _issue(
    output: DocumentBundleOutputSpec,
    code: str,
    message: str,
    category: DocumentBundlePreflightCategory,
) -> DocumentBundlePreflightIssue:
    return DocumentBundlePreflightIssue(
        code=code,
        message=message,
        category=category,
        output_id=output.output_id,
    )
