from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.import_review import (
    ImportChannelOverride,
    ImportReviewController,
    ImportReviewPlan,
    ImportReviewValidationError,
)
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.services.uom_dictionary import QuantityClass


def _dataset() -> Dataset:
    dataset = Dataset(
        "dataset-review",
        "Review",
        DatasetKind.USER,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    dictionary = SemanticChannelDictionary()
    rop = dictionary.resolve("ROP", unit="m/h")
    pressure = dictionary.resolve("SPP", unit="psi")
    dataset.curves = {
        "rop": CurveData(
            CurveMetadata(
                "rop",
                "ROP",
                rop.canonical_mnemonic,
                "m/h",
                "Rate of penetration",
                dataset.dataset_id,
                semantic=rop,
            ),
            np.array([1.0, -999.25, 3.0]),
        ),
        "spp": CurveData(
            CurveMetadata(
                "spp",
                "SPP",
                pressure.canonical_mnemonic,
                "psi",
                "Standpipe pressure",
                dataset.dataset_id,
                semantic=pressure,
            ),
            np.array([100.0, 110.0, 120.0]),
        ),
    }
    return dataset


def test_initial_plan_preserves_loaded_semantic_snapshot() -> None:
    dataset = _dataset()
    controller = ImportReviewController()

    plan = controller.initial_plan(dataset)
    preview = controller.preview(dataset, plan)

    assert plan.active_index_id == dataset.active_index_id
    assert preview.error_count == 0
    assert preview.channels[0].confidence == dataset.curves["rop"].metadata.semantic.confidence
    assert dataset.parameters == {}


def test_commit_applies_overrides_to_copy_and_keeps_source_untouched() -> None:
    dataset = _dataset()
    controller = ImportReviewController()
    initial = controller.initial_plan(dataset)
    rop = initial.channels[0]
    spp = initial.channels[1]
    plan = replace(
        initial,
        index_mnemonic="MD_REVIEWED",
        index_role=IndexRole.DEPTH,
        index_type=IndexType.MD,
        index_unit="ft",
        null_value=-999.25,
        channels=(
            replace(
                rop,
                canonical_mnemonic="ROP_MANUAL",
                canonical_kind="drilling.rop_manual",
                quantity_class=QuantityClass.LINEAR_VELOCITY,
                unit="ft/h",
            ),
            replace(spp, import_enabled=False),
        ),
    )

    committed = controller.commit(dataset, plan)

    assert committed.dataset is not dataset
    assert committed.dataset.active_index.mnemonic == "MD_REVIEWED"
    assert committed.dataset.active_index.unit == "ft"
    assert set(committed.dataset.curves) == {"rop"}
    curve = committed.dataset.curves["rop"]
    assert np.isnan(curve.values[1])
    assert curve.metadata.unit == "ft/h"
    assert curve.metadata.canonical_mnemonic == "ROP_MANUAL"
    assert curve.metadata.semantic is not None
    assert curve.metadata.semantic.canonical_kind == "drilling.rop_manual"
    assert curve.metadata.semantic.matched_by == "manual_import_review"
    assert committed.dataset.parameters["IMPORT_REVIEW_ACCEPTED"] == "true"
    assert dataset.active_index.mnemonic == "DEPT"
    assert dataset.curves["rop"].values[1] == -999.25
    assert set(dataset.curves) == {"rop", "spp"}
    assert dataset.parameters == {}


def test_preview_reports_index_qc_without_mutating_dataset() -> None:
    dataset = _dataset()
    dataset.active_index.values = np.array([100.0, 100.0, 99.0])
    dataset.depth = dataset.active_index.values.copy()
    controller = ImportReviewController()

    review = controller.preview(dataset, controller.initial_plan(dataset))

    assert review.index_duplicate_count == 1
    assert review.index_direction == "descending"
    assert {issue.code for issue in review.issues} >= {
        "duplicate-index-values",
        "descending-index",
    }
    assert np.array_equal(dataset.depth, np.array([100.0, 100.0, 99.0]))


def test_commit_rejects_blocking_errors_atomically() -> None:
    dataset = _dataset()
    controller = ImportReviewController()
    initial = controller.initial_plan(dataset)
    plan = replace(
        initial,
        index_role=IndexRole.TIME,
        index_type=IndexType.MD,
        channels=tuple(replace(item, import_enabled=False) for item in initial.channels),
    )

    with pytest.raises(ImportReviewValidationError) as error:
        controller.commit(dataset, plan)

    assert error.value.review.error_count == 2
    assert {issue.code for issue in error.value.review.issues} == {
        "index-role-type-conflict",
        "no-imported-channels",
    }
    assert set(dataset.curves) == {"rop", "spp"}
    assert dataset.parameters == {}


def test_plan_rejects_duplicate_curve_overrides() -> None:
    with pytest.raises(ValueError, match="duplicate curve"):
        ImportReviewPlan(
            active_index_id="index",
            index_mnemonic="DEPT",
            index_role=IndexRole.DEPTH,
            index_type=IndexType.MD,
            index_unit="m",
            channels=(ImportChannelOverride("c1"), ImportChannelOverride("c1")),
        )
