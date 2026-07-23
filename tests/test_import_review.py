from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.import_review import build_import_review
from geoworkbench.services.semantic_channels import SemanticChannelDictionary


def _dataset() -> Dataset:
    dataset = Dataset(
        "dataset-1",
        "Review",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 100.2, 100.4]),
    )
    dictionary = SemanticChannelDictionary()
    rop = dictionary.resolve("ROP", unit="м/ч")
    unknown = dictionary.resolve("X77", unit="ticks")
    dataset.curves = {
        "rop": CurveData(
            CurveMetadata(
                "rop",
                "ROP",
                rop.canonical_mnemonic,
                "м/ч",
                "Rate",
                dataset.dataset_id,
                semantic=rop,
            ),
            np.array([1.0, np.nan, 3.0]),
        ),
        "unknown": CurveData(
            CurveMetadata(
                "unknown",
                "X77",
                unknown.canonical_mnemonic,
                "ticks",
                None,
                dataset.dataset_id,
                semantic=unknown,
            ),
            np.array([np.nan, np.nan, np.nan]),
        ),
    }
    return dataset


def test_import_review_exposes_index_semantics_nulls_and_channel_bindings() -> None:
    review = build_import_review(_dataset())

    assert review.index_mnemonic == "DEPT"
    assert review.index_role == "depth"
    assert review.row_count == 3
    assert len(review.channels) == 2

    rop = review.channels[0]
    assert rop.canonical_kind == "drilling.rop"
    assert rop.quantity_class == "linear_velocity"
    assert rop.valid_count == 2
    assert rop.null_count == 1
    assert rop.issues == ()

    unknown = review.channels[1]
    assert unknown.canonical_kind == "unknown.x77"
    assert unknown.valid_count == 0
    assert {issue.code for issue in unknown.issues} == {
        "unresolved-semantic-channel",
        "unknown-channel-uom",
        "all-null-channel",
    }
    assert review.warning_count == 3
    assert review.error_count == 0


def test_import_review_is_read_only_when_legacy_curve_has_no_binding() -> None:
    dataset = Dataset(
        "dataset-legacy",
        "Legacy",
        DatasetKind.USER,
        DepthDomain.MD,
        np.array([0.0, 1.0]),
    )
    curve = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", None, dataset.dataset_id),
        np.array([0.1, 0.2]),
    )
    dataset.curves[curve.metadata.curve_id] = curve

    review = build_import_review(dataset)

    assert review.channels[0].canonical_kind == "gas.c1"
    assert curve.metadata.semantic is None


def test_import_review_marks_semantic_uom_quantity_conflict_as_error() -> None:
    dataset = Dataset(
        "dataset-conflict",
        "Conflict",
        DatasetKind.USER,
        DepthDomain.MD,
        np.array([0.0, 1.0]),
    )
    binding = SemanticChannelDictionary().resolve("C1", unit="psi")
    curve = CurveData(
        CurveMetadata(
            "c1",
            "C1",
            binding.canonical_mnemonic,
            "psi",
            None,
            dataset.dataset_id,
            semantic=binding,
        ),
        np.array([1.0, 2.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve

    review = build_import_review(dataset)

    assert review.error_count == 1
    assert {issue.code for issue in review.channels[0].issues} == {
        "channel-uom-conflict"
    }
