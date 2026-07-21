from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.dataset_copy import create_dataset_copy


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
