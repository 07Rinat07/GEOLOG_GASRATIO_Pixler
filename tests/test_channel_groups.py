import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.channel_groups import default_curve_mnemonics


def test_default_curve_group_prefers_gas_and_recognizes_tgas() -> None:
    dataset = Dataset(
        "dataset",
        "Mixed",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    for mnemonic in ("LITH_CODE", "C2", "TGAS", "C1", "ZONE_CODE"):
        dataset.curves[mnemonic] = CurveData(
            CurveMetadata(mnemonic, mnemonic, mnemonic, None, None, dataset.dataset_id),
            np.array([1.0, 2.0]),
        )

    assert default_curve_mnemonics(dataset) == ["TGAS", "C1", "C2"]
