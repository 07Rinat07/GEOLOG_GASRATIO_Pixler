from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.dataset_copy import create_dataset_copy
from geoworkbench.services.report_passport import _parse_formula_provenance


def test_dataset_copy_has_independent_arrays_and_new_identity() -> None:
    source = Dataset(
        "source",
        "Original",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([100.0, 100.5, 101.0]),
    )
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", "Gamma ray", "source"),
        np.asarray([10.0, 20.0, 30.0]),
    )

    copy = create_dataset_copy(source, name="Copy", provenance="test-copy")

    assert copy.dataset_id != source.dataset_id
    assert copy.name == "Copy"
    assert copy.source_path is None
    assert copy.active_index_id != source.active_index_id
    np.testing.assert_allclose(copy.depth, source.depth)
    copied_curve = copy.curve_by_mnemonic("GR")
    assert copied_curve is not None
    assert copied_curve.metadata.curve_id != "gr"
    assert copied_curve.metadata.source_dataset_id == copy.dataset_id

    copy.depth[0] = 999.0
    copied_curve.values[0] = 999.0
    assert source.depth[0] == 100.0
    assert source.curve_by_mnemonic("GR").values[0] == 10.0


def test_copy_preserves_formula_identity_and_immediate_curve_lineage() -> None:
    source = Dataset("source", "Original", DatasetKind.GTI, DepthDomain.MD, np.array([1., 2.]))
    for curve_id, provenance in (
        ("custom", "custom-formula:calc1:2"),
        ("profile", "calculation:profile1:3"),
        ("plain", "source"),
    ):
        source.curves[curve_id] = CurveData(
            CurveMetadata(curve_id, curve_id, curve_id, None, None, "source", provenance),
            np.array([1., 2.]),
        )
    copied = create_dataset_copy(source, name="Copy", provenance="external-las-copy")
    for curve_id, identity in (("custom", ("custom-formula", "calc1", "2")),
                               ("profile", ("calculation", "profile1", "3"))):
        curve = copied.curve_by_mnemonic(curve_id)
        assert _parse_formula_provenance(curve.metadata.provenance) == identity
        assert curve.metadata.provenance.endswith(f"external-las-copy:source:{curve_id}")
    assert copied.curve_by_mnemonic("plain").metadata.provenance == "external-las-copy:source:plain"
    second = create_dataset_copy(copied, name="Second", provenance="external-las-copy")
    copied_custom = copied.curve_by_mnemonic("custom")
    second_custom = second.curve_by_mnemonic("custom")
    assert _parse_formula_provenance(second_custom.metadata.provenance) == ("custom-formula", "calc1", "2")
    assert second_custom.metadata.provenance.endswith(
        f"external-las-copy:{copied.dataset_id}:{copied_custom.metadata.curve_id}"
    )
